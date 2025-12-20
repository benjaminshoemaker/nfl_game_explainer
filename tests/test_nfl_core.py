"""
Unit tests for api/lib/nfl_core.py - Pure analytics functions.
"""
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from lib.nfl_core import (
    yardline_to_coord,
    calculate_success,
    any_stat_contains,
    is_penalty_play,
    is_spike_or_kneel,
    is_special_teams_play,
    is_nullified_play,
    classify_offense_play,
    is_competitive_play,
    process_game_stats,
    build_analysis_text,
)


# =============================================================================
# yardline_to_coord tests
# =============================================================================
class TestYardlineToCoord:
    def test_own_side(self):
        # Team at their own 25 yard line
        assert yardline_to_coord("SEA 25", "SEA") == 25

    def test_opponent_side(self):
        # Team at opponent's 30 yard line = 100 - 30 = 70
        assert yardline_to_coord("DAL 30", "SEA") == 70

    def test_midfield(self):
        # At the 50
        assert yardline_to_coord("SEA 50", "SEA") == 50
        assert yardline_to_coord("DAL 50", "SEA") == 50

    def test_goal_line_edge_cases(self):
        assert yardline_to_coord("SEA 1", "SEA") == 1
        assert yardline_to_coord("DAL 1", "SEA") == 99

    def test_case_insensitive(self):
        assert yardline_to_coord("sea 25", "SEA") == 25
        assert yardline_to_coord("SEA 25", "sea") == 25

    def test_invalid_input_none(self):
        assert yardline_to_coord(None, "SEA") is None
        assert yardline_to_coord("SEA 25", None) is None

    def test_invalid_input_empty(self):
        assert yardline_to_coord("", "SEA") is None
        assert yardline_to_coord("SEA 25", "") is None

    def test_invalid_format(self):
        assert yardline_to_coord("SEA", "SEA") is None
        assert yardline_to_coord("25", "SEA") is None
        assert yardline_to_coord("SEA 25 extra", "SEA") is None

    def test_non_numeric_yard(self):
        assert yardline_to_coord("SEA abc", "SEA") is None


# =============================================================================
# calculate_success tests
# =============================================================================
class TestCalculateSuccess:
    def test_first_down_threshold(self):
        # 1st & 10: need 4+ yards (40%)
        assert calculate_success(1, 10, 4) is True
        assert calculate_success(1, 10, 3.9) is False
        assert calculate_success(1, 10, 5) is True
        assert calculate_success(1, 10, 0) is False

    def test_second_down_threshold(self):
        # 2nd & 10: need 6+ yards (60%)
        assert calculate_success(2, 10, 6) is True
        assert calculate_success(2, 10, 5.9) is False
        assert calculate_success(2, 10, 10) is True

    def test_third_down_conversion(self):
        # 3rd down: need 100% of distance
        assert calculate_success(3, 5, 5) is True
        assert calculate_success(3, 5, 4.9) is False
        assert calculate_success(3, 5, 10) is True
        assert calculate_success(3, 1, 1) is True

    def test_fourth_down_conversion(self):
        # 4th down: same as 3rd
        assert calculate_success(4, 1, 1) is True
        assert calculate_success(4, 1, 0.9) is False
        assert calculate_success(4, 2, 5) is True

    def test_short_yardage_scenarios(self):
        # 1st & 1: need 0.4+ yards
        assert calculate_success(1, 1, 1) is True
        assert calculate_success(1, 1, 0) is False

    def test_invalid_down(self):
        assert calculate_success(0, 10, 5) is False
        assert calculate_success(5, 10, 5) is False


