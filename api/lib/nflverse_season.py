"""Pure nflverse adapter for the eight descriptive season factors.

Inputs are whitelisted play/schedule dictionaries supplied by the research
loader. No ESPN statistics, EPA success flag, WP, odds or imported ratings are
used. Unknown inputs withhold the affected factor, not the entire game.
"""

from collections import defaultdict
from datetime import datetime
import math
import re
from zoneinfo import ZoneInfo

from .nfl_core import calculate_success
from .team_season import FACTORS, measure

METRIC_VERSION = "nflverse-eight-factors-v1"
ALIASES = {"LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV", "WAS": "WSH"}

# An explicit whitelist prevents accidental market-derived model features.
PBP_COLUMNS = (
    "game_id", "play_id", "season", "season_type", "week", "home_team", "away_team",
    "posteam", "defteam", "play_type", "play_deleted", "down", "ydstogo", "yardline_100",
    "yards_gained", "passing_yards", "lateral_reception", "qb_dropback", "qb_scramble", "sack",
    "two_point_attempt", "extra_point_attempt", "fixed_drive", "drive_start_yard_line",
    "interception", "fumble", "fumble_lost", "fumbled_1_team", "fumbled_2_team",
    "fumble_recovery_1_team", "fumble_recovery_2_team", "own_kickoff_recovery",
    "penalty", "penalty_team", "penalty_yards", "touchdown", "td_team", "return_touchdown",
    "safety", "field_goal_result", "extra_point_result", "two_point_conv_result",
    "defensive_two_point_conv", "defensive_extra_point_conv", "posteam_score", "posteam_score_post",
    "defteam_score", "defteam_score_post", "special_teams_play", "desc",
)


def team_key(value):
    return ALIASES.get(value, value)


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def selected_offense(play):
    return (play.get("play_deleted") != 1 and play.get("two_point_attempt") != 1
            and play.get("play_type") in ("run", "pass"))


def yardline(value, offense, opponent):
    match = re.fullmatch(r"([A-Z]{2,3})\s+(\d{1,2})", str(value or ""))
    if not match:
        return 50 if str(value).strip() == "50" else None
    side, n = team_key(match.group(1)), int(match.group(2))
    if not 0 <= n <= 50:
        return None
    return n if side == offense else 100 - n if side == opponent else None


def schedule_event(row, team_names=None):
    """Normalize nflverse schedule metadata into the shared aggregate schema."""
    names = team_names or {}
    home, away = team_key(row["home_team"]), team_key(row["away_team"])
    complete = finite(row.get("home_score")) and finite(row.get("away_score"))
    date = datetime.fromisoformat(f"{row['gameday']}T{row.get('gametime') or '00:00'}")
    date = date.replace(tzinfo=ZoneInfo("America/New_York")).isoformat()
    espn_id = row.get("espn")
    if isinstance(espn_id, float) and finite(espn_id):
        espn_id = str(int(espn_id))
    competitors = [{"id": team, "homeAway": side, "score": int(row[f"{side}_score"]) if complete else None,
                    "team": {"id": team, "abbreviation": team, "displayName": names.get(team, team)}}
                   for team, side in ((home, "home"), (away, "away"))]
    return {"id": row["game_id"], "date": date, "season": {"year": int(row["season"]),
            "type": 2 if row["game_type"] == "REG" else 3}, "week": {"number": int(row["week"])},
            "status": {"type": {"state": "post" if complete else "pre"}},
            "competitions": [{"competitors": competitors}],
            "gameUrl": f"/game/{espn_id}" if espn_id else None}


