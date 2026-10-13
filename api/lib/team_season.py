"""Exact, coverage-aware descriptive season factors. No predictive ratings.

All football classification comes from nfl_core. The season layer pools raw
counters and pairs each team's output with its opponent's output; it never
averages the rounded values returned by the game UI.
"""

from collections import Counter
from datetime import datetime
import math
import re

from .nfl_core import process_game_stats, reconcile_final_boxscore

SCHEMA_VERSION = 1
METRIC_VERSION = "eight-factors-full-game-v1"
FACTORS = (
    {"id": "success_rate", "label": "Success rate", "unit": "percent", "higherIsBetter": True,
     "numerator": "Successful Plays", "denominator": "Plays"},
    {"id": "yards_per_play", "label": "Adjusted yards / play", "unit": "yards/play", "higherIsBetter": True,
     "numerator": "Offensive Yards", "denominator": "Plays"},
    {"id": "explosive_rate", "label": "Explosive-play rate", "unit": "percent", "higherIsBetter": True,
     "numerator": "Explosive Plays", "denominator": "Plays"},
    {"id": "points_per_trip", "label": "Points per trip inside 40", "unit": "points/trip", "higherIsBetter": True,
     "numerator": "Points Inside 40", "denominator": "Drives Inside 40"},
    {"id": "turnovers", "label": "Turnovers", "unit": "per game", "higherIsBetter": False,
     "numerator": "Turnovers", "denominator": None},
    {"id": "field_position", "label": "Starting field position", "unit": "yardline", "higherIsBetter": True,
     "numerator": "Start Field Pos Sum", "denominator": "Drives Count"},
    {"id": "penalties", "label": "Penalty yards", "unit": "yards/game", "higherIsBetter": False,
     "numerator": "Penalty Yards", "denominator": None},
    {"id": "non_offensive_points", "label": "Non-offensive points", "unit": "points/game", "higherIsBetter": True,
     "numerator": "Non-Offensive Points", "denominator": None},
)


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def measure(numerator, denominator, reasons=()):
    valid = not reasons and all(isinstance(x, (int, float)) and math.isfinite(x)
                                for x in (numerator, denominator))
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if valid and denominator > 0 else None,
            "usable": bool(valid), "reasons": sorted(set(reasons))}


