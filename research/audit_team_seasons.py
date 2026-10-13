"""Independent nflverse comparison for the three play-efficiency factors.

Recomputes this app's 40/60/100 success rule and 10/20 explosive thresholds;
nflverse's existing `success` column uses a different definition and is never
used. This diagnostic does not replace ESPN data or automatically clear gaps.
"""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import duckdb

from api.lib.nfl_core import _canonical_team_abbr
from research.build_team_seasons import save_json


def canonical(abbr):
    return _canonical_team_abbr(abbr).upper()


def reference_rows(parquet):
    # The lateral exception is shared with the independently adjudicated 2025
    # audit: yards_gained can contain only the final receiving lateral segment.
    with duckdb.connect() as conn:
        cursor = conn.execute("""
            WITH eligible AS (
                SELECT *, CASE WHEN play_type = 'pass' AND lateral_reception = 1
                                    AND passing_yards IS NOT NULL
                               THEN passing_yards ELSE yards_gained END AS metric_yards
                FROM read_parquet(?)
                WHERE season_type = 'REG' AND play_type IN ('run', 'pass')
                    AND coalesce(two_point_attempt, 0) = 0
                    AND coalesce(play_deleted, 0) = 0 AND posteam IS NOT NULL
            )
            SELECT season, week, home_team, away_team, posteam,
                count(*) AS plays, sum(metric_yards) AS yards,
                sum(CASE WHEN down = 1 AND metric_yards >= .4 * ydstogo THEN 1
                         WHEN down = 2 AND metric_yards >= .6 * ydstogo THEN 1
                         WHEN down IN (3,4) AND metric_yards >= ydstogo THEN 1
                         ELSE 0 END) AS successes,
                sum(CASE WHEN qb_dropback = 1 AND metric_yards >= 20 THEN 1
                         WHEN coalesce(qb_dropback, 0) = 0 AND metric_yards >= 10 THEN 1
                         ELSE 0 END) AS explosives,
                sum(CASE WHEN metric_yards IS NULL OR down IS NULL OR ydstogo IS NULL
                         THEN 1 ELSE 0 END) AS incomplete_plays
            FROM eligible GROUP BY season, week, home_team, away_team, posteam
        """, [str(parquet)])
        fields = [d[0] for d in cursor.description]
        return [dict(zip(fields, row)) for row in cursor.fetchall()]


def audit(records, refs):
    lookup = {}
    for ref in refs:
        key = (ref["season"], ref["week"], canonical(ref["home_team"]), canonical(ref["away_team"]), canonical(ref["posteam"]))
        if key in lookup:
            raise ValueError(f"Duplicate reference team-game {key}")
        lookup[key] = ref
    compared, missing = [], []
    for game in records:
        home = next(t for t in game["teams"] if t["homeAway"] == "home")
        away = next(t for t in game["teams"] if t["homeAway"] == "away")
        for team in game["teams"]:
            key = (game["season"], game["week"], canonical(home["abbr"]), canonical(away["abbr"]), canonical(team["abbr"]))
            ref = lookup.get(key)
            if ref is None or ref["incomplete_plays"]:
                missing.append({"gameId": game["gameId"], "team": team["abbr"],
                                "reason": "reference_missing" if ref is None else "reference_incomplete"})
                continue
            counters = team["counters"]
            a = [counters[k] for k in ("Plays", "Offensive Yards", "Successful Plays", "Explosive Plays")]
            b = [ref[k] for k in ("plays", "yards", "successes", "explosives")]
            deltas = {key: (a[index] / a[0] - b[index] / b[0]) if a[0] and b[0] else None
                      for key, index in (("yards_per_play", 1), ("success_rate", 2), ("explosive_rate", 3))}
            compared.append({"gameId": game["gameId"], "team": team["abbr"], "week": game["week"],
                             "espn": a, "nflverse": b, "exactCounters": a == b, "rateDeltas": deltas,
                             "boxscoreGapFlagged": bool(game["sourceGaps"])})
    totals = defaultdict(lambda: {source: {side: [0, 0, 0, 0] for side in ("own", "opponent")}
                                  for source in ("espn", "nflverse")})
    compared_by_game = defaultdict(list)
    for row in compared:
        compared_by_game[row["gameId"]].append(row)
    for rows in compared_by_game.values():
        if len(rows) != 2:
            continue
        for index, row in enumerate(rows):
            for source in ("espn", "nflverse"):
                for side, values in (("own", row[source]), ("opponent", rows[1 - index][source])):
                    for i, value in enumerate(values):
                        totals[row["team"]][source][side][i] += value
    net_comparison = {}
    for factor, index in (("yards_per_play", 1), ("success_rate", 2), ("explosive_rate", 3)):
        values = {source: {team: sides[source]["own"][index] / sides[source]["own"][0]
                                   - sides[source]["opponent"][index] / sides[source]["opponent"][0]
                           for team, sides in totals.items()
                           if sides[source]["own"][0] and sides[source]["opponent"][0]}
                  for source in ("espn", "nflverse")}
        ranks = {source: {team: 1 + sum(other > value + 1e-10 for other in by_team.values())
                          for team, value in by_team.items()} for source, by_team in values.items()}
        net_comparison[factor] = [
            {"team": team, "espn": values["espn"][team], "nflverse": values["nflverse"][team],
             "espnRank": ranks["espn"][team], "nflverseRank": ranks["nflverse"][team]}
            for team in sorted(set(values["espn"]) & set(values["nflverse"]))]
    return {"teamGamesCompared": len(compared), "unmatchedOrIncomplete": missing,
            "exactCounterMatches": sum(r["exactCounters"] for r in compared),
            "disagreementsWithoutBoxscoreFlag": sum(not r["exactCounters"] and not r["boxscoreGapFlagged"] for r in compared),
            "flaggedButCountersAgree": sum(r["exactCounters"] and r["boxscoreGapFlagged"] for r in compared),
            "differences": [r for r in compared if not r["exactCounters"]],
            "seasonNetComparison": net_comparison,
            "maxAbsoluteRateDelta": {key: max((abs(r["rateDeltas"][key]) for r in compared
                                               if r["rateDeltas"][key] is not None), default=None)
                                     for key in ("success_rate", "yards_per_play", "explosive_rate")},
            "definition": {"counterOrder": ["plays", "yards", "successes", "explosives"],
                           "success": "40/60/100 yards required; not nflverse EPA success",
                           "explosives": "20 yards on dropbacks including scrambles; 10 on runs",
                           "selection": "nflverse run/pass, no two-point tries or deleted plays; app selection can differ for aborted/fake-kick plays",
                           "scope": "Three efficiency factors only; trips, field position, scoring and turnovers require separate validation",
                           "seasonComparison": "Diagnostic net ranks from all mutually covered game pairs, BEFORE quality exclusions; not published product ranks",
                           "interpretation": "Disagreements include source gaps and conventions; nflverse is not assumed to be ground truth"}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(json.loads(args.games.read_text()), reference_rows(args.reference))
    result["inputs"] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.games, args.reference)}
    save_json(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("differences", "definition", "inputs", "seasonNetComparison")}, indent=2))