def extract_game(plays, event):
    if event["status"]["type"]["state"] != "post":
        raise ValueError("Only completed games can enter season analysis")
    comps = event["competitions"][0]["competitors"]
    ids = [c["id"] for c in comps]
    if len(set(ids)) != 2:
        raise ValueError("Expected two distinct teams")
    opponent = {ids[0]: ids[1], ids[1]: ids[0]}
    plays = sorted(plays, key=lambda p: p["play_id"])
    if not plays or any(p["game_id"] != event["id"] for p in plays):
        raise ValueError("Missing plays or game identity mismatch")
    if len({p["play_id"] for p in plays}) != len(plays):
        raise ValueError("Duplicate play IDs")
    if any(p["season"] != event["season"]["year"] or p["week"] != event["week"]["number"]
           or {team_key(p["home_team"]), team_key(p["away_team"])} != set(ids)
           for p in plays):
        raise ValueError("Play metadata disagrees with schedule")
    counts = {team: {key: 0 for key in (
        "Plays", "Offensive Yards", "Successful Plays", "Explosive Plays", "Drives Inside 40",
        "Points Inside 40", "Start Field Pos Sum", "Drives Count", "Turnovers", "Penalty Yards",
        "Non-Offensive Points", "Interceptions", "Fumbles Lost", "Onside Recoveries Against")}
        for team in ids}
    reasons = {team: defaultdict(set) for team in ids}
    evidence = {team: {f["id"]: [] for f in FACTORS} for team in ids}
    scores = {team: 0 for team in ids}
    drives = defaultdict(list)
    drive_points = defaultdict(float)
    pending_td = None

    def flag(team, keys, reason):
        for target in ([team] if team in ids else ids):
            for key in keys:
                reasons[target][key].add(reason)

    def add_score(team, points, non_offensive=False, drive=None, play=None):
        if team not in ids:
            flag(None, ("non_offensive_points", "points_per_trip"), "unattributed_score")
            return
        scores[team] += points
        if non_offensive:
            counts[team]["Non-Offensive Points"] += points
            evidence[team]["non_offensive_points"].append({"playId": play["play_id"], "points": points})
        elif drive is not None:
            drive_points[(drive, team)] += points

    for p in plays:
        if p.get("play_deleted") == 1:
            continue
        own = team_key(p.get("posteam"))
        defense = team_key(p.get("defteam"))
        drive = p.get("fixed_drive")
        if finite(drive):
            drives[drive].append(p)
        elif selected_offense(p):
            flag(own, ("points_per_trip", "field_position"), "missing_drive_id")
        if selected_offense(p):
            if own not in ids:
                flag(None, ("success_rate", "yards_per_play", "explosive_rate"), "missing_offense")
                continue
            c = counts[own]
            c["Plays"] += 1
            yards = p.get("passing_yards") if p.get("lateral_reception") == 1 and finite(p.get("passing_yards")) else p.get("yards_gained")
            if not finite(yards):
                flag(own, ("success_rate", "yards_per_play", "explosive_rate"), "missing_yards")
            else:
                c["Offensive Yards"] += yards
                if p.get("down") not in (1, 2, 3, 4) or not finite(p.get("ydstogo")):
                    flag(own, ("success_rate",), "missing_down_or_distance")
                else:
                    c["Successful Plays"] += calculate_success(p["down"], p["ydstogo"], yards)
                dropback = p.get("qb_dropback") == 1 or p.get("qb_scramble") == 1 or p.get("sack") == 1 or p.get("play_type") == "pass"
                c["Explosive Plays"] += yards >= (20 if dropback else 10)

        # Provider-attributed, recorded penalty yards; retain no-play fouls.
        if p.get("penalty") == 1:
            charged = team_key(p.get("penalty_team"))
            if charged not in ids or not finite(p.get("penalty_yards")):
                flag(charged, ("penalties",), "missing_penalty_attribution_or_yards")
            else:
                counts[charged]["Penalty Yards"] += abs(p["penalty_yards"])
                evidence[charged]["penalties"].append({"playId": p["play_id"], "yards": abs(p["penalty_yards"])})

        # Conversion turnovers do not count as possession giveaways.
        if p.get("two_point_attempt") != 1 and p.get("extra_point_attempt") != 1:
            if p.get("interception") == 1:
                if own in ids:
                    counts[own]["Interceptions"] += 1
                    counts[own]["Turnovers"] += 1
                else:
                    flag(None, ("turnovers",), "unattributed_interception")
            fumble_losses = 0
            fumbles = [(team_key(p.get(f"fumbled_{i}_team")), team_key(p.get(f"fumble_recovery_{i}_team"))) for i in (1, 2)]
            for fumbling, recovering in fumbles:
                if fumbling in ids and recovering in ids and recovering != fumbling:
                    counts[fumbling]["Fumbles Lost"] += 1
                    counts[fumbling]["Turnovers"] += 1
                    fumble_losses += 1
            if p.get("fumble_lost") == 1 and not fumble_losses:
                known = [team for team, recovery in fumbles if team in ids]
                if len(known) == 1 and fumbles[0][1] is None:
                    # Lost fumble through an end zone need not name a recoverer.
                    counts[known[0]]["Fumbles Lost"] += 1
                    counts[known[0]]["Turnovers"] += 1
                else:
                    flag(None, ("turnovers",), "ambiguous_fumble_loss")
            if p.get("own_kickoff_recovery") == 1:
                if own in ids:
                    counts[own]["Onside Recoveries Against"] += 1
                    counts[own]["Turnovers"] += 1
                else:
                    flag(None, ("turnovers",), "unattributed_onside_recovery")

        if p.get("touchdown") == 1:
            scoring_team = team_key(p.get("td_team"))
            non_offensive = p.get("return_touchdown") == 1
            add_score(scoring_team, 6, non_offensive, drive, p)
            pending_td = (scoring_team, non_offensive, drive)
        if p.get("field_goal_result") == "made":
            add_score(own, 3, False, drive, p)
            pending_td = None
        if p.get("safety") == 1:
            # A special-teams safety can be awarded to either side. Prefer the
            # explicit score change; a missing/ambiguous attribution is flagged.
            deltas = [(team, p.get(after) - p.get(before)) for team, before, after in (
                (own, "posteam_score", "posteam_score_post"), (defense, "defteam_score", "defteam_score_post"))
                if finite(p.get(before)) and finite(p.get(after))]
            awarded = [team for team, delta in deltas if delta == 2]
            add_score(awarded[0] if len(awarded) == 1 else None, 2, True, None, p)
            pending_td = None
        if p.get("defensive_two_point_conv") == 1 or p.get("defensive_extra_point_conv") == 1:
            add_score(defense, 2, True, None, p)
        elif p.get("extra_point_result") == "good" or p.get("two_point_conv_result") == "success":
            points = 1 if p.get("extra_point_result") == "good" else 2
            if pending_td and pending_td[0] == own:
                add_score(own, points, pending_td[1], pending_td[2], p)
            else:
                add_score(own, points, False, drive, p)
                flag(own, ("points_per_trip", "non_offensive_points"), "conversion_without_touchdown_context")
        # Keep pending TD through penalties on a retry, clear it when normal
        # play resumes so an unrelated conversion cannot inherit attribution.
        if p.get("play_type") == "kickoff" and p.get("touchdown") != 1:
            pending_td = None

    for drive, rows in drives.items():
        scrimmage = [p for p in rows if p.get("play_type") in
                     ("run", "pass", "qb_kneel", "qb_spike", "punt", "field_goal")
                     and p.get("two_point_attempt") != 1]
        if not scrimmage:
            continue
        own = team_key(scrimmage[0].get("posteam"))
        if own not in ids:
            flag(None, ("field_position", "points_per_trip"), "unknown_drive_offense")
            continue
        actual = [p for p in scrimmage if team_key(p.get("posteam")) == own]
        if len(actual) != len(scrimmage):
            flag(own, ("field_position", "points_per_trip"), "mixed_drive_offenses")
        # NFLverse supplies the start AFTER the kickoff return and enforcement.
        starts = {yardline(p.get("drive_start_yard_line"), own, opponent[own]) for p in actual
                  if p.get("drive_start_yard_line")}
        starts.discard(None)
        start = next(iter(starts)) if len(starts) == 1 else None
        if start is None:
            flag(own, ("field_position",), "missing_or_conflicting_drive_start")
        else:
            counts[own]["Start Field Pos Sum"] += start
            counts[own]["Drives Count"] += 1
            evidence[own]["field_position"].append({"drive": drive, "start": start})
        eligible = [p for p in actual if selected_offense(p)]
        if not eligible:
            continue
        offensive_td = any(p.get("touchdown") == 1 and team_key(p.get("td_team")) == own
                           and p.get("return_touchdown") != 1 for p in actual)
        # A long TD qualifies even when no snap begins inside the 40. Otherwise
        # count any offensive state inside the 40, including a subsequent kick.
        reached = offensive_td or any(finite(p.get("yardline_100")) and p["yardline_100"] <= 40 for p in actual)
        if not reached and any(not finite(p.get("yardline_100")) for p in eligible):
            flag(own, ("points_per_trip",), "missing_trip_field_position")
        if reached:
            points = drive_points[(drive, own)]
            counts[own]["Drives Inside 40"] += 1
            counts[own]["Points Inside 40"] += points
            evidence[own]["points_per_trip"].append({"drive": drive, "points": points})

    for comp in comps:
        if scores[comp["id"]] != comp["score"]:
            flag(None, ("non_offensive_points", "points_per_trip"), "scoring_events_do_not_reconcile")
    teams = []
    for comp in comps:
        own = comp["id"]
        factors = {f["id"]: measure(counts[own][f["numerator"]], counts[own][f["denominator"]]
                                    if f["denominator"] else 1, reasons[own][f["id"]]) for f in FACTORS}
        teams.append({"id": own, "abbr": own, "name": comp["team"]["displayName"],
                      "homeAway": comp["homeAway"], "score": comp["score"],
                      "counters": counts[own], "factors": factors, "evidence": evidence[own]})
    return {"gameId": event["id"], "season": event["season"]["year"], "seasonType": event["season"]["type"],
            "week": event["week"]["number"], "kickoff": event["date"], "teams": teams,
            "source": "nflverse", "sourceGaps": [], "scoringCheck": scores}
