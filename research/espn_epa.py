"""Experimental ESPN-only play EPA transitions.

The expected-points predictor is supplied by the caller. No nflverse play
fields or outcomes enter the estimates in this module.
"""

import re


def team_id(play):
    return str(((play.get("start") or {}).get("team") or {}).get("id") or "")


def is_kickoff_play(play):
    kind = ((play.get("type") or {}).get("text") or "").lower()
    if "kickoff" in kind:
        return True
    return ((play.get("start") or {}).get("down") == 0 and
            re.search(r"\bkicks?\s+\d+\s+yards\s+from\b",
                      play.get("text") or "", re.I) is not None)


def possession_id(play, team_ids):
    starter = team_id(play)
    if starter not in team_ids:
        return None
    if is_kickoff_play(play):
        return next(team for team in team_ids if team != starter)
    return starter


def preplay_ep(play, team_ids, espn_state, predict, predict_fg):
    kind = ((play.get("type") or {}).get("text") or "").lower()
    if kind in ("timeout", "official timeout", "two-minute warning",
                "end period", "coin toss"):
        return None
    state = espn_state(play)
    if ("kneel" in kind or re.search(r"\bkneels?\b", play.get("text") or "", re.I)):
        if state.get("yardline_100") is not None and state["yardline_100"] > 50:
            return 0.0
    if is_kickoff_play(play):
        # nflfastR evaluates a kickoff from the receiving team's hypothetical
        # first-and-ten at its 25; ESPN's start.team is the kicking team.
        state = {**state, "down": 1, "ydstogo": 10, "yardline_100": 75,
                 "home": 1 - state["home"] if state.get("home") is not None else None,
                 "posteam_timeouts_remaining": state["defteam_timeouts_remaining"],
                 "defteam_timeouts_remaining": state["posteam_timeouts_remaining"]}
    if not possession_id(play, team_ids):
        return None
    if "field goal" in kind:
        return predict_fg(state)
    return predict(state)


def embedded_extra_point_epa(touchdown_play, expected_point):
    """Recover a PAT result folded into an ESPN touchdown description."""
    if (touchdown_play.get("scoringType") or {}).get("name") != "touchdown":
        return None
    text = touchdown_play.get("text") or ""
    if re.search(r"extra point is (?:no good|missed|blocked|failed)", text, re.I):
        return -expected_point
    if re.search(r"extra point is good", text, re.I):
        return 1 - expected_point
    if re.search(r"\([^)]*\bKick\)", text, re.I):
        return 1 - expected_point
    return None


def embedded_two_point_epa(touchdown_play, expected_point):
    """Value a two-point try recorded only in ESPN's touchdown text."""
    if (touchdown_play.get("scoringType") or {}).get("name") != "touchdown":
        return None
    text = touchdown_play.get("text") or ""
    if not re.search(r"two-point conversion attempt", text, re.I):
        return None
    if re.search(r"attempt succeeds", text, re.I):
        return 2 - expected_point
    if re.search(r"attempt fails", text, re.I):
        return -expected_point
    return None


def estimate_play_epa(plays, position, team_ids, espn_state, predict,
                      predict_fg):
    play = plays[position]
    current_team = possession_id(play, team_ids)
    if current_team is None:
        return None
    before = preplay_ep(play, team_ids, espn_state, predict, predict_fg)
    if before is None:
        return None

    scoring = (play.get("scoringType") or {}).get("name")
    if scoring == "touchdown":
        scorer = str(((play.get("end") or {}).get("team") or {}).get("id") or "")
        if scorer in team_ids:
            return (7 if scorer == current_team else -7) - before
    if scoring == "field-goal":
        return 3 - before

    period = (play.get("period") or {}).get("number")
    for later in plays[position + 1:]:
        later_period = (later.get("period") or {}).get("number")
        if period in (2, 4) and later_period != period:
            return -before
        later_team = possession_id(later, team_ids)
        if later_team is None:
            continue
        after = preplay_ep(later, team_ids, espn_state, predict, predict_fg)
        if after is not None:
            return (after if later_team == current_team else -after) - before
    if period in (2, 4):
        return -before
    return None
