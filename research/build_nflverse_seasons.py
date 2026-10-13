"""Build canonical nflverse season datasets from local, checksum-recorded files.

PYTHONPATH=. .venv/bin/python research/build_nflverse_seasons.py --seasons 2024 2025 2026
Use --fetch to download missing sources from nflverse. Existing source files
are never overwritten implicitly. Research source columns explicitly exclude
odds, WP, and third-party ratings.
"""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

import duckdb

from api.lib.nflverse_season import METRIC_VERSION, PBP_COLUMNS, extract_game, schedule_event, team_key
from api.lib.team_season import FACTORS, aggregate_season
from research.build_team_seasons import save_json

ROOT = Path(__file__).resolve().parents[1]
SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
TEAMS_URL = "https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/teams_colors_logos.csv"


def ensure_file(path, url, fetch):
    if not path.exists():
        if not fetch:
            raise FileNotFoundError(f"Missing {path}; use --fetch or supply the local source")
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=90) as response:
            content = response.read()
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(content)
        temp.replace(path)
    return {"path": str(path.resolve()), "url": url, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load_events(schedule_path, teams_path, season, through_week):
    names = {}
    for row in csv.DictReader(teams_path.open()):
        key = team_key(row["team_abbr"])
        if key not in names or key == row["team_abbr"]:
            names[key] = row["team_name"]
    events = []
    for row in csv.DictReader(schedule_path.open()):
        if int(row["season"]) != season or row["game_type"] != "REG" or int(row["week"]) > through_week:
            continue
        # Only use schedule/identity/results columns. Never return market fields.
        clean = {k: row[k] for k in ("game_id", "season", "game_type", "week", "gameday", "gametime",
                                     "home_team", "away_team", "home_score", "away_score", "espn")}
        for side in ("home", "away"):
            clean[f"{side}_score"] = float(clean[f"{side}_score"]) if clean[f"{side}_score"] else None
        events.append(schedule_event(clean, names))
    if len({e["id"] for e in events}) != len(events):
        raise ValueError("Duplicate games in schedule")
    return events


def load_plays(path, season, through_week):
    with duckdb.connect() as conn:
        fields = {r[0] for r in conn.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()}
        missing = set(PBP_COLUMNS) - fields
        if missing:
            raise ValueError(f"Missing nflverse columns: {sorted(missing)}")
        # All identifiers are compile-time whitelist entries, never user input.
        columns = ",".join('"' + name + '"' for name in PBP_COLUMNS)
        cursor = conn.execute(f"SELECT {columns} FROM read_parquet(?) WHERE season=? AND season_type='REG' AND week<=? ORDER BY game_id,play_id",
                              [str(path), season, through_week])
        rows = cursor.fetchall()
    grouped = defaultdict(list)
    for row in rows:
        play = dict(zip(PBP_COLUMNS, row))
        grouped[play["game_id"]].append(play)
    return grouped


def build_season(season, args):
    output = args.output.resolve()
    sources = output / "sources"
    schedule = args.schedule or sources / "games.csv"
    teams = args.teams or sources / "teams.csv"
    parquet = Path(str(args.pbp_pattern).format(season=season))
    inputs = [ensure_file(schedule, SCHEDULE_URL, args.fetch), ensure_file(teams, TEAMS_URL, args.fetch),
              ensure_file(parquet, f"https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet", args.fetch)]
    events = load_events(schedule, teams, season, args.through_week)
    grouped = load_plays(parquet, season, args.through_week)
    # Default snapshot ends at the latest week represented in the PBP file.
    # Missing games WITHIN that week remain in the coverage denominator.
    if not grouped:
        raise ValueError(f"No regular-season plays for {season}")
    week = min(args.through_week, max(p[0]["week"] for p in grouped.values()))
    events = [e for e in events if e["week"]["number"] <= week]
    records, errors = [], {}
    for event in events:
        if event["status"]["type"]["state"] != "post":
            continue
        try:
            records.append(extract_game(grouped.get(event["id"], []), event))
        except (ValueError, TypeError, KeyError) as error:
            errors[event["id"]] = f"{type(error).__name__}: {error}"
    snapshot = aggregate_season(records, events, season, through_week=week,
                                source="nflverse", metric_version=METRIC_VERSION)
    snapshot["generatedAt"] = datetime.now(timezone.utc).isoformat()
    snapshot["validation"] = {"scoringReconciledGames": sum(all(g["scoringCheck"][t["id"]] == t["score"]
                                                                 for t in g["teams"]) for g in records),
                              "source": "nflverse", "providerComparisonRequired": False}
    stem = f"{season}-week-{week}"
    save_json(output / f"{stem}.json", snapshot)
    save_json(output / f"{stem}-games.json", records)
    save_json(output / f"{stem}-manifest.json", {"metricVersion": METRIC_VERSION, "inputs": inputs,
              "generatedAt": snapshot["generatedAt"], "errors": errors,
              "codeSha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                             ("api/lib/nflverse_season.py", "api/lib/team_season.py", "research/build_nflverse_seasons.py")}})
    for w in range(1, week + 1):
        weekly = aggregate_season(records, events, season, through_week=w, source="nflverse", metric_version=METRIC_VERSION)
        weekly["generatedAt"] = snapshot["generatedAt"]
        save_json(output / "weekly" / f"{season}-week-{w}.json", weekly)
    reasons = Counter(reason for g in records for t in g["teams"] for f in t["factors"].values() for reason in f["reasons"])
    coverage = {f["id"]: {"teamGames": snapshot["league"][f["id"]]["teamGamesIncluded"],
                            "rankedTeams": snapshot["teams"][0]["factors"][f["id"]]["net"]["rankPool"]}
                for f in FACTORS} if snapshot["teams"] else {}
    summary = {"season": season, "throughWeek": week, "games": len(records), "expected": snapshot["expectedGames"],
               "teams": len(snapshot["teams"]), "scoring": snapshot["validation"]["scoringReconciledGames"],
               "coverage": coverage, "reasons": dict(reasons), "errors": errors}
    save_json(output / f"{stem}-audit.json", summary)
    print(json.dumps(summary), flush=True)
    return snapshot


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", type=int, nargs="+", required=True)
    parser.add_argument("--through-week", type=int, default=18, choices=range(1, 19))
    parser.add_argument("--pbp-pattern", default="/tmp/nfl_game_explainer_pbp_{season}.parquet")
    parser.add_argument("--schedule", type=Path)
    parser.add_argument("--teams", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "game_summaries/nflverse")
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    for season in args.seasons:
        build_season(season, args)