# =============================================================================
# any_stat_contains tests
# =============================================================================
class TestAnyStatContains:
    def test_finds_in_abbreviation(self):
        play = {
            "statistics": [
                {"type": {"abbreviation": "PASS", "text": "Passing Yards"}}
            ]
        }
        assert any_stat_contains(play, ["pass"]) is True
        assert any_stat_contains(play, ["rush"]) is False

    def test_finds_in_text(self):
        play = {
            "statistics": [
                {"type": {"abbreviation": "RU", "text": "Rushing Yards"}}
            ]
        }
        assert any_stat_contains(play, ["rush"]) is True
        assert any_stat_contains(play, ["pass"]) is False

    def test_multiple_needles(self):
        play = {
            "statistics": [
                {"type": {"abbreviation": "SK", "text": "Sack"}}
            ]
        }
        assert any_stat_contains(play, ["pass", "sack"]) is True
        assert any_stat_contains(play, ["rush", "punt"]) is False

    def test_empty_statistics(self):
        play = {"statistics": []}
        assert any_stat_contains(play, ["pass"]) is False

    def test_missing_statistics(self):
        play = {}
        assert any_stat_contains(play, ["pass"]) is False

    def test_case_insensitive(self):
        play = {
            "statistics": [
                {"type": {"abbreviation": "PASS", "text": "PASSING"}}
            ]
        }
        assert any_stat_contains(play, ["pass"]) is True


# =============================================================================
# is_penalty_play tests
# =============================================================================
class TestIsPenaltyPlay:
    def test_penalty_object_with_no_play(self):
        play = {"penalty": {"yards": 10}}
        assert is_penalty_play(play, "penalty on sea, no play", "penalty") is True

    def test_penalty_declined_text_returns_false(self):
        play = {"hasPenalty": True}
        assert is_penalty_play(play, "run for 10 yards, penalty declined", "rush") is False

    def test_has_penalty_flag_without_no_play_returns_false(self):
        play = {"hasPenalty": True}
        assert is_penalty_play(play, "pass complete", "pass") is False

    def test_has_penalty_flag_with_no_play_returns_true(self):
        play = {"hasPenalty": True}
        assert is_penalty_play(play, "penalty on aaa, no play", "pass") is True

    def test_no_play_with_penalty_in_text(self):
        play = {}
        assert is_penalty_play(play, "penalty on sea, no play", "pass") is True

    def test_penalty_type_with_no_play(self):
        play = {}
        assert is_penalty_play(play, "offensive holding, no play", "penalty") is True

    def test_not_penalty_play(self):
        play = {}
        assert is_penalty_play(play, "pass complete for 10 yards", "pass") is False

    def test_penalty_without_no_play(self):
        # Declined penalties don't nullify the play
        play = {"penalty": {"yards": 10}}
        assert is_penalty_play(play, "pass complete, penalty declined", "pass") is False


# =============================================================================
# is_spike_or_kneel tests
# =============================================================================
class TestIsSpikeOrKneel:
    def test_spike_in_text(self):
        assert is_spike_or_kneel("qb spike", "pass") is True

    def test_spike_in_type(self):
        assert is_spike_or_kneel("clock stop", "spike") is True

    def test_kneel_in_text(self):
        assert is_spike_or_kneel("quarterback kneel", "rush") is True

    def test_qb_kneel_variant(self):
        assert is_spike_or_kneel("qb kneel for -1 yards", "rush") is True

    def test_kneel_in_type(self):
        assert is_spike_or_kneel("runs for -1", "kneel") is True

    def test_normal_play(self):
        assert is_spike_or_kneel("pass complete for 15 yards", "pass") is False
        assert is_spike_or_kneel("run up the middle", "rush") is False


# =============================================================================
# is_special_teams_play tests
# =============================================================================
class TestIsSpecialTeamsPlay:
    def test_punt(self):
        assert is_special_teams_play("punt for 45 yards", "punt") is True

    def test_kickoff(self):
        assert is_special_teams_play("kickoff", "kickoff") is True

    def test_field_goal(self):
        assert is_special_teams_play("field goal good", "field goal") is True

    def test_extra_point(self):
        assert is_special_teams_play("extra point good", "extra point") is True

    def test_onside_kick(self):
        assert is_special_teams_play("onside kick", "kickoff") is True

    def test_touchdown_excluded(self):
        # TDs should NOT be classified as special teams (to not exclude offensive TDs)
        assert is_special_teams_play("touchdown pass", "pass") is False
        assert is_special_teams_play("pass touchdown", "touchdown") is False

    def test_normal_offensive_play(self):
        assert is_special_teams_play("pass complete", "pass") is False
        assert is_special_teams_play("run for 5", "rush") is False


