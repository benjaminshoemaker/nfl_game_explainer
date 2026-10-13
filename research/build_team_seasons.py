"""Build reproducible team-season snapshots and a factor coverage audit.

PYTHONPATH=. .venv/bin/python research/build_team_seasons.py --season 2025 --fetch-missing
Network access is opt-in. Generated sources, reports and payloads stay in the
gitignored game_summaries directory. No OpenAI, odds, or pregame WP are used.
"""

import argparse
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

from api.lib.game_analysis import get_game_data
from api.lib.team_season import FACTORS, METRIC_VERSION, aggregate_season, extract_game, select_events

ROOT = Path(__file__).resolve().parents[1]


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def load_schedule(season, directory, fetch):
    path = directory / f"season_schedule_{season}.json"
    urls = [("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
             f"?dates={year}&seasontype=2&limit=1000") for year in (season, season + 1)]
    if fetch:
        data = {"events": []}
        for url in urls:
            with urllib.request.urlopen(url, timeout=30) as response:
                part = json.load(response)
            data["events"].extend(part.get("events") or [])
        if not data.get("events"):
            raise ValueError("Schedule returned no events; previous snapshot was preserved")
        save_json(path, data)
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}; use --fetch-missing to obtain the schedule")
    return json.loads(path.read_text()), {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                                         "urls": urls, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def coverage_report(snapshot, errors):
    lines = [f"# {snapshot['season']} team-season coverage through Week {snapshot['throughWeek']}", "",
             "Retrospective full-game regular-season snapshot. No predictive model has been fitted.", "",
             f"- Teams: {len(snapshot['teams'])}",
             f"- Completed games on schedule: {snapshot['expectedGames']}",
             f"- Game payloads included: {snapshot['availableGames']}",
             f"- Missing or rejected games: {len(snapshot['missingGameIds'])}", "",
             "| Factor | Usable team-games | Expected team-games | Teams with complete net coverage |",
             "| --- | ---: | ---: | ---: |"]
    for factor in FACTORS:
        key = factor["id"]
        league = snapshot["league"][key]
        complete = sum(t["factors"][key]["net"]["complete"]
                       and t["factors"][key]["net"]["value"] is not None for t in snapshot["teams"])
        lines.append(f"| {factor['label']} | {league['teamGamesIncluded']} | {league['teamGamesExpected']} | {complete} |")
    validation = snapshot.get("validation") or {}
    lines.extend(["", "## Interpretation", "",
                  ("The independent efficiency audit was applied to this snapshot; disputed values are withheld from ranks."
                   if validation.get("independentEfficiencyAudit") else
                   "No independent efficiency audit was applied to this snapshot."),
                  "Rates pool exact counts and denominators. Net values use the same covered games on both sides; positive net always favors the listed team.",
                  "Official turnovers and penalty totals can be available when play-derived factors are incomplete. Other factors conservatively exclude games with box-score/play-feed gaps.",
                  "Incomplete factors retain covered-sample values but have no rank. Qualified-team ranks identify their pool size; they are not presented as full-league ranks when fewer than 32 teams qualify.",
                  "Agreement with box-score totals is a coverage screen, not independent proof that every play-derived value is correct.",
                  "The snapshot is recomputed from available corrected source files. It is not an archive of what was published before historical games.",
                  "No-opportunity rates remain null; real observed zeroes remain zero. Penalties and turnovers are displayed per game, with total numerators preserved.",
                  "Non-offensive points use the existing game parser convention, including its attribution of scoring-sequence points.",
                  "", "## Rejected games", ""])
    lines.extend([f"- {gid}: {message}" for gid, message in sorted(errors.items())] or ["None."])
    lines.extend(["", "## Next modeling gate", "",
                  "Resolve historical coverage and verify factor parity against an independent play stream before fitting predictive weights. Keep prior-season features chronological and all market-derived fields excluded.", ""])
    return "\n".join(lines)


def apply_independent_audit(records, audit, records_sha):
    """Withhold disputed efficiency factors without silently replacing sources."""
    if records_sha not in audit.get("inputs", {}).values():
        raise ValueError("Independent audit does not match these exact game records; rerun the audit")
    result = deepcopy(records)
    indexed = {(g["gameId"], t["abbr"]): t for g in result for t in g["teams"]}
    for difference in audit["differences"]:
        team = indexed[(difference["gameId"], difference["team"])]
        for key in ("success_rate", "yards_per_play", "explosive_rate"):
            m = team["factors"][key]
            m["usable"] = False
            m["value"] = None
            m["reasons"] = sorted(set(m["reasons"] + ["independent_source_disagreement"]))
    for missing in audit["unmatchedOrIncomplete"]:
        team = indexed[(missing["gameId"], missing["team"])]
        for key in ("success_rate", "yards_per_play", "explosive_rate"):
            m = team["factors"][key]
            m["usable"] = False
            m["value"] = None
            m["reasons"] = sorted(set(m["reasons"] + ["independent_reference_unavailable"]))
    return result


def build(args):
    output = args.output.resolve()
    sources = output / "sources"
    schedule, schedule_source = load_schedule(args.season, sources, args.fetch_missing)
    events = select_events([schedule], args.season, 2, args.through_week)
    finals = [e for e in events if e.get("status", {}).get("type", {}).get("state") == "post"]
    if not finals:
        raise ValueError("No completed regular-season games in the selected schedule")
    candidates = [sources / "games", ROOT / "pbp_cache",
                  ROOT / "audits" / f"factor_gap_{args.season}_cache"]
    paths = {}
    for event in finals:
        gid = str(event["id"])
        for directory in candidates:
            path = directory / f"{gid}.json"
            if path.exists():
                paths[gid] = path
                break
    errors = {}
    missing = [str(e["id"]) for e in finals if str(e["id"]) not in paths]
    print(f"{args.season}: {len(finals)} scheduled finals; {len(paths)} cached; {len(missing)} missing", flush=True)
    if args.fetch_missing:
        def fetch(gid):
            raw = get_game_data(gid)
            extract_game(raw)  # Never persist an error page or nonfinal payload as valid.
            path = sources / "games" / f"{gid}.json"
            save_json(path, raw)
            return path
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(fetch, gid): gid for gid in missing}
            for future in as_completed(futures):
                gid = futures[future]
                try:
                    paths[gid] = future.result()
                except Exception as error:
                    errors[gid] = f"{type(error).__name__}: {error}"
        print(f"Fetch complete: {len(paths)} payloads, {len(errors)} errors", flush=True)
    records = []
    manifest = []
    for event in finals:
        gid = str(event["id"])
        if gid not in paths:
            errors.setdefault(gid, "No cached source payload")
            continue
        path = paths[gid]
        content = path.read_bytes()
        try:
            record = extract_game(json.loads(content))
            if record["gameId"] != gid or record["season"] != args.season or record["seasonType"] != 2:
                raise ValueError("Source identity does not match requested game")
            records.append(record)
            manifest.append({"gameId": gid, "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                             "sha256": hashlib.sha256(content).hexdigest(),
                             "sourceFileModifiedAt": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
        except Exception as error:
            errors[gid] = f"{type(error).__name__}: {error}"
    records_content = json.dumps(records, indent=2, allow_nan=False) + "\n"
    checked_records = records
    audit_source = None
    if args.independent_audit:
        audit_content = args.independent_audit.read_bytes()
        independent = json.loads(audit_content)
        checked_records = apply_independent_audit(records, independent, hashlib.sha256(records_content.encode()).hexdigest())
        audit_source = {"path": str(args.independent_audit), "sha256": hashlib.sha256(audit_content).hexdigest()}
    snapshot = aggregate_season(checked_records, events, args.season, through_week=args.through_week)
    snapshot["validation"] = {"boxscoreScreen": True, "independentEfficiencyAudit": audit_source is not None,
                              "otherFactorsIndependentlyValidated": False}
    snapshot["generatedAt"] = datetime.now(timezone.utc).isoformat()
    snapshot["lastIncludedKickoff"] = max(r["kickoff"] for r in records) if records else None
    model = {"metricVersion": METRIC_VERSION, "generatedAt": snapshot["generatedAt"],
             "schedule": schedule_source, "games": manifest, "errors": errors, "independentAudit": audit_source,
             "calculationSha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                   for name in ("api/lib/nfl_core.py", "api/lib/team_season.py")}}
    stem = f"{args.season}-week-{args.through_week}"
    save_json(output / f"{stem}.json", snapshot)
    save_json(output / f"{stem}-games.json", records)
    save_json(output / f"{stem}-manifest.json", model)
    (output / f"{stem}-coverage.md").write_text(coverage_report(snapshot, errors))
    for week in range(1, args.through_week + 1):
        weekly = aggregate_season(checked_records, events, args.season, through_week=week)
        weekly["generatedAt"] = snapshot["generatedAt"]
        weekly["validation"] = snapshot["validation"]
        save_json(output / "weekly" / f"{args.season}-week-{week}.json", weekly)
    print(json.dumps({"snapshot": str(output / f"{stem}.json"), "teams": len(snapshot["teams"]),
                      "games": snapshot["availableGames"], "missing": snapshot["missingGameIds"]}), flush=True)
    return snapshot


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--through-week", type=int, default=18, choices=range(1, 19))
    parser.add_argument("--fetch-missing", action="store_true")
    parser.add_argument("--independent-audit", type=Path, help="An exact-input audit JSON produced by audit_team_seasons.py")
    parser.add_argument("--output", type=Path, default=ROOT / "game_summaries/team_seasons")
    build(parser.parse_args())
