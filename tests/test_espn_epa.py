"""Check score and possession signs in the ESPN-only EPA transition code."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.espn_epa import (
    embedded_extra_point_epa, embedded_two_point_epa, estimate_play_epa,
    possession_id,
)


def play(team, ep, kind="Rush", period=1, scoring=None, scorer=None):
    return {
        "start": {"team": {"id": team}, "ep_for_test": ep},
        "end": {"team": {"id": scorer or team}},
        "period": {"number": period},
        "type": {"text": kind},
        "scoringType": {"name": scoring} if scoring else None,
    }


def state(row):
    return {"ep": row["start"]["ep_for_test"],
            "posteam_timeouts_remaining": 3,
            "defteam_timeouts_remaining": 3}


def predict(row):
    return row["ep"]


def test_touchdown_uses_scoring_team_not_starting_team():
    offensive = play("A", 2, scoring="touchdown", scorer="A")
    defensive = play("A", 2, scoring="touchdown", scorer="B")
    assert estimate_play_epa([offensive], 0, {"A", "B"}, state, predict, predict) == 5
    assert estimate_play_epa([defensive], 0, {"A", "B"}, state, predict, predict) == -9


def test_possession_flip_negates_next_expected_points():
    plays = [play("A", 1), play("B", 2)]
    assert estimate_play_epa(plays, 0, {"A", "B"}, state, predict, predict) == -3


def test_administrative_timeout_is_not_the_successor_state():
    plays = [play("A", 1), play("B", 6, "Official Timeout"), play("B", 2)]
    assert estimate_play_epa(plays, 0, {"A", "B"}, state, predict, predict) == -3


def test_own_side_kneel_has_zero_successor_expected_points():
    kneel = play("B", 2, "Rush")
    kneel["text"] = "Quarterback kneels to B 19 for -1 yards."
    def own_side_state(row):
        return {**state(row), "yardline_100": 81}
    assert estimate_play_epa([play("A", 4), kneel], 0,
                             {"A", "B"}, own_side_state, predict, predict) == -4


def test_kickoff_belongs_to_receiving_team():
    plays = [play("A", 0.5, "Kickoff"), play("B", 1.5)]
    assert estimate_play_epa(plays, 0, {"A", "B"}, state, predict, predict) == 1.0


def test_nullified_kickoff_filed_as_penalty_belongs_to_receiver():
    kickoff = play("A", 0.5, "Penalty")
    kickoff["start"]["down"] = 0
    kickoff["text"] = "Kicker kicks 61 yards from A 35 to B 4. PENALTY - No Play."
    assert possession_id(kickoff, {"A", "B"}) == "B"


def test_end_of_half_has_zero_terminal_expected_points():
    plays = [play("A", 1.4, period=2), play("B", 0.8, period=3)]
    assert estimate_play_epa(plays, 0, {"A", "B"}, state, predict, predict) == -1.4


def test_extra_point_embedded_in_touchdown_text():
    touchdown = play("A", 2, scoring="touchdown")
    touchdown["text"] = "TOUCHDOWN. J.Myers extra point is GOOD."
    assert abs(embedded_extra_point_epa(touchdown, 0.93) - 0.07) < 1e-9
    touchdown["text"] = "TOUCHDOWN. Extra point is NO GOOD."
    assert embedded_extra_point_epa(touchdown, 0.93) == -0.93


def test_two_point_attempt_embedded_in_touchdown_text():
    touchdown = play("A", 2, scoring="touchdown")
    touchdown["text"] = "TOUCHDOWN. TWO-POINT CONVERSION ATTEMPT. Pass is complete. ATTEMPT SUCCEEDS."
    assert embedded_two_point_epa(touchdown, 0.947) == 1.053
    touchdown["text"] = "TOUCHDOWN. TWO-POINT CONVERSION ATTEMPT. Pass is incomplete. ATTEMPT FAILS."
    assert embedded_two_point_epa(touchdown, 0.947) == -0.947
    touchdown["text"] = "TOUCHDOWN. Extra point is GOOD."
    assert embedded_two_point_epa(touchdown, 0.947) is None