# =============================================================================
# is_nullified_play tests
# =============================================================================
class TestIsNullifiedPlay:
    def test_nullified(self):
        assert is_nullified_play("play nullified by penalty") is True

    def test_no_play(self):
        assert is_nullified_play("penalty on offense, no play") is True

    def test_normal_play(self):
        assert is_nullified_play("pass complete for 10 yards") is False

    def test_expects_lowercase_input(self):
        # Function expects caller to lowercase the input (per naming convention text_lower)
        assert is_nullified_play("nullified") is True
        assert is_nullified_play("no play") is True
        # Uppercase would not match (by design - caller should lowercase)
        assert is_nullified_play("NULLIFIED") is False


# =============================================================================
# classify_offense_play tests
# =============================================================================
class TestClassifyOffensePlay:
    def test_pass_play(self):
        play = {
            "text": "Pass complete for 15 yards",
            "type": {"text": "Pass"}
        }
        is_off, is_run, is_pass = classify_offense_play(play)
        assert is_off is True
        assert is_run is False
        assert is_pass is True

    def test_run_play_basic(self):
        play = {
            "text": "Rush for 5 yards",
            "type": {"text": "Rush"}
        }
        is_off, is_run, is_pass = classify_offense_play(play)
        assert is_off is True
        assert is_run is True
        assert is_pass is False

    def test_run_play_patterns(self):
        patterns = [
            "runs up the middle for 3",
            "around left end for 8",
            "right tackle for 2",
            "left guard for 4"
        ]
        for pattern in patterns:
            play = {"text": pattern, "type": {"text": "Rush"}}
            is_off, is_run, _ = classify_offense_play(play)
            assert is_off is True, f"Failed for pattern: {pattern}"
            assert is_run is True, f"Failed for pattern: {pattern}"

    def test_sack_is_pass(self):
        play = {
            "text": "Sacked for -8 yards",
            "type": {"text": "Sack"}
        }
        is_off, is_run, is_pass = classify_offense_play(play)
        assert is_off is True
        assert is_run is False
        assert is_pass is True

    def test_scramble_is_pass(self):
        play = {
            "text": "Scramble for 12 yards",
            "type": {"text": "Scramble"},
            "statistics": [{"type": {"abbreviation": "rush"}}]
        }
        is_off, is_run, is_pass = classify_offense_play(play)
        assert is_off is True
        assert is_run is False
        assert is_pass is True

    def test_kickoff_return_excluded(self):
        play = {
            "text": "Kickoff return for touchdown",
            "type": {"text": "Kickoff Return"}
        }
        is_off, is_run, is_pass = classify_offense_play(play)
        assert is_off is False

    def test_punt_return_excluded(self):
        play = {
            "text": "Punt return for 30 yards",
            "type": {"text": "Punt Return"}
        }
        is_off, is_run, is_pass = classify_offense_play(play)
        assert is_off is False

    def test_penalty_excluded(self):
        play = {
            "text": "Penalty on offense, no play",
            "type": {"text": "Penalty"},
            "penalty": {"yards": 10}
        }
        is_off, is_run, is_pass = classify_offense_play(play)
        assert is_off is False

    def test_spike_excluded(self):
        play = {
            "text": "QB Spike",
            "type": {"text": "Spike"}
        }
        is_off, is_run, is_pass = classify_offense_play(play)
        assert is_off is False


