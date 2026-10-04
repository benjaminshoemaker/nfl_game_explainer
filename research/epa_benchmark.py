"""Reproducible ESPN EPA benchmark against postgame nflverse play values.

Run with ``PYTHONPATH=. .venv/bin/python research/epa_benchmark.py``.
The output is an ignored JSON evidence file; this does not change the app.
The reference is a comparison target, not ground truth for disputed states.
"""

import argparse
import json
import hashlib
import re
import urllib.request
from collections import Counter
from pathlib import Path

import duckdb
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from api.lib.game_analysis import get_game_data
from research.espn_epa import (
    embedded_extra_point_epa, embedded_two_point_epa, estimate_play_epa,
    possession_id,
)
from research.nflfastr_ep_model import load_model as load_nflfastr_model
from research.nflfastr_ep_model import predict_ep as predict_nflfastr_ep


ROOT = Path(__file__).resolve().parents[1]
PBP_2025 = Path("/tmp/nfl_game_explainer_pbp_2025.parquet")
PBP_2026 = Path("/tmp/nfl_game_explainer_pbp_2026.parquet")
PARQUET_SHA256 = {
    2025: "c6ecedd6d678cc37ed316b23ef84ee1ec6abb69c514bb11868a7ebd5a367df29",
    2026: "e04965158a00a23cf89193f9959c05f9e532f4313f2fde62fce074b226832273",
}
OUT = ROOT / "audits/epa_goal_benchmark.json"
EPA_TOLERANCE = 0.25
CATEGORIES = ("offense", "special_teams", "penalty", "kneel", "spike", "two_point")
GAMES = {
    "401872950": "2026_03_CIN_PIT",
    "401872951": "2026_03_HOU_IND",
    "401872954": "2026_03_NYJ_DET",
    "401872955": "2026_03_SEA_WAS",
    "401872956": "2026_03_TEN_NYG",
    "401872957": "2026_03_NE_JAX",
    "401872959": "2026_03_MIN_TB",
    "401872961": "2026_03_LV_NO",
    "401872962": "2026_03_LA_DEN",
    "401872963": "2026_03_PHI_CHI",
}
HOLDOUT_GAMES = {
    "401872958": "2026_03_ARI_SF",
    "401872948": "2026_03_ATL_GB",
    "401872960": "2026_03_BAL_DAL",
    "401872949": "2026_03_CAR_CLE",
    "401872952": "2026_03_KC_MIA",
    "401872953": "2026_03_LAC_BUF",
}
FEATURES = (
    "down", "ydstogo", "yardline_100", "half_seconds_remaining",
    "posteam_timeouts_remaining", "defteam_timeouts_remaining",
)


