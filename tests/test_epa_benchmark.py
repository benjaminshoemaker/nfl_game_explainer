"""Guard the EPA goal denominator against easy-subset inflation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.epa_benchmark import (
    GAMES, HOLDOUT_GAMES, benchmark_result, espn_state, team_epa_summary,
)


def test_benchmark_counts_missing_and_special_teams_in_coverage():
    rows = [
        {"play_id": ("game", 1), "play_type": "pass", "two_point_attempt": 0, "epa": 1.0},
        {"play_id": ("game", 2), "play_type": "run", "two_point_attempt": 0, "epa": -2.0},
        {"play_id": ("game", 3), "play_type": "kickoff", "two_point_attempt": 0, "epa": 0.5},
        {"play_id": ("game", 4), "play_type": "pass", "two_point_attempt": 1, "epa": 0.5},
    ]
    result = benchmark_result(rows, {("game", 1): 1.2, ("game", 3): 0.8})

    assert result["offense"]["eligible"] == 2
    assert result["offense"]["predicted"] == 1
    assert result["offense"]["agreement_given_prediction"] == 1.0
    assert result["offense"]["agreement_all_eligible"] == 0.5
    assert result["special_teams"]["eligible"] == 1
    assert result["special_teams"]["within_tolerance"] == 0


def test_punt_spot_uses_displayed_field_side():
    punt = {
        "type": {"text": "Punt"},
        "start": {"down": 4, "distance": 4, "yardsToEndzone": 26,
                  "downDistanceText": "4th & 4 at WSH 26"},
        "_epa_team_abbreviation": "WSH",
        "period": {"number": 1}, "clock": {"displayValue": "11:17"},
    }
    assert espn_state(punt)["yardline_100"] == 74


def test_development_and_holdout_games_are_disjoint():
    assert not (set(GAMES) & set(HOLDOUT_GAMES))
    assert not (set(GAMES.values()) & set(HOLDOUT_GAMES.values()))


def test_defense_is_negative_of_opponent_offense():
    rows = [{
        "game_id": "g", "play_type": "pass", "two_point_attempt": 0,
        "reference_posteam": "SEA", "reference_defteam": "WAS",
        "espn_estimate": 1.2, "reference_epa": 1.0, "error": 0.2,
    }]
    team = team_epa_summary(rows)["g"]
    assert team["SEA"]["offense"]["espn_epa"] == 1.2
    assert team["WAS"]["defense"]["espn_epa"] == -1.2
    assert team["WAS"]["defense"]["nflverse_epa"] == -1.0


def test_special_teams_net_is_zero_sum():
    rows = [{
        "game_id": "g", "play_type": "kickoff", "two_point_attempt": 0,
        "reference_posteam": "SEA", "reference_defteam": "WAS",
        "espn_estimate": 0.8, "reference_epa": 0.7, "error": 0.1,
    }]
    team = team_epa_summary(rows)["g"]
    assert team["SEA"]["special_teams"]["espn_epa"] == 0.8
    assert team["WAS"]["special_teams"]["espn_epa"] == -0.8