# =============================================================================
# is_competitive_play tests
# =============================================================================
class TestIsCompetitivePlay:
    def test_uses_start_probabilities_when_competitive(self):
        # If start-of-play is competitive, the play is competitive even if end-of-play is not.
        prob_map = {"1": {"homeWinPercentage": 0.99, "awayWinPercentage": 0.01}}
        play = {"id": "1", "period": {"number": 4}}
        # Start probs say competitive, map says not
        assert is_competitive_play(play, prob_map, wp_threshold=0.975,
                                   start_home_wp=0.5, start_away_wp=0.5) is True

    def test_overtime_always_competitive(self):
        prob_map = {"1": {"homeWinPercentage": 0.99, "awayWinPercentage": 0.01}}
        play = {"id": "1", "period": {"number": 5}}
        assert is_competitive_play(play, prob_map, wp_threshold=0.5) is True

    def test_threshold_boundary_home(self):
        prob_map = {}
        play = {"id": "1", "period": {"number": 4}}
        # At threshold
        assert is_competitive_play(play, prob_map, wp_threshold=0.975,
                                   start_home_wp=0.975, start_away_wp=0.025) is False
        # Below threshold
        assert is_competitive_play(play, prob_map, wp_threshold=0.975,
                                   start_home_wp=0.974, start_away_wp=0.026) is True

    def test_threshold_boundary_away(self):
        prob_map = {}
        play = {"id": "1", "period": {"number": 4}}
        # At threshold for away
        assert is_competitive_play(play, prob_map, wp_threshold=0.975,
                                   start_home_wp=0.025, start_away_wp=0.975) is False

    def test_missing_probability_data_defaults_competitive(self):
        prob_map = {}
        play = {"id": "999", "period": {"number": 2}}
        # No map entry, no start probs -> assume competitive
        assert is_competitive_play(play, prob_map, wp_threshold=0.5) is True

    def test_fallback_to_probability_map(self):
        # When no start probs provided, use probability_map
        prob_map = {"1": {"homeWinPercentage": 0.6, "awayWinPercentage": 0.4}}
        play = {"id": "1", "period": {"number": 2}}
        assert is_competitive_play(play, prob_map, wp_threshold=0.975) is True

    def test_game_changing_play_with_start_probs(self):
        # Rivers interception scenario: start was competitive, end is not
        prob_map = {"1": {"homeWinPercentage": 0.994, "awayWinPercentage": 0.006}}
        play = {"id": "1", "period": {"number": 4}}
        # Start probs were competitive (IND 14.3%, SEA 85.7%)
        assert is_competitive_play(play, prob_map, wp_threshold=0.975,
                                   start_home_wp=0.857, start_away_wp=0.143) is True

    def test_end_of_play_can_make_competitive(self):
        # Start was non-competitive, but end becomes competitive -> treat as competitive.
        prob_map = {"1": {"homeWinPercentage": 0.90, "awayWinPercentage": 0.10}}
        play = {"id": "1", "period": {"number": 4}}
        assert is_competitive_play(play, prob_map, wp_threshold=0.975,
                                   start_home_wp=0.982, start_away_wp=0.018) is True

    def test_noncompetitive_at_start_and_end(self):
        prob_map = {"1": {"homeWinPercentage": 0.985, "awayWinPercentage": 0.015}}
        play = {"id": "1", "period": {"number": 4}}
        assert is_competitive_play(play, prob_map, wp_threshold=0.975,
                                   start_home_wp=0.982, start_away_wp=0.018) is False