def official_int(value):
    try:
        return int(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None


def extract_game(raw):
    """Return one audited completed-game record or raise for invalid metadata."""
    header = raw.get("header") or {}
    season = header.get("season") or {}
    competitions = header.get("competitions") or []
    if len(competitions) != 1:
        raise ValueError("Expected one competition")
    competition = competitions[0]
    status = (competition.get("status") or {}).get("type") or {}
    if status.get("state") != "post" or not status.get("completed", True):
        raise ValueError("Game is not final")
    competitors = competition.get("competitors") or []
    if len(competitors) != 2 or len({str(c.get("id")) for c in competitors}) != 2:
        raise ValueError("Expected two distinct teams")
    game_id = str(header.get("id") or competition.get("id") or "")
    if not game_id or not competition.get("date"):
        raise ValueError("Missing game ID or kickoff")
    timestamp(competition["date"])
    counts = {}
    rows, details = process_game_stats(raw, expanded=True, wp_threshold=1.0,
                                       aggregate_stats=counts)
    rows, gaps = reconcile_final_boxscore(raw, rows, details)
    by_abbr = {r["Team"]: r for r in rows}
    boxes = {str(t["team"]["id"]): t for t in (raw.get("boxscore") or {}).get("teams") or []}
    if set(boxes) != {str(c["id"]) for c in competitors} or set(counts) != set(boxes):
        raise ValueError("Box score and competitor team IDs disagree")
    score_by_side = {c["homeAway"]: int(c["score"]) for c in competitors}
    scoring = raw.get("scoringPlays") or []
    last_score = scoring[-1] if scoring else {}
    scoring_complete = all(last_score.get(f"{side}Score", 0) == score
                           for side, score in score_by_side.items())
    teams = []
    for comp in competitors:
        tid = str(comp["id"])
        box = boxes[tid]
        abbr = box["team"]["abbreviation"]
        row = by_abbr[abbr]
        stats = {s.get("name"): s.get("displayValue") for s in box.get("statistics") or []}
        missing_box = any(official_int(stats.get(k)) is None for k in ("totalYards", "totalOffensivePlays"))
        # Conservative game-level exclusion: a gap on either side can affect
        # drive starts, trips, opponent values, and possession attribution.
        play_reasons = (["boxscore_play_feed_gap"] if gaps else [])
        if missing_box:
            play_reasons.append("missing_official_validation")
        if not (raw.get("drives") or {}).get("previous"):
            play_reasons.append("missing_drive_feed")
        factors = {}
        for factor in FACTORS:
            key = factor["id"]
            numerator = counts[tid][factor["numerator"]]
            denominator = counts[tid][factor["denominator"]] if factor["denominator"] else 1
            reasons = list(play_reasons)
            if key == "turnovers":
                # Reconciled official giveaways plus the existing onside rule.
                numerator = row["Turnovers"]
                reasons = [] if official_int(stats.get("turnovers")) is not None else ["missing_official_turnovers"]
            elif key == "penalties":
                penalty = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", str(stats.get("totalPenaltiesYards", "")))
                numerator = int(penalty.group(2)) if penalty else None
                reasons = [] if penalty else ["missing_official_penalty_yards"]
            elif key == "non_offensive_points" and not scoring_complete:
                reasons.append("incomplete_scoring_feed")
            factors[key] = measure(numerator, denominator, reasons)
        teams.append({"id": tid, "abbr": abbr,
                      "name": comp["team"].get("displayName", abbr),
                      "homeAway": comp["homeAway"], "score": int(comp["score"]),
                      "counters": counts[tid], "factors": factors})
    return {"gameId": game_id, "season": int(season["year"]),
            "seasonType": int(season["type"]), "week": int(header["week"]),
            "kickoff": competition["date"], "sourceGaps": gaps, "teams": teams}


def select_events(schedules, season, season_type=2, through_week=18):
    """Calendar-year ESPN responses can contain two NFL seasons. Filter both."""
    events = {}
    for schedule in schedules:
        for event in schedule.get("events") or []:
            if (event.get("season", {}).get("year") != season
                    or event.get("season", {}).get("type") != season_type
                    or event.get("week", {}).get("number", 999) > through_week):
                continue
            events[str(event["id"])] = event
    return sorted(events.values(), key=lambda e: (e["date"], str(e["id"])))


def pool(measures, expected_games):
    usable = [m for m in measures if m["usable"]]
    numerator = sum(m["numerator"] for m in usable)
    denominator = sum(m["denominator"] for m in usable)
    result = measure(numerator, denominator)
    result.update({"gamesIncluded": len(usable), "gamesExpected": expected_games,
                   "complete": expected_games > 0 and len(usable) == expected_games,
                   "excludedReasons": dict(Counter(reason for m in measures for reason in m["reasons"]))})
    if not usable:
        result["value"] = None
    result.pop("usable")
    result.pop("reasons")
    return result


def add_ranks(teams):
    """Competition ranks on unrounded values; ties share a rank/percentile.

    A rank is only comparable within its explicitly published qualified pool.
    Incomplete team factors remain visible but receive no rank or percentile.
    """
    for factor in FACTORS:
        for view in ("own", "opponent", "net"):
            higher = True if view == "net" else factor["higherIsBetter"] == (view == "own")
            eligible = [t["factors"][factor["id"]][view] for t in teams
                        if t["factors"][factor["id"]][view]["complete"]
                        and t["factors"][factor["id"]][view]["value"] is not None]
            values = [m["value"] for m in eligible]
            for team in teams:
                m = team["factors"][factor["id"]][view]
                m.update({"rank": None, "percentile": None, "rankPool": len(values), "leagueSize": len(teams)})
                if not m["complete"] or m["value"] is None:
                    continue
                v = m["value"]
                equal = sum(math.isclose(x, v, rel_tol=1e-10, abs_tol=1e-10) for x in values)
                better = sum(not math.isclose(x, v, rel_tol=1e-10, abs_tol=1e-10)
                             and (x > v if higher else x < v) for x in values)
                m["rank"] = better + 1
                m["tied"] = equal > 1
                m["percentile"] = (100 * (len(values) - better - (equal + 1) / 2) / (len(values) - 1)
                                     if len(values) > 1 else 50)


def aggregate_season(records, events, season, season_type=2, through_week=18,
                     source="ESPN", metric_version=METRIC_VERSION):
    """Build one cutoff snapshot using schedule-derived expected game counts.

    Raw records outside the snapshot are never used. Duplicate IDs are rejected
    instead of silently counting the same game twice.
    """
    selected = select_events([{"events": events}], season, season_type, through_week)
    finals = {str(e["id"]): e for e in selected
              if e.get("status", {}).get("type", {}).get("state") == "post"}
    by_game = {}
    for record in records:
        gid = record["gameId"]
        if gid not in finals:
            continue
        if gid in by_game:
            raise ValueError(f"Duplicate game {gid}")
        event = finals[gid]
        expected_ids = {str(c["id"]) for c in event["competitions"][0]["competitors"]}
        if (record["season"] != season or record["seasonType"] != season_type
                or record["week"] != event["week"]["number"]
                or {t["id"] for t in record["teams"]} != expected_ids):
            raise ValueError(f"Game {gid} metadata disagrees with schedule")
        by_game[gid] = record
    roster = {}
    for event in selected:
        for c in event["competitions"][0]["competitors"]:
            t = c["team"]
            roster[str(c["id"])] = {"id": str(c["id"]), "abbr": t["abbreviation"], "name": t["displayName"]}
    teams = []
    for tid, meta in sorted(roster.items(), key=lambda item: item[1]["abbr"]):
        schedule = []
        pairs = []
        wins = losses = ties = 0
        expected = 0
        for event in selected:
            comps = event["competitions"][0]["competitors"]
            own = next((c for c in comps if str(c["id"]) == tid), None)
            if not own:
                continue
            opponent = next(c for c in comps if str(c["id"]) != tid)
            gid = str(event["id"])
            final = gid in finals
            expected += final
            score = int(own["score"]) if final else None
            against = int(opponent["score"]) if final else None
            if final:
                wins += score > against
                losses += score < against
                ties += score == against
            schedule.append({"gameId": gid, "week": event["week"]["number"], "kickoff": event["date"],
                             "gameUrl": event.get("gameUrl", f"/game/{gid}" if source == "ESPN" else None),
                             "opponentId": str(opponent["id"]), "opponent": opponent["team"]["abbreviation"],
                             "homeAway": own["homeAway"], "final": final, "score": score, "opponentScore": against,
                             "dataAvailable": gid in by_game})
            if gid in by_game:
                rt = by_game[gid]["teams"]
                pairs.append((next(t for t in rt if t["id"] == tid), next(t for t in rt if t["id"] != tid)))
        factors = {}
        for f in FACTORS:
            key = f["id"]
            own = pool([a["factors"][key] for a, b in pairs], expected)
            opponent = pool([b["factors"][key] for a, b in pairs], expected)
            paired = [(a["factors"][key], b["factors"][key]) for a, b in pairs
                      if a["factors"][key]["usable"] and b["factors"][key]["usable"]]
            paired_own = pool([a for a, b in paired], expected)
            paired_opp = pool([b for a, b in paired], expected)
            sign = 1 if f["higherIsBetter"] else -1
            net_value = (sign * (paired_own["value"] - paired_opp["value"])
                         if paired_own["value"] is not None and paired_opp["value"] is not None else None)
            factors[key] = {"own": own, "opponent": opponent,
                            "net": {"value": net_value, "gamesIncluded": len(paired), "gamesExpected": expected,
                                    "pairedOwnValue": paired_own["value"], "pairedOpponentValue": paired_opp["value"],
                                    "complete": expected > 0 and len(paired) == expected}}
        teams.append({**meta, "record": {"wins": wins, "losses": losses, "ties": ties},
                      "gamesExpected": expected, "gamesAvailable": len(pairs), "schedule": schedule, "factors": factors})
    add_ranks(teams)
    league = {}
    for f in FACTORS:
        ms = [t["factors"][f["id"]]["own"] for t in teams]
        numerator = sum(m["numerator"] for m in ms)
        denominator = sum(m["denominator"] for m in ms)
        league[f["id"]] = {"value": numerator / denominator if denominator else None,
                            "teamGamesIncluded": sum(m["gamesIncluded"] for m in ms),
                            "teamGamesExpected": sum(m["gamesExpected"] for m in ms)}
    return {"schemaVersion": SCHEMA_VERSION, "metricVersion": metric_version,
            "season": season, "seasonType": season_type, "throughWeek": through_week,
            "scope": "full_game", "source": source, "snapshotType": "retrospective_recalculation",
            "expectedGames": len(finals), "availableGames": len(by_game),
            "missingGameIds": sorted(set(finals) - set(by_game)),
            "factors": list(FACTORS), "league": league, "teams": teams,
            "powerRankings": {"status": "not_fitted", "marketInputs": False}}