def ensure_parquet(year, path):
    if not path.exists():
        url = f"https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{year}.parquet"
        urllib.request.urlretrieve(url, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != PARQUET_SHA256[year]:
        raise RuntimeError(f"{path} has changed; inspect and re-pin this audit's reference before continuing")


def espn_game_data(game_id, refresh=False):
    path = ROOT / "audits" / f"epa_espn_{game_id}.json"
    if refresh or not path.exists():
        raw = get_game_data(game_id)
        path.write_text(json.dumps(raw, separators=(",", ":")) + "\n")
    payload = path.read_bytes()
    return json.loads(payload), hashlib.sha256(payload).hexdigest()


def reference_rows(conn, parquet, where, params=()):
    columns = (
        "game_id, cast(play_id as bigint) as play_id, play_type, "
        "two_point_attempt, posteam, defteam, touchdown, safety, "
        "interception, fumble_lost, down, ydstogo, yardline_100, "
        "half_seconds_remaining, posteam_timeouts_remaining, "
        "defteam_timeouts_remaining, roof, ep, epa, \"desc\" as description"
    )
    cur = conn.execute(
        f"select {columns} from read_parquet(?) where {where}",
        [str(parquet), *params],
    )
    names = [x[0] for x in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def feature_vector(row):
    values = [row.get(k) for k in FEATURES]
    if any(v is None for v in values):
        return None
    down, distance, yardline, seconds = values[:4]
    if not (1 <= down <= 4 and 1 <= distance <= 40 and
            1 <= yardline <= 99 and 0 <= seconds <= 1800):
        return None
    if not all(0 <= n <= 3 for n in values[4:]):
        return None
    return values


def espn_state(play):
    start = play.get("start") or {}
    yardline_100 = start.get("yardsToEndzone")
    kind = ((play.get("type") or {}).get("text") or "").lower()
    if "punt" in kind:
        # ESPN's punt start.yardsToEndzone is sometimes the yard line on the
        # punter's own side. The displayed spot retains the side of the field.
        spot = re.search(r"\bat\s+([A-Z]{2,3})\s+(\d{1,2})\b",
                         start.get("downDistanceText") or "")
        offense = play.get("_epa_team_abbreviation")
        if spot and offense:
            side, yard = spot.group(1), int(spot.group(2))
            yardline_100 = 100 - yard if side == offense else yard
    period = (play.get("period") or {}).get("number")
    clock = (play.get("clock") or {}).get("displayValue") or ""
    match = re.fullmatch(r"(\d+):(\d{2})", clock)
    if period not in (1, 2, 3, 4) or not match:
        seconds = None
    else:
        seconds = int(match.group(1)) * 60 + int(match.group(2))
        if period in (1, 3):
            seconds += 900
    return {
        "down": start.get("down"),
        "ydstogo": start.get("distance"),
        "yardline_100": yardline_100,
        "half_seconds_remaining": seconds,
        "posteam_timeouts_remaining": play.get("_epa_offense_timeouts"),
        "defteam_timeouts_remaining": play.get("_epa_defense_timeouts"),
        "home": play.get("_epa_home"),
        "roof": play.get("_epa_roof"),
    }


def venue_roof(venue_id, refresh=False):
    path = ROOT / "audits" / f"epa_venue_{venue_id}.json"
    url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/venues/{venue_id}"
    if refresh or not path.exists():
        with urllib.request.urlopen(url, timeout=15) as response:
            venue = json.load(response)
        path.write_text(json.dumps(venue, separators=(",", ":")) + "\n")
    venue = json.loads(path.read_text())
    if not venue.get("indoor"):
        return "outdoors"
    # ESPN exposes indoor but not retractable. These venue names have
    # independently documented retractable roofs.
    if venue.get("fullName") in ("Lucas Oil Stadium", "AT&T Stadium"):
        return "retractable"
    return "dome"


def annotate_timeouts(plays, competitors):
    id_to_team = {c["team"]["id"]: c["team"]["abbreviation"] for c in competitors}
    city_to_team = {c["team"]["location"].lower(): c["team"]["abbreviation"] for c in competitors}
    normalized = lambda x: {
        "LA": "LAR", "WAS": "WSH", "HST": "HOU",
        "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE",
    }.get(x, x)
    counts = {normalized(team): 3 for team in id_to_team.values()}
    last_period = None
    for play in plays:
        period = (play.get("period") or {}).get("number")
        if period == 3 and last_period != 3:
            counts = {team: 3 for team in counts}
        last_period = period
        text = play.get("text", "")
        challenge = re.search(r"([^.]*) challenged .*\(Timeout #(\d+)\.\)", text, re.I)
        if challenge:
            preceding = challenge.group(1).lower()
            for city, team_name in city_to_team.items():
                if preceding.endswith(city):
                    counts[normalized(team_name)] = max(0, 3 - int(challenge.group(2)))
                    break
        offense = normalized(id_to_team.get((play.get("start") or {}).get("team", {}).get("id")))
        if offense in counts:
            play["_epa_team_abbreviation"] = offense
            defense = next(team for team in counts if team != offense)
            play["_epa_offense_timeouts"] = counts[offense]
            play["_epa_defense_timeouts"] = counts[defense]
        match = re.search(r"Timeout #(\d+) by ([A-Z]{2,3})", text, re.I)
        if match:
            team = normalized(match.group(2).upper())
            if team in counts:
                counts[team] = max(0, 3 - int(match.group(1)))


def play_suffix(game_id, play):
    full = str(play.get("id") or "")
    if not full.startswith(game_id) or not full[len(game_id):].isdigit():
        return None
    return int(full[len(game_id):])


def eligible(row):
    return row["play_type"] in ("run", "pass") and not row["two_point_attempt"]


def benchmark_category(row):
    if row.get("two_point_attempt"):
        return "two_point"
    if eligible(row):
        return "offense"
    if row["play_type"] in ("kickoff", "punt", "field_goal", "extra_point"):
        return "special_teams"
    if row["play_type"] == "no_play" and re.search(
        r"\bpenalty\b", row.get("description") or "", re.I
    ):
        return "penalty"
    if row["play_type"] == "qb_kneel":
        return "kneel"
    if row["play_type"] == "qb_spike":
        return "spike"
    return None


def benchmark_result(rows, predicted):
    """Score coverage on every eligible row, including missing ESPN IDs."""
    by_category = {}
    for category in CATEGORIES:
        selected = [r for r in rows if benchmark_category(r) == category and r["epa"] is not None]
        compared = [(r, predicted[r["play_id"]]) for r in selected if r["play_id"] in predicted]
        errors = [value - row["epa"] for row, value in compared]
        within = sum(abs(error) <= EPA_TOLERANCE for error in errors)
        by_category[category] = {
            "eligible": len(selected),
            "predicted": len(compared),
            "coverage": len(compared) / len(selected) if selected else None,
            "within_tolerance": within,
            "agreement_given_prediction": within / len(compared) if compared else None,
            "agreement_all_eligible": within / len(selected) if selected else None,
            "error": summarize_errors(errors),
        }
    return by_category


def team_epa_summary(compared_plays):
    """Compare team splits without counting mirrored defense twice."""
    result = {}
    for row in compared_plays:
        if row["espn_estimate"] is None:
            continue
        category = benchmark_category(row)
        if category == "offense":
            assignments = ((row["reference_posteam"], "offense", 1),
                           (row["reference_defteam"], "defense", -1))
        elif category == "special_teams":
            assignments = ((row["reference_posteam"], "special_teams", 1),
                           (row["reference_defteam"], "special_teams", -1))
        else:
            assignments = ((row["reference_posteam"], category, 1),
                           (row["reference_defteam"], f"{category}_defense", -1))
        for team, label, sign in assignments:
            bucket = result.setdefault(row["game_id"], {}).setdefault(team, {}).setdefault(
                label, {"plays": 0, "espn_epa": 0.0, "nflverse_epa": 0.0,
                        "within_tolerance": 0})
            bucket["plays"] += 1
            bucket["espn_epa"] += sign * row["espn_estimate"]
            bucket["nflverse_epa"] += sign * row["reference_epa"]
            bucket["within_tolerance"] += abs(row["error"]) <= EPA_TOLERANCE
    return result


def safe_successor(plays, position, ref_by_id, game_id):
    current = plays[position]
    if current.get("scoringPlay") or current.get("isPenalty") or current.get("isTurnover"):
        return None
    end = current.get("end") or {}
    start = current.get("start") or {}
    if not end or end.get("team", {}).get("id") != start.get("team", {}).get("id"):
        return None
    for later in plays[position + 1:]:
        typ = (later.get("type") or {}).get("text", "").lower()
        if "timeout" in typ or "two-minute warning" in typ:
            continue
        later_start = later.get("start") or {}
        if any(end.get(k) != later_start.get(k) for k in ("down", "distance", "yardsToEndzone")):
            return None
        if end.get("team", {}).get("id") != later_start.get("team", {}).get("id"):
            return None
        if (current.get("homeScore"), current.get("awayScore")) != (later.get("homeScore"), later.get("awayScore")):
            return None
        ref = ref_by_id.get(play_suffix(game_id, later))
        if ref is None or not eligible(ref):
            return None
        return later, ref
    return None


def summarize_errors(values):
    if not values:
        return None
    a = np.abs(np.asarray(values, dtype=float))
    return {
        "n": len(a), "mae": float(a.mean()),
        "median_abs": float(np.median(a)), "p90_abs": float(np.quantile(a, 0.9)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", choices=("development", "holdout"),
                        default="development")
    parser.add_argument("--refresh-espn", action="store_true",
                        help="replace local ESPN snapshots with current API responses")
    args = parser.parse_args()
    games_map = GAMES if args.sample == "development" else HOLDOUT_GAMES
    output = OUT if args.sample == "development" else ROOT / "audits/epa_goal_holdout.json"
    ensure_parquet(2025, PBP_2025)
    ensure_parquet(2026, PBP_2026)
    conn = duckdb.connect()
    nflfastr_model = load_nflfastr_model()
    train = reference_rows(
        conn, PBP_2025,
        "season=2025 and season_type='REG' and ep is not null",
    )
    train = [row for row in train if feature_vector(row) is not None]
    x_train = np.asarray([feature_vector(row) for row in train], dtype=float)
    y_train = np.asarray([row["ep"] for row in train], dtype=float)
    model = HistGradientBoostingRegressor(
        max_iter=300, max_leaf_nodes=50, learning_rate=0.07,
        l2_regularization=5, random_state=5,
    ).fit(x_train, y_train)
    fg_train = [row for row in train if row["play_type"] == "field_goal"]
    fg_model = HistGradientBoostingRegressor(
        max_iter=160, max_leaf_nodes=12, min_samples_leaf=15,
        learning_rate=0.05, l2_regularization=5, random_state=5,
    ).fit(
        np.asarray([feature_vector(row) for row in fg_train], dtype=float),
        np.asarray([row["ep"] for row in fg_train], dtype=float),
    )
    xp_expected = conn.execute(
        "select avg(ep) from read_parquet(?) "
        "where season=2025 and season_type='REG' "
        "and play_type='extra_point' and ep is not null",
        [str(PBP_2025)],
    ).fetchone()[0]
    two_point_expected = conn.execute(
        "select avg(ep) from read_parquet(?) "
        "where season=2025 and season_type='REG' "
        "and two_point_attempt and ep is not null",
        [str(PBP_2025)],
    ).fetchone()[0]

    refs = reference_rows(
        conn, PBP_2026,
        "season=2026 and season_type='REG' and week=3 and game_id in ("
        + ",".join("?" for _ in games_map) + ")",
        tuple(games_map.values()),
    )
    by_game = {gid: {} for gid in games_map.values()}
    for row in refs:
        by_game[row["game_id"]][row["play_id"]] = row

    def predict(row):
        v = feature_vector(row)
        if v is None:
            return None
        return float(model.predict(np.asarray([v], dtype=float))[0])

    def predict_fg(row):
        v = feature_vector(row)
        if v is None:
            return None
        return float(fg_model.predict(np.asarray([v], dtype=float))[0])

    def predict_exact(row):
        return predict_nflfastr_ep(nflfastr_model, row)

    games = []
    all_ep_ref_errors = []
    all_ep_esp_errors = []
    all_ep_state_deltas = []
    all_safe_ref_errors = []
    all_safe_esp_errors = []
    all_safe_state_deltas = []
    all_safe_play_errors = []
    benchmark_rows = []
    benchmark_predictions = {}
    benchmark_teams = {}
    espn_hashes = {}
    for game_id, ref_game_id in games_map.items():
        raw, espn_hashes[game_id] = espn_game_data(game_id, args.refresh_espn)
        competition = raw["header"]["competitions"][0]
        venue_id = raw["gameInfo"]["venue"]["id"]
        roof = venue_roof(venue_id, args.refresh_espn)
        home_id = next(str(c["team"]["id"]) for c in competition["competitors"]
                       if c["homeAway"] == "home")
        teams = {c["homeAway"]: c["team"]["abbreviation"] for c in competition["competitors"]}
        plays = [p for drive in raw.get("drives", {}).get("previous", []) for p in drive.get("plays", [])]
        plays += (raw.get("drives", {}).get("current") or {}).get("plays", [])
        annotate_timeouts(plays, competition["competitors"])
        for play in plays:
            starter = str(((play.get("start") or {}).get("team") or {}).get("id") or "")
            play["_epa_home"] = int(starter == home_id) if starter else None
            play["_epa_roof"] = roof
        esp_by_id = {play_suffix(game_id, p): p for p in plays if play_suffix(game_id, p) is not None}
        if len(esp_by_id) != sum(play_suffix(game_id, p) is not None for p in plays):
            raise AssertionError(f"duplicate ESPN play ID in {game_id}")
        ref_by_id = by_game[ref_game_id]
        if not ref_by_id:
            raise AssertionError(f"no nflverse rows for {ref_game_id}")
        offense = [r for r in ref_by_id.values() if eligible(r)]
        benchmark_rows.extend(ref_by_id.values())
        team_ids = {str(c["team"]["id"]) for c in competition["competitors"]}
        team_abbr = {str(c["team"]["id"]): {
            "WSH": "WAS", "LAR": "LA",
        }.get(c["team"]["abbreviation"], c["team"]["abbreviation"])
            for c in competition["competitors"]}
        for position, play in enumerate(plays):
            suffix = play_suffix(game_id, play)
            if suffix is None:
                continue
            estimate = estimate_play_epa(
                plays, position, team_ids, espn_state, predict_exact, predict_fg,
                period_ended=True,
            )
            if estimate is not None:
                benchmark_predictions[(ref_game_id, suffix)] = estimate
                benchmark_teams[(ref_game_id, suffix)] = team_abbr.get(
                    possession_id(play, team_ids))
        # ESPN folds PATs and two-point tries into touchdown descriptions.
        # Align a synthetic estimate with the later nflverse ID only for
        # evaluation; the result comes from ESPN text and 2025 expected points.
        ordered_espn = sorted(
            ((play_suffix(game_id, p), p) for p in plays
             if play_suffix(game_id, p) is not None),
            key=lambda pair: pair[0],
        )
        for ref in ref_by_id.values():
            if ref["play_type"] != "extra_point" and not ref["two_point_attempt"]:
                continue
            preceding = [p for suffix, p in ordered_espn if suffix < ref["play_id"]]
            for candidate in reversed(preceding):
                kind = ((candidate.get("type") or {}).get("text") or "").lower()
                if "kickoff" in kind or (candidate.get("scoringPlay") and
                                          (candidate.get("scoringType") or {}).get("name") != "touchdown"):
                    break
                if (candidate.get("scoringType") or {}).get("name") == "touchdown":
                    estimate = (
                        embedded_two_point_epa(candidate, two_point_expected)
                        if ref["two_point_attempt"] else
                        embedded_extra_point_epa(candidate, xp_expected)
                    )
                    if estimate is not None:
                        benchmark_predictions[(ref_game_id, ref["play_id"])] = estimate
                        scorer = str(((candidate.get("end") or {}).get("team") or {}).get("id") or "")
                        benchmark_teams[(ref_game_id, ref["play_id"])] = team_abbr.get(scorer)
                    break
        match_ids = [r for r in offense if r["play_id"] in esp_by_id]
        missing = [r for r in offense if r["play_id"] not in esp_by_id]
        state_valid = []
        state_exact = []
        state_mismatch = []
        ep_ref_errors = []
        ep_esp_errors = []
        ep_state_deltas = []
        for ref in match_ids:
            esp = espn_state(esp_by_id[ref["play_id"]])
            if feature_vector(esp) is None or feature_vector(ref) is None:
                continue
            state_valid.append(ref)
            differences = [k for k in FEATURES if esp[k] != ref[k]]
            if differences:
                state_mismatch.append({
                    "id": ref["play_id"], "fields": differences,
                    "espn": esp, "nflverse": {k: ref[k] for k in FEATURES},
                    "description": ref["description"],
                })
            else:
                state_exact.append(ref)
            if ref["ep"] is not None:
                pred_ref, pred_esp = predict(ref), predict(esp)
                ep_ref_errors.append(pred_ref - ref["ep"])
                ep_esp_errors.append(pred_esp - ref["ep"])
                ep_state_deltas.append(pred_esp - pred_ref)

        safe_ref_errors = []
        safe_esp_errors = []
        safe_state_deltas = []
        safe_play_errors = []
        safe_count = 0
        for position, play in enumerate(plays):
            ref = ref_by_id.get(play_suffix(game_id, play))
            if ref is None or not eligible(ref) or ref["epa"] is None:
                continue
            next_pair = safe_successor(plays, position, ref_by_id, game_id)
            if next_pair is None:
                continue
            next_esp_play, next_ref = next_pair
            current_esp, next_esp = espn_state(play), espn_state(next_esp_play)
            if any(feature_vector(x) is None for x in (ref, next_ref, current_esp, next_esp)):
                continue
            safe_count += 1
            approx_ref = predict(next_ref) - predict(ref)
            approx_esp = predict(next_esp) - predict(current_esp)
            safe_ref_errors.append(approx_ref - ref["epa"])
            safe_esp_errors.append(approx_esp - ref["epa"])
            safe_state_deltas.append(approx_esp - approx_ref)
            safe_play_errors.append({
                "id": ref["play_id"], "description": ref["description"],
                "reference_epa": ref["epa"],
                "model_using_reference_states": approx_ref,
                "model_using_espn_states": approx_esp,
                "error_using_espn_states": approx_esp - ref["epa"],
            })

        all_ep_ref_errors.extend(ep_ref_errors)
        all_ep_esp_errors.extend(ep_esp_errors)
        all_ep_state_deltas.extend(ep_state_deltas)
        all_safe_ref_errors.extend(safe_ref_errors)
        all_safe_esp_errors.extend(safe_esp_errors)
        all_safe_state_deltas.extend(safe_state_deltas)
        all_safe_play_errors.extend({**row, "game": game_id} for row in safe_play_errors)
        games.append({
            "espn_game_id": game_id, "nflverse_game_id": ref_game_id,
            "matchup": f"{teams['away']} at {teams['home']}",
            "espn_venue_id": venue_id, "inferred_model_roof": roof,
            "espn_rows": len(plays), "nflverse_rows": len(ref_by_id),
            "nflverse_offensive_plays": len(offense),
            "offensive_id_matched": len(match_ids),
            "offensive_missing_ids": [{"id": r["play_id"], "type": r["play_type"],
                                       "description": r["description"]} for r in missing],
            "matched_state_valid": len(state_valid),
            "matched_state_exact": len(state_exact),
            "state_mismatches": state_mismatch,
            "reference_roof": Counter(str(r["roof"]) for r in offense),
            "espn_timeout_rows": sum(bool(re.search(r"Timeout #\d+ by", p.get("text", ""), re.I)) for p in plays),
            "nflverse_timeout_rows": sum(bool(r["description"] and re.search(r"Timeout #\d+ by", r["description"], re.I)) for r in ref_by_id.values()),
            "ep_model_on_reference": summarize_errors(ep_ref_errors),
            "ep_model_on_espn": summarize_errors(ep_esp_errors),
            "ep_change_from_espn_state": summarize_errors(ep_state_deltas),
            "safe_subset_plays": safe_count,
            "safe_epa_model_on_reference": summarize_errors(safe_ref_errors),
            "safe_epa_model_on_espn": summarize_errors(safe_esp_errors),
            "safe_epa_change_from_espn_state": summarize_errors(safe_state_deltas),
            "largest_safe_epa_errors": sorted(
                safe_play_errors, key=lambda row: abs(row["error_using_espn_states"]), reverse=True
            )[:5],
        })
        print(game_id, games[-1]["matchup"], len(offense), len(match_ids),
              len(state_exact), safe_count, flush=True)

    # Play IDs are unique only within a game; flatten with a compound key.
    benchmark = benchmark_result(
        [{**r, "play_id": (r["game_id"], r["play_id"])} for r in benchmark_rows],
        benchmark_predictions,
    )
    game_benchmarks = {
        game["nflverse_game_id"]: benchmark_result(
            [{**r, "play_id": (r["game_id"], r["play_id"])}
             for r in benchmark_rows if r["game_id"] == game["nflverse_game_id"]],
            benchmark_predictions,
        )
        for game in games
    }
    compared_plays = [
        {"game_id": row["game_id"], "play_id": row["play_id"],
         "play_type": row["play_type"], "description": row["description"],
         "two_point_attempt": row["two_point_attempt"],
         "touchdown": row["touchdown"], "safety": row["safety"],
         "interception": row["interception"], "fumble_lost": row["fumble_lost"],
         "reference_posteam": row["posteam"], "reference_defteam": row["defteam"],
         "espn_posteam": benchmark_teams.get((row["game_id"], row["play_id"])),
         "reference_epa": row["epa"],
         "espn_estimate": benchmark_predictions.get((row["game_id"], row["play_id"])),
         "error": (
             benchmark_predictions[(row["game_id"], row["play_id"])] - row["epa"]
             if (row["game_id"], row["play_id"]) in benchmark_predictions else None
         )}
        for row in benchmark_rows
        if benchmark_category(row) and row["epa"] is not None
    ]
    subgroups = {
        "scoring_offense": [r for r in compared_plays if benchmark_category(r) == "offense"
                            and (r["touchdown"] or r["safety"])],
        "turnover_offense": [r for r in compared_plays if benchmark_category(r) == "offense"
                             and (r["interception"] or r["fumble_lost"])],
    }
    subgroup_scores = {
        name: benchmark_result(
            [{**r, "play_id": (r["game_id"], r["play_id"]), "epa": r["reference_epa"]}
             for r in rows],
            {(r["game_id"], r["play_id"]): r["espn_estimate"]
             for r in rows if r["espn_estimate"] is not None},
        )["offense"]
        for name, rows in subgroups.items()
    }
    report = {
        "benchmark": {
            "epa_tolerance": EPA_TOLERANCE,
            "criteria": "at least 95% coverage and at least 95% of predicted plays within tolerance in each football-play category; defense mirrors opponent offensive EPA",
            "uncategorized_with_epa": sum(
                benchmark_category(r) is None and r["epa"] is not None
                for r in benchmark_rows
            ),
            "uncategorized_by_play_type": dict(Counter(
                r["play_type"] or "<null>" for r in benchmark_rows
                if benchmark_category(r) is None and r["epa"] is not None
            )),
            "categories": benchmark,
            "by_game": game_benchmarks,
            "by_team": team_epa_summary(compared_plays),
            "subgroups": subgroup_scores,
            "team_assignment_mismatches": [
                {"game_id": r["game_id"], "play_id": r["play_id"],
                 "espn_posteam": r["espn_posteam"],
                 "reference_posteam": r["reference_posteam"]}
                for r in compared_plays if r["espn_estimate"] is not None
                and r["espn_posteam"] != r["reference_posteam"]
            ],
            "compared_plays": compared_plays,
            "method_limit": "Completed-game comparison: non-scoring ESPN plays use the next eligible ESPN event; touchdown PATs and two-point tries are synthesized from ESPN touchdown text and aligned to nflverse IDs only for evaluation",
        },
        "data_sources": {"espn": "live summary responses fetched by app's get_game_data",
                         "espn_snapshot_sha256": espn_hashes,
                         "nflverse_2025": str(PBP_2025), "nflverse_2026": str(PBP_2026)},
        "sample": args.sample,
        "model": "Benchmarked EPA uses the pinned published nflfastR EP XGBoost model on ESPN-derived states, a 2025-trained field-goal EP surrogate, and 2025 mean extra-point and two-point EP; legacy safe-subset diagnostics still use the six-feature surrogate",
        "model_training_rows": len(train),
        "summary": {
            "offensive_plays": sum(g["nflverse_offensive_plays"] for g in games),
            "offensive_id_matched": sum(g["offensive_id_matched"] for g in games),
            "matched_state_valid": sum(g["matched_state_valid"] for g in games),
            "matched_state_exact": sum(g["matched_state_exact"] for g in games),
            "ep_model_on_reference": summarize_errors(all_ep_ref_errors),
            "ep_model_on_espn": summarize_errors(all_ep_esp_errors),
            "ep_change_from_espn_state": summarize_errors(all_ep_state_deltas),
            "safe_subset_plays": sum(g["safe_subset_plays"] for g in games),
            "safe_epa_model_on_reference": summarize_errors(all_safe_ref_errors),
            "safe_epa_model_on_espn": summarize_errors(all_safe_esp_errors),
            "safe_epa_change_from_espn_state": summarize_errors(all_safe_state_deltas),
            "largest_safe_epa_errors": sorted(
                all_safe_play_errors, key=lambda row: abs(row["error_using_espn_states"]), reverse=True
            )[:15],
        },
        "games": games,
    }
    output.write_text(json.dumps(report, indent=2, default=dict) + "\n")
    print("saved", output, flush=True)


if __name__ == "__main__":
    main()