# =============================================================================
# process_game_stats integration tests
# =============================================================================
class TestProcessGameStats:
    def test_returns_list_and_dict(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {
                "competitions": [
                    {"competitors": [{"id": "1", "score": "7"}, {"id": "2", "score": "3"}]}
                ]
            },
            "drives": {"previous": []},
            "scoringPlays": [],
        }
        rows, details = process_game_stats(sample, expanded=True)
        assert isinstance(rows, list)
        assert len(rows) == 2
        assert isinstance(details, dict)

    def test_turnovers_tracked_correctly(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {
                "competitions": [
                    {"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}
                ]
            },
            "drives": {
                "previous": [
                    {
                        "team": {"id": "1"},
                        "plays": [
                            {
                                "text": "Pass INTERCEPTED by defender",
                                "type": {"text": "Interception"},
                                "start": {"team": {"id": "1"}},
                                "end": {"team": {"id": "2"}},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            }
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }
        rows, details = process_game_stats(sample, expanded=True)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["AAA"]["Turnovers"] == 1
        assert len(details["1"]["Turnovers"]) == 1

    def test_fumble_turnover_with_replay_reversal_counts(self):
        text = (
            "Fumble Recovery (Opponent): (Shotgun) S.Darnold pass short middle to C.Kupp to LA 17 "
            "for 17 yards (K.Curl). FUMBLES (K.Curl), RECOVERED by LA-C.Durant at LA 1."
            "The Replay Official reviewed the touchback ruling, and the play was REVERSED."
            "(Shotgun) S.Darnold pass short middle to C.Kupp to LA 17 for 17 yards (K.Curl). "
            "FUMBLES (K.Curl), RECOVERED by LA-C.Durant at LA 0. Touchback."
        )
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "SEA"}},
                    {"team": {"id": "2", "abbreviation": "LAR"}},
                ]
            },
            "header": {
                "competitions": [
                    {"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}
                ]
            },
            "drives": {
                "previous": [
                    {
                        "team": {"id": "1"},
                        "plays": [
                            {
                                "id": "1",
                                "text": text,
                                "type": {"text": "Pass"},
                                "start": {"team": {"id": "1"}},
                                "end": {"team": {"id": "2"}},
                                "team": {"abbreviation": "SEA", "id": "1"},
                            }
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }
        rows, details = process_game_stats(sample, expanded=True)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["SEA"]["Turnovers"] == 1
        assert len(details["1"]["Turnovers"]) == 1
        assert details["1"]["Turnovers"][0]["reason"] == "fumble"

    def test_drive_starts_included_with_start_position_and_preceding_play_context(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {
                "competitions": [
                    {
                        "competitors": [
                            {"id": "1", "score": "0", "homeAway": "home"},
                            {"id": "2", "score": "0", "homeAway": "away"},
                        ]
                    }
                ]
            },
            "drives": {
                "previous": [
                    {
                        "team": {"id": "1"},
                        "start": {"yardsToEndzone": 75, "yardLine": "AAA 25"},
                        "plays": [
                            {
                                "id": "k1",
                                "text": "Kicker kicks 65 yards to BBB 0. Return to BBB 25.",
                                "type": {"text": "Kickoff"},
                                "start": {"team": {"id": "1"}, "down": 0, "distance": 0, "yardsToEndzone": 75},
                                "end": {"team": {"id": "1"}},
                                "period": {"number": 1},
                                "clock": {"displayValue": "15:00"},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            },
                            {
                                "id": "p1",
                                "text": "A punt 45 yards",
                                "type": {"text": "Punt"},
                                "start": {"team": {"id": "1"}, "down": 4, "distance": 10},
                                "end": {"team": {"id": "2"}},
                                "period": {"number": 1},
                                "clock": {"displayValue": "14:20"},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            },
                        ],
                    },
                    {
                        "team": {"id": "2"},
                        "start": {"yardsToEndzone": 60, "yardLine": "BBB 40"},
                        "plays": [
                            {
                                "id": "r1",
                                "text": "Run for 5 yards",
                                "type": {"text": "Rush"},
                                "statYardage": 5,
                                "start": {"team": {"id": "2"}, "down": 1, "distance": 10, "yardsToEndzone": 60},
                                "end": {"team": {"id": "2"}},
                                "period": {"number": 1},
                                "clock": {"displayValue": "14:10"},
                                "team": {"abbreviation": "BBB", "id": "2"},
                            }
                        ],
                    },
                ]
            },
            "scoringPlays": [],
        }
        _rows, details = process_game_stats(sample, expanded=True)
        assert len(details["1"]["Drive Starts"]) == 1
        assert details["1"]["Drive Starts"][0]["start_pos"] == "AAA 25"
        assert "kick" in (details["1"]["Drive Starts"][0]["text"] or "").lower()

        assert len(details["2"]["Drive Starts"]) == 1
        assert details["2"]["Drive Starts"][0]["start_pos"] == "BBB 40"
        assert "punt" in (details["2"]["Drive Starts"][0]["text"] or "").lower()
        assert details["2"]["Drive Starts"][0]["clock"] == "14:10"

    def test_interception_reversed_to_incompletion_not_counted_as_turnover(self):
        text = (
            "(Shotgun) QB pass intended for WR INTERCEPTED by BBB-Defender at AAA 40. "
            "Return to AAA 40 for no gain. "
            "The Replay Official reviewed the interception ruling, and the play was REVERSED."
            "(Shotgun) QB pass incomplete short middle to WR."
        )
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {
                "competitions": [
                    {"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}
                ]
            },
            "drives": {
                "previous": [
                    {
                        "team": {"id": "1"},
                        "plays": [
                            {
                                "id": "1",
                                "text": text,
                                "type": {"text": "Pass Incompletion"},
                                "start": {"team": {"id": "1"}},
                                "end": {"team": {"id": "1"}},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            }
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }
        rows, details = process_game_stats(sample, expanded=True)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["AAA"]["Turnovers"] == 0
        assert by_team["BBB"]["Turnovers"] == 0
        assert details["1"]["Turnovers"] == []
        assert details["2"]["Turnovers"] == []

    def test_two_point_conversion_interception_not_counted_as_turnover(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {
                "competitions": [
                    {"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}
                ]
            },
            "drives": {
                "previous": [
                    {
                        "team": {"id": "1"},
                        "plays": [
                            {
                                "id": "1",
                                "text": "T.Shough pass to D.Vele is intercepted. ATTEMPT FAILS. TWO-POINT CONVERSION ATTEMPT.",
                                "type": {"text": "Pass"},
                                "start": {"team": {"id": "1"}},
                                "end": {"team": {"id": "2"}},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            }
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }
        rows, details = process_game_stats(sample, expanded=True)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["AAA"]["Turnovers"] == 0
        assert details["1"]["Turnovers"] == []

    def test_onside_kick_recovered_by_kicking_team_charges_receiving_turnover(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {
                "competitions": [
                    {"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}
                ]
            },
            "drives": {
                "previous": [
                    {
                        # On kickoffs, drives are typically attributed to the receiving team.
                        "team": {"id": "2"},
                        "plays": [
                            {
                                "id": "1",
                                "text": "Onside kick recovered by AAA at BBB 45.",
                                "type": {"text": "Kickoff"},
                                "start": {"team": {"id": "1"}},
                                "end": {"team": {"id": "1"}},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            }
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }
        rows, details = process_game_stats(sample, expanded=True)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["BBB"]["Turnovers"] == 1
        assert by_team["AAA"]["Turnovers"] == 0
        assert len(details["2"]["Turnovers"]) == 1
        assert details["2"]["Turnovers"][0]["reason"] == "onside_kick_lost"

    def test_kickoff_return_fumble_recovered_by_kicking_team_charges_receiving_turnover(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {
                "competitions": [
                    {"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}
                ]
            },
            "drives": {
                "previous": [
                    {
                        # Kickoff drive attributed to the receiving team.
                        "team": {"id": "2"},
                        "plays": [
                            {
                                "id": "1",
                                "text": "A.AAA kicks 65 yards to BBB 0. Returner to BBB 25. FUMBLES, RECOVERED by AAA-A.AAA at BBB 25.",
                                "type": {"text": "Kickoff"},
                                "start": {"team": {"id": "1"}},
                                "end": {"team": {"id": "1"}},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            }
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }
        rows, details = process_game_stats(sample, expanded=True)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["BBB"]["Turnovers"] == 1
        assert by_team["AAA"]["Turnovers"] == 0
        assert len(details["2"]["Turnovers"]) == 1
        assert details["2"]["Turnovers"][0]["reason"] == "fumble"

    def test_punt_return_fumble_recovered_by_return_team_is_not_a_turnover(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {
                "competitions": [
                    {"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}
                ]
            },
            "drives": {
                "previous": [
                    {
                        "team": {"id": "1"},
                        "plays": [
                            {
                                "id": "1",
                                "text": "A.AAA punts 42 yards to BBB 36. Returner to BBB 38 for 2 yards. FUMBLES, and recovers at BBB 39.",
                                "type": {"text": "Punt"},
                                "start": {"team": {"id": "1"}},
                                "end": {"team": {"id": "2"}},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            }
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }
        rows, details = process_game_stats(sample, expanded=True)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["AAA"]["Turnovers"] == 0
        assert by_team["BBB"]["Turnovers"] == 0
        assert details["1"]["Turnovers"] == []
        assert details["2"]["Turnovers"] == []

    def test_interception_return_fumble_lost_counts_as_turnover_for_return_team(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {
                "competitions": [
                    {"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}
                ]
            },
            "drives": {
                "previous": [
                    {
                        "team": {"id": "1"},
                        "plays": [
                            {
                                "id": "1",
                                "text": "QB pass INTERCEPTED by BBB at AAA 30. Return to AAA 20 for 10 yards. FUMBLES, RECOVERED by AAA at AAA 40.",
                                "type": {"text": "Pass"},
                                "start": {"team": {"id": "1"}},
                                "end": {"team": {"id": "1"}},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            }
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }
        rows, details = process_game_stats(sample, expanded=True)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["AAA"]["Turnovers"] == 1
        assert by_team["BBB"]["Turnovers"] == 1
        assert len(details["1"]["Turnovers"]) == 1
        assert details["1"]["Turnovers"][0]["reason"] == "interception"
        assert len(details["2"]["Turnovers"]) == 1
        assert details["2"]["Turnovers"][0]["reason"] == "fumble"

    def test_fumble_recovered_by_own_team_with_different_text_abbr_is_not_a_turnover(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "WSH"}},
                    {"team": {"id": "2", "abbreviation": "DEN"}},
                ]
            },
            "header": {
                "competitions": [
                    {"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}
                ]
            },
            "drives": {
                "previous": [
                    {
                        "team": {"id": "1"},
                        "plays": [
                            {
                                "id": "1",
                                "text": "QB sacked at WSH 41 for -6 yards. FUMBLES, recovered by WAS-Player at WSH 40.",
                                "type": {"text": "Sack"},
                                "start": {"team": {"id": "1"}},
                                "end": {"team": {"id": "1"}},
                                "team": {"abbreviation": "WSH", "id": "1"},
                            }
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }
        rows, details = process_game_stats(sample, expanded=True)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["WSH"]["Turnovers"] == 0
        assert by_team["DEN"]["Turnovers"] == 0
        assert details["1"]["Turnovers"] == []

    def test_intentional_grounding_penalty_does_not_affect_total_yards(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {
                "competitions": [
                    {"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}
                ]
            },
            "drives": {
                "previous": [
                    {
                        "team": {"id": "1"},
                        "plays": [
                            {
                                "id": "1",
                                "text": "(Shotgun) QB pass incomplete. PENALTY on AAA-QB, Intentional Grounding, 17 yards, enforced at AAA 38.",
                                "type": {"text": "Pass Incompletion"},
                                "statYardage": -34,
                                "start": {"team": {"id": "1"}, "yardsToEndzone": 62},
                                "end": {"team": {"id": "1"}, "yardsToEndzone": 79},
                                "penalty": {
                                    "type": {"text": "Intentional Grounding", "slug": "intentional-grounding"},
                                    "yards": 17,
                                    "status": {"text": "Accepted", "slug": "accepted"},
                                },
                                "team": {"abbreviation": "AAA", "id": "1"},
                            }
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }
        rows, _details = process_game_stats(sample, expanded=False)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["AAA"]["Total Yards"] == 0

    def test_total_yards_corrects_accepted_penalty_double_applied_signature(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {
                "competitions": [
                    {"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}
                ]
            },
            "drives": {
                "previous": [
                    {
                        "team": {"id": "1"},
                        "plays": [
                            {
                                "id": "1",
                                "text": "Runner right end for 20 yards. PENALTY on AAA, Offensive Holding, 10 yards, enforced at AAA 40.",
                                "type": {"text": "Rush"},
                                # Observed ESPN bug signature: statYardage == net - penalty.
                                # Here, start_yte=65, end_yte=70 => net=-5; penalty=10 => stat=-15.
                                "statYardage": -15,
                                "start": {"team": {"id": "1"}, "yardsToEndzone": 65, "down": 1, "distance": 10},
                                "end": {"team": {"id": "1"}, "yardsToEndzone": 70},
                                "penalty": {
                                    "type": {"text": "Offensive Holding", "slug": "offensive-holding"},
                                    "yards": 10,
                                    "status": {"text": "Accepted", "slug": "accepted"},
                                },
                                "team": {"abbreviation": "AAA", "id": "1"},
                            }
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }

        rows, details = process_game_stats(sample, expanded=True, wp_threshold=1.0)
        by_team = {row["Team"]: row for row in rows}
        # Corrected yardage should be net + penalty = (-5) + 10 = +5.
        assert by_team["AAA"]["Total Yards"] == 5
        assert len(details["1"]["Total Yards Corrections"]) == 1
        assert details["1"]["Total Yards Corrections"][0]["correctedYards"] == 5

    def test_total_yards_include_kneels_but_ypp_excludes_them(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {"competitions": [{"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}]},
            "drives": {
                "previous": [
                    {
                        "team": {"id": "1"},
                        "plays": [
                            {
                                "id": "1",
                                "text": "QB kneels to AAA 20 for -2 yards.",
                                "type": {"text": "Rush"},
                                "statYardage": -2,
                                "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
                                "end": {"team": {"id": "1"}},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            },
                            {
                                "id": "2",
                                "text": "Run up the middle to AAA 24 for 4 yards.",
                                "type": {"text": "Rush"},
                                "statYardage": 4,
                                "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
                                "end": {"team": {"id": "1"}},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            },
                            {
                                "id": "3",
                                "text": "QB spikes the ball to stop the clock.",
                                "type": {"text": "Spike"},
                                "statYardage": 0,
                                "start": {"team": {"id": "1"}, "down": 2, "distance": 6},
                                "end": {"team": {"id": "1"}},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            },
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }

        rows, _details = process_game_stats(sample, expanded=False, wp_threshold=1.0)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["AAA"]["Total Yards"] == 2
        assert by_team["AAA"]["Yards Per Play"] == 4.0

    def test_fumble_own_recovery_uses_credited_yards_from_text(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {"competitions": [{"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}]},
            "drives": {
                "previous": [
                    {
                        "team": {"id": "1"},
                        "plays": [
                            {
                                "id": "1",
                                "text": "Runner left end to AAA 31 for -3 yards. FUMBLES, recovered by AAA-Player at AAA 25.",
                                "type": {"text": "Rush"},
                                "statYardage": -9,
                                "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
                                "end": {"team": {"id": "1"}},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            }
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }
        rows, _details = process_game_stats(sample, expanded=False, wp_threshold=1.0)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["AAA"]["Turnovers"] == 0
        assert by_team["AAA"]["Total Yards"] == -3
        assert by_team["AAA"]["Yards Per Play"] == -3.0

    def test_fumble_recovery_own_play_type_overrides_bad_end_team_for_turnovers(self):
        sample = {
            "boxscore": {
                "teams": [
                    {"team": {"id": "1", "abbreviation": "AAA"}},
                    {"team": {"id": "2", "abbreviation": "BBB"}},
                ]
            },
            "header": {"competitions": [{"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}]},
            "drives": {
                "previous": [
                    {
                        "team": {"id": "1"},
                        "plays": [
                            {
                                "id": "1",
                                "text": "Direct snap. AAA FUMBLES (Aborted) at BBB 10, recovered by AAA-Player at BBB 11.",
                                "type": {"text": "Fumble Recovery (Own)"},
                                "statYardage": -2,
                                "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
                                # Some ESPN payloads report end.team as the opponent even on own recoveries.
                                "end": {"team": {"id": "2"}},
                                "team": {"abbreviation": "AAA", "id": "1"},
                            }
                        ],
                    }
                ]
            },
            "scoringPlays": [],
        }
        rows, details = process_game_stats(sample, expanded=True, wp_threshold=1.0)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["AAA"]["Turnovers"] == 0
        assert details["1"]["Turnovers"] == []


# =============================================================================
# build_analysis_text tests
# =============================================================================
class TestBuildAnalysisText:
    def test_generates_summary(self):
        payload = {
            "team_meta": [
                {"abbr": "AAA", "homeAway": "away"},
                {"abbr": "BBB", "homeAway": "home"},
            ],
            "summary_table": [
                {"Team": "AAA", "Score": 14},
                {"Team": "BBB", "Score": 7},
            ],
            "advanced_table": [
                {"Team": "AAA", "Explosive Plays": 3, "Yards Per Play": 5.5},
                {"Team": "BBB", "Explosive Plays": 1, "Yards Per Play": 3.2},
            ],
        }
        text = build_analysis_text(payload)
        assert "AAA" in text
        assert "BBB" in text
        assert "14-7" in text or "14" in text

    def test_handles_tie(self):
        payload = {
            "team_meta": [
                {"abbr": "AAA", "homeAway": "away"},
                {"abbr": "BBB", "homeAway": "home"},
            ],
            "summary_table": [
                {"Team": "AAA", "Score": 10},
                {"Team": "BBB", "Score": 10},
            ],
            "advanced_table": [],
        }
        text = build_analysis_text(payload)
        assert "square" in text.lower() or "10-10" in text
