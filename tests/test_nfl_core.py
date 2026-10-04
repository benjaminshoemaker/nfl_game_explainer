"""
Unit tests for api/lib/nfl_core.py - Pure analytics functions.
"""
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from lib.nfl_core import (
    _charged_penalty_yards,
    _split_drives_on_possession_change,
    _enforced_at_yards_to_endzone,
    normalize_position_text,
    yardline_to_coord,
    calculate_success,
    any_stat_contains,
    is_penalty_play,
    is_spike_or_kneel,
    is_special_teams_play,
    is_nullified_play,
    classify_offense_play,
    classify_total_offense_play,
    is_competitive_play,
    process_game_stats,
    reconcile_final_boxscore,
    build_analysis_text,
)


def test_accepted_zero_yard_penalty_uses_its_own_text_not_declined_foul():
    play = {
        "text": "PENALTY on PHI, Defensive Too Many Men on Field, 0 yards, enforced at PHI 1 - No Play."
                "Penalty on PHI-J.Hunt, Defensive Offside, declined.",
        "type": {"text": "Rush"},
    }
    accepted = {"type": {"text": "Defensive Too Many Men on Field"}, "status": {"slug": "accepted"}}
    assert _charged_penalty_yards(accepted, play) == (0, "0 penalty yards stated in ESPN play text")
    different_foul = {"type": {"text": "Defensive Offside"}, "status": {"slug": "accepted"}}
    assert _charged_penalty_yards(different_foul, play) == (None, "Penalty yards unavailable")


@pytest.mark.parametrize("play_abbr, metadata_abbr", [
    ("CLV", "CLE"), ("BLT", "BAL"), ("HST", "HOU"),
    ("ARZ", "ARI"), ("WAS", "WSH"), ("LA", "LAR"),
    ("JAC", "JAX"),
])
def test_enforcement_spot_uses_espn_team_aliases(play_abbr, metadata_abbr):
    assert _enforced_at_yards_to_endzone(
        f"Penalty, enforced at {play_abbr} 23", metadata_abbr
    ) == 77
    assert yardline_to_coord(f"{play_abbr} 23", metadata_abbr) == 23


@pytest.mark.parametrize("play_abbr, metadata_abbr", [
    ("CLV", "CLE"), ("BLT", "BAL"), ("HST", "HOU"),
    ("ARZ", "ARI"), ("WAS", "WSH"), ("LA", "LAR"),
    ("JAC", "JAX"),
])
def test_penalty_attribution_and_drilldown_use_espn_team_aliases(play_abbr, metadata_abbr):
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": metadata_abbr}},
            {"team": {"id": "2", "abbreviation": "OPP"}},
        ]},
        "drives": {"previous": [{"team": {"id": "2"}, "plays": [{
            "id": "penalty", "text": f"PENALTY on {play_abbr}-Player, Holding, 5 yards, enforced at {play_abbr} 30 - No Play.",
            "type": {"text": "Penalty"},
            "start": {"team": {"id": "2"}, "down": 1},
            "end": {"possessionText": f"{play_abbr} 35"},
            "penalty": {"yards": 5, "status": {"slug": "accepted"}},
        }]}]},
    }
    stats, details = process_game_stats(game, expanded=True, penalty_yards_from_plays=True)
    by_team = {row["Team"]: row for row in stats}
    assert by_team[metadata_abbr]["Penalty Yards"] == 5
    assert by_team["OPP"]["Penalty Yards"] == 0
    assert details["1"]["Penalty Yards"][0]["end_pos"] == f"{metadata_abbr} 35"
    assert details["2"]["Penalty Yards"] == []


def test_penalty_enforced_at_midfield_is_parsed():
    assert _enforced_at_yards_to_endzone(
        "PENALTY on PHI, Offensive Holding, 10 yards, enforced at 50.", "PHI"
    ) == 50


def test_unknown_position_team_is_not_labeled_as_opponent():
    assert normalize_position_text('XYZ 20', {'cle': 'CLE', 'car': 'CAR'}) is None


def _turnovers_for_single_play(play, offense_abbr="AAA", defense_abbr="BBB"):
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": offense_abbr}},
            {"team": {"id": "2", "abbreviation": defense_abbr}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [
            {"id": "1", "start": {"team": {"id": "1"}}, **play},
        ]}]},
    }
    rows, _ = process_game_stats(game, expanded=True)
    return {row["Team"]: row["Turnovers"] for row in rows}


def test_official_and_adjusted_yards_per_play_are_distinct():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "AAA"}, "statistics": [
                {"name": "yardsPerPlay", "displayValue": "7.6"},
            ]},
            {"team": {"id": "2", "abbreviation": "BBB"}, "statistics": []},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Rush"}, "text": "Runner up the middle for 5 yards.",
            "statYardage": 5, "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
        }]}]},
    }

    rows, _ = process_game_stats(game, wp_threshold=1.0)
    by_team = {row["Team"]: row for row in rows}
    assert by_team["AAA"]["Official Yards Per Play (Full Game)"] == 7.6
    assert by_team["AAA"]["Adjusted Yards Per Play"] == 5.0
    assert by_team["BBB"]["Official Yards Per Play (Full Game)"] is None
    assert by_team["BBB"]["Adjusted Yards Per Play"] == 0


def test_final_boxscore_reconciliation_preserves_calculated_gaps():
    game = {
        "header": {"competitions": [{"status": {"type": {"state": "post"}}}]},
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "TEN"}, "statistics": [
                {"name": "totalYards", "displayValue": "327"},
                {"name": "turnovers", "displayValue": "2"},
            ]},
            {"team": {"id": "2", "abbreviation": "ARI"}, "statistics": [
                {"name": "totalYards", "displayValue": "360"},
                {"name": "turnovers", "displayValue": "3"},
            ]},
        ]},
    }
    parsed = [
        {"Team": "TEN", "Total Yards": 327, "Turnovers": 1, "Turnover Margin": 1},
        {"Team": "ARI", "Total Yards": 362, "Turnovers": 2, "Turnover Margin": -1},
    ]
    details = {"1": {"Turnovers": []}, "2": {"Turnovers": []}}

    reconciled, gaps = reconcile_final_boxscore(game, parsed, details)
    by_team = {row["Team"]: row for row in reconciled}
    assert by_team["TEN"]["Total Yards"] == 327
    assert by_team["ARI"]["Total Yards"] == 360
    assert by_team["TEN"]["Turnovers"] == 2
    assert by_team["ARI"]["Turnovers"] == 3
    assert by_team["TEN"]["Calculated Turnovers"] == 1
    assert by_team["ARI"]["Calculated Total Yards"] == 362
    assert by_team["TEN"]["Turnover Margin"] == 1
    assert len(gaps) == 2
    assert {gap["team"]: gap["turnovers_gap"] for gap in gaps} == {"TEN": 1, "ARI": 1}
    assert {gap["team"]: gap["yards_gap"] for gap in gaps} == {"TEN": 0, "ARI": -2}
    assert parsed[0]["Turnovers"] == 1  # Keep the parser result for the season audit.


def test_live_game_keeps_play_by_play_totals():
    game = {
        "header": {"competitions": [{"status": {"type": {"state": "in"}}}]},
        "boxscore": {"teams": [{"team": {"id": "1", "abbreviation": "AAA"}, "statistics": [
            {"name": "totalYards", "displayValue": "100"},
            {"name": "turnovers", "displayValue": "2"},
        ]}]},
    }
    parsed = [{"Team": "AAA", "Total Yards": 90, "Turnovers": 1}]
    reconciled, gaps = reconcile_final_boxscore(game, parsed, {})
    assert reconciled == parsed
    assert gaps == []


def test_final_boxscore_flags_missing_plays_even_when_yards_match():
    game = {
        "header": {"competitions": [{"status": {"type": {"state": "post"}}}]},
        "boxscore": {"teams": [{"team": {"id": "1", "abbreviation": "ARI"},
                                "statistics": [
                                    {"name": "totalYards", "displayValue": "253"},
                                    {"name": "turnovers", "displayValue": "1"},
                                    {"name": "totalOffensivePlays", "displayValue": "64"},
                                ]}]},
    }
    parsed = [{"Team": "ARI", "Total Yards": 253, "Turnovers": 1,
               "Calculated Offensive Plays": 59}]
    reconciled, gaps = reconcile_final_boxscore(game, parsed, {"1": {"Turnovers": []}})
    assert reconciled[0]["Official Offensive Plays"] == 64
    assert reconciled[0]["Calculated Offensive Plays"] == 59
    assert gaps == [{"team": "ARI", "yards_gap": 0, "turnovers_gap": 0,
                     "plays_gap": 5}]


@pytest.mark.parametrize("event", ["END QUARTER 1", "Two-Minute Warning"])
def test_period_markers_are_not_offensive_snaps(event):
    play = {"type": {"text": event}, "text": event, "statYardage": 0}
    assert classify_total_offense_play(play) == (False, False, False)


def test_spike_caption_counts_in_official_offensive_play_check():
    play = {"type": {"text": "Pass Incompletion"},
            "text": "J.Goff spiked the ball to stop the clock.", "statYardage": 0}
    assert classify_total_offense_play(play) == (True, False, True)


def test_final_boxscore_reconciliation_preserves_custom_onside_count():
    game = {
        "header": {"competitions": [{"status": {"type": {"state": "post"}}}]},
        "boxscore": {"teams": [{"team": {"id": "1", "abbreviation": "CHI"}, "statistics": [
            {"name": "totalYards", "displayValue": "576"},
            {"name": "turnovers", "displayValue": "0"},
        ]}]},
    }
    rows = [{"Team": "CHI", "Total Yards": 576, "Turnovers": 1}]
    details = {"1": {"Turnovers": [{"reason": "onside_kick_lost"}]}}
    reconciled, gaps = reconcile_final_boxscore(game, rows, details)
    assert reconciled[0]["Turnovers"] == 1
    assert gaps == []


def test_2025_chi_cin_drive_golden_for_efficiency_and_field_position():
    # ESPN game 401772765, Chicago's Q2 12:12 drive: 4, -7, 11 yards, then punt.
    # Hand check: only the 1st-and-10 run succeeds; 8 net yards on 3 snaps;
    # no explosive play; drive begins at Chicago's own 18.
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "3", "abbreviation": "CHI"}},
            {"team": {"id": "4", "abbreviation": "CIN"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "3", "score": "0"}, {"id": "4", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "3"}, "plays": [
            {"id": "4017727651283", "type": {"text": "Rush"},
             "text": "K.Monangai right guard to CHI 22 for 4 yards.", "statYardage": 4,
             "start": {"team": {"id": "3"}, "down": 1, "distance": 10, "yardsToEndzone": 82}},
            {"id": "4017727651312", "type": {"text": "Sack"},
             "text": "C.Williams sacked at CHI 15 for -7 yards.", "statYardage": -7,
             "start": {"team": {"id": "3"}, "down": 2, "distance": 6, "yardsToEndzone": 78}},
            {"id": "4017727651332", "type": {"text": "Pass Reception"},
             "text": "C.Williams pass to C.Loveland to CHI 26 for 11 yards.", "statYardage": 11,
             "start": {"team": {"id": "3"}, "down": 3, "distance": 13, "yardsToEndzone": 85}},
            {"id": "4017727651357", "type": {"text": "Punt"},
             "text": "T.Taylor punts to CIN 5; return to CIN 15.", "statYardage": 10,
             "start": {"team": {"id": "3"}, "down": 4, "distance": 2, "yardsToEndzone": 74}},
        ]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    chi = next(row for row in rows if row["Team"] == "CHI")
    assert chi["Total Yards"] == 8
    assert chi["Adjusted Yards Per Play"] == 2.67
    assert chi["Success Rate"] == 0.333
    assert chi["Explosive Plays"] == 0
    assert chi["Explosive Play Rate"] == 0
    assert chi["Ave Start Field Pos"] == "Own 18"


def test_special_teams_metrics_use_net_punt_yards_and_kickoff_resulting_spot():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "AAA"}},
            {"team": {"id": "2", "abbreviation": "BBB"}},
        ]},
        "drives": {"previous": [{"team": {"id": "2"}, "plays": [
            {"id": "ko", "type": {"text": "Kickoff"},
             "text": "AAA kickoff to BBB 35, Touchback.", "statYardage": 0,
             "start": {"team": {"id": "1"}, "yardLine": 35},
             "end": {"team": {"id": "2"}, "yardsToEndzone": 65}},
            {"id": "punt1", "type": {"text": "Punt"},
             "text": "BBB punts 50 yards to AAA 14. Return to AAA 20 for 6 yards.",
             "statYardage": 6, "start": {"team": {"id": "2"}}},
            {"id": "punt2", "type": {"text": "Punt"},
             "text": "BBB punts 45 yards to AAA 10, out of bounds.",
             "statYardage": 0, "start": {"team": {"id": "2"}}},
        ]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    by_team = {row["Team"]: row for row in rows}

    assert by_team["BBB"]["Net Punting"] == 44.5
    assert by_team["AAA"]["Avg Opponent Kickoff Start"] == "Own 35"
    assert by_team["BBB"]["Avg Opponent Kickoff Start"] == "—"


def test_2025_chi_cin_opening_kickoff_golden_for_non_offensive_points():
    # ESPN game 401772765 opens with a Cincinnati 98-yard kickoff-return TD.
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "3", "abbreviation": "CHI"}},
            {"team": {"id": "4", "abbreviation": "CIN"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "3", "score": "0", "homeAway": "away"},
            {"id": "4", "score": "7", "homeAway": "home"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "4"}, "plays": [{
            "id": "40177276539", "type": {"text": "Kickoff Return Touchdown"},
            "text": "C.Santos kicks to CIN 2. C.Jones for 98 yards, TOUCHDOWN. Extra point is GOOD.",
            "statYardage": 98, "scoringPlay": True,
            "start": {"team": {"id": "3"}}, "end": {"team": {"id": "4"}},
        }]}]},
        "scoringPlays": [{
            "id": "40177276539", "team": {"id": "4"},
            "homeScore": 7, "awayScore": 0,
            "type": {"text": "Kickoff Return Touchdown"},
            "scoringType": {"name": "touchdown"},
            "text": "Charlie Jones 98 Yd Kickoff Return (Evan McPherson Kick)",
        }],
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    by_team = {row["Team"]: row for row in rows}
    assert by_team["CIN"]["Non-Offensive Points"] == 7
    assert by_team["CIN"]["Total Yards"] == 0
    assert by_team["CHI"]["Non-Offensive Points"] == 0


def test_interception_followed_by_fumble_uses_explicit_recovery_team():
    turnovers = _turnovers_for_single_play({
        "type": {"text": "Fumble Recovery (Opponent)"},
        "text": (
            "QB pass INTERCEPTED by BBB-C.Bryant at BBB 32. "
            "C.Bryant FUMBLES, RECOVERED by AAA-T.Benson at BBB 47."
        ),
        "end": {"team": {"id": "1"}},
    })
    assert turnovers == {"AAA": 1, "BBB": 1}


def test_punt_return_fumble_uses_explicit_recovery_team():
    turnovers = _turnovers_for_single_play({
        "type": {"text": "Fumble Recovery (Opponent)"},
        "text": "Punter punts to BBB 2. Returner FUMBLES, RECOVERED by AAA-T.Sieg at BBB 8.",
        "end": {"team": {"id": "1"}},
    })
    assert turnovers == {"AAA": 0, "BBB": 1}


def test_interception_then_two_fumbles_counts_each_possession_loss():
    turnovers = _turnovers_for_single_play({
        "type": {"text": "Fumble Recovery (Opponent)"},
        "text": (
            "QB pass INTERCEPTED by BBB-D.Hand at BBB 17. D.Hand to BBB 24. "
            "FUMBLES, RECOVERED by AAA-J.Hurts at BBB 32. J.Hurts to BBB 33. "
            "FUMBLES, RECOVERED by BBB-T.Dye at BBB 43."
        ),
        "end": {"team": {"id": "2"}},
    })
    assert turnovers == {"AAA": 2, "BBB": 1}


def test_touchdown_followed_by_conversion_text_does_not_erase_fumble():
    turnovers = _turnovers_for_single_play({
        "type": {"text": "Sack Opp Fumble Recovery"},
        "text": (
            "QB sacked, FUMBLES, RECOVERED by BBB-Defender. TOUCHDOWN. "
            "TWO-POINT CONVERSION ATTEMPT. Pass is incomplete."
        ),
        "end": {"team": {"id": "2"}},
    })
    assert turnovers == {"AAA": 1, "BBB": 0}


def test_touchdown_followed_by_failed_conversion_interception_is_not_turnover():
    turnovers = _turnovers_for_single_play({
        "type": {"text": "Rushing Touchdown"},
        "text": (
            "QB scrambles for 2 yards, TOUCHDOWN. TWO-POINT CONVERSION ATTEMPT. "
            "QB pass is intercepted. ATTEMPT FAILS."
        ),
        "end": {"team": {"id": "2"}},
    })
    assert turnovers == {"AAA": 0, "BBB": 0}


def test_nullified_interception_return_touchdown_preserves_interception():
    turnovers = _turnovers_for_single_play({
        "type": {"text": "Pass Interception Return"},
        "text": (
            "QB pass INTERCEPTED by BBB-Defender. Defender for 44 yards, "
            "TOUCHDOWN NULLIFIED by Penalty. Penalty on BBB, 15 yards, enforced at AAA 15."
        ),
        "end": {"team": {"id": "2"}},
    })
    assert turnovers == {"AAA": 1, "BBB": 0}


def test_nullified_offensive_touchdown_does_not_credit_yards():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "AAA"}},
            {"team": {"id": "2", "abbreviation": "BBB"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Rush"}, "statYardage": 2,
            "text": "Runner for 2 yards, TOUCHDOWN NULLIFIED by Penalty.",
            "start": {"team": {"id": "1"}, "yardsToEndzone": 2},
            "end": {"team": {"id": "1"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == 0


def _yards_for_real_play(play, offense="AAA", defense="BBB"):
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": offense}},
            {"team": {"id": "2", "abbreviation": defense}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [play]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    return rows[0]["Total Yards"], rows[0]["Adjusted Yards Per Play"]


def _single_play_with_debug(play, offense="AAA", defense="BBB"):
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": offense}},
            {"team": {"id": "2", "abbreviation": defense}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [play]}]},
    }
    debug = []
    rows, _ = process_game_stats(game, wp_threshold=1.0, debug_rows=debug)
    return rows[0], next(row for row in debug if row.get("kind") == "play")


def test_pick_six_retains_underlying_pass_attempt():
    play = {
        "id": "401772956636", "type": {"text": "Interception Return Touchdown"},
        "text": (
            "(Shotgun) T.Lance pass short middle intended for K.Lambert-Smith "
            "INTERCEPTED by J.McMillian at LAC 45. J.McMillian for 45 yards, "
            "TOUCHDOWN. W.Lutz extra point is GOOD."
        ),
        "statYardage": 45,
        "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
        "end": {"team": {"id": "2"}},
    }
    row, debug = _single_play_with_debug(play, "LAC", "DEN")
    assert row["Turnovers"] == 1
    assert row["Total Yards"] == 0
    assert debug["statDeltas"]["LAC"]["Plays"] == 1
    assert debug["statDeltas"]["LAC"].get("Offensive Yards", 0) == 0
    assert row["Success Rate"] == 0


def test_score_only_interception_caption_still_proves_a_pass_attempt():
    play = {
        "id": "1", "type": {"text": "Interception Return Touchdown"},
        "text": "Defender 40 Yd Interception Return (Kicker Kick)",
        "statYardage": 40,
        "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
        "end": {"team": {"id": "2"}},
    }
    row, debug = _single_play_with_debug(play)
    assert row["Calculated Offensive Plays"] == 1
    assert debug["statDeltas"]["AAA"]["Plays"] == 1
    assert row["Total Yards"] == 0


def test_own_recovered_rushing_fumble_counts_in_adjusted_efficiency():
    play = {
        "id": "4017728331254", "type": {"text": "Fumble Recovery (Own)"},
        "text": "(Shotgun) M.Jones to NO 26 for -5 yards. FUMBLES, and recovers at NO 26.",
        "statYardage": -5,
        "start": {"team": {"id": "1"}, "down": 2, "distance": 9,
                  "yardsToEndzone": 21},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 26},
    }
    row, debug = _single_play_with_debug(play, "SF", "NO")
    assert row["Total Yards"] == -5
    assert row["Adjusted Yards Per Play"] == -5
    assert debug["statDeltas"]["SF"]["Plays"] == 1


def test_opponent_recovered_rushing_fumble_keeps_offensive_snap_and_yards():
    play = {
        "id": "4017729133177", "type": {"text": "Fumble Recovery (Opponent)"},
        "text": "(Shotgun) B.Nix to DEN 35 for -4 yards. FUMBLES, RECOVERED by JAX-E.Ogbah at DEN 34.",
        "statYardage": 0,
        "start": {"team": {"id": "1"}, "down": 2, "distance": 10,
                  "yardsToEndzone": 61},
        "end": {"team": {"id": "2"}, "yardsToEndzone": 34},
    }
    row, debug = _single_play_with_debug(play, "DEN", "JAX")
    assert debug["statDeltas"]["DEN"]["Plays"] == 1
    assert debug["statDeltas"]["DEN"]["Total Offensive Plays"] == 1
    assert row["Total Yards"] == row["Adjusted Yards Per Play"]


def test_score_only_safety_credits_known_yards_but_not_unseen_snap_detail():
    play = {
        "id": "4017728031172", "type": {"text": "Safety"},
        "text": "Jeffery Simmons Safety", "statYardage": -2,
        "start": {"team": {"id": "1"}, "down": 3, "distance": 7},
        "end": {"team": {"id": "2"}},
    }
    row, debug = _single_play_with_debug(play, "KC", "TEN")
    assert row["Total Yards"] == -2
    assert row["Calculated Offensive Plays"] == 0
    assert "Plays" not in debug["statDeltas"].get("KC", {})


def test_between_downs_penalty_does_not_reduce_touchdown_pass_yards():
    # LAC-KC 4017727143594: ESPN statYardage folds the 8-yard penalty
    # into the 23-yard pass, but credits Herbert all 23 passing yards.
    play = {
        "id": "4017727143594", "type": {"text": "Passing Touchdown"},
        "text": "J.Herbert pass to Q.Johnston for 23 yards, TOUCHDOWN."
                "PENALTY on KC-J.Hicks, Face Mask, 8 yards, enforced between downs.",
        "statYardage": 15,
        "penalty": {"yards": 8, "status": {"slug": "accepted"}},
        "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                  "yardsToEndzone": 23},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 0},
    }
    assert _yards_for_real_play(play, "LAC", "KC") == (23, 23)


def test_post_catch_face_mask_keeps_yards_to_enforcement_spot():
    # LAR-NO 4017728741876: 14-yard touchdown was nullified, but the
    # accepted face mask at NO 6 leaves an official eight-yard reception.
    play = {
        "id": "4017728741876", "type": {"text": "Pass Reception"},
        "text": "M.Stafford pass to D.Allen for 14 yards, TOUCHDOWN NULLIFIED by Penalty."
                "PENALTY on LA-D.Allen, Face Mask, 15 yards, enforced at NO 6.",
        "statYardage": -22,
        "penalty": {"yards": 15, "type": {"slug": "face-mask"},
                    "status": {"slug": "accepted"}},
        "start": {"team": {"id": "1"}, "down": 2, "distance": 8,
                  "yardsToEndzone": 14},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 21},
    }
    assert _yards_for_real_play(play, "LAR", "NO") == (8, 8)


@pytest.mark.parametrize("play,offense,defense,expected", [
    ({
        "id": "4017728494113", "type": {"text": "Rush"},
        "text": "J.Taylor left tackle for 53 yards, TOUCHDOWN NULLIFIED by Penalty."
                "PENALTY on IND-A.Mitchell, Offensive Holding, 10 yards, enforced at LA 48.",
        "statYardage": -15,
        "penalty": {"yards": 10, "type": {"slug": "offensive-holding"},
                    "status": {"slug": "accepted"}},
        "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                  "yardsToEndzone": 53},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 58},
    }, "IND", "LAR", 5),
    ({
        "id": "4017729022577", "type": {"text": "Rush"},
        "text": "J.Cook for 24 yards, TOUCHDOWN NULLIFIED by Penalty."
                "PENALTY on BUF-R.Van Demark, Offensive Holding, 10 yards, enforced at CIN 20."
                "The play was REVERSED.J.Cook to CIN 1 for 23 yards. FUMBLES, "
                "ball out of bounds at CIN 1.PENALTY on BUF-R.Van Demark, "
                "Offensive Holding, 10 yards, enforced at CIN 20.",
        "statYardage": -16,
        "penalty": {"yards": 10, "type": {"slug": "offensive-holding"},
                    "status": {"slug": "accepted"}},
        "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                  "yardsToEndzone": 24},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 30},
    }, "BUF", "CIN", 4),
])
def test_nullified_touchdown_retains_yards_before_downfield_holding(
    play, offense, defense, expected
):
    assert _yards_for_real_play(play, offense, defense) == (expected, expected)


@pytest.mark.parametrize("play,offense,defense,expected", [
    ({
        "id": "401772895188", "type": {"text": "Fumble Recovery (Own)"},
        "text": "B.Mayfield sacked at TB 40 for -8 yards. FUMBLES, "
                "recovered by TB-R.White at TB 38. R.White to TB 45 for 7 yards.",
        "statYardage": -3,
        "start": {"team": {"id": "1"}, "down": 1, "distance": 15,
                  "yardsToEndzone": 52},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 55},
    }, "TB", "ARI", -3),
    ({
        "id": "401772854669", "type": {"text": "Sack Opp Fumble Recovery"},
        "text": "J.Goff sacked at CIN 39 for -7 yards. FUMBLES, "
                "touched at CIN 26, RECOVERED by CIN-L.Wilson at CIN 28.",
        "statYardage": 0,
        "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                  "yardsToEndzone": 32},
        "end": {"team": {"id": "2"}, "yardsToEndzone": 28},
    }, "DET", "CIN", 0),
    ({
        "id": "4017728345095", "type": {"text": "Sack"},
        "text": "R.Wilson sacked at NYG 29 for -6 yards. FUMBLES, "
                "ball out of bounds at NYG 21.",
        "statYardage": -14,
        "start": {"team": {"id": "1"}, "down": 2, "distance": 3,
                  "yardsToEndzone": 65},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 79},
    }, "NYG", "DAL", -14),
    ({
        "id": "4017726322513", "type": {"text": "Fumble Recovery (Own)"},
        "text": "C.Wentz sacked at MIN 48 for -8 yards. FUMBLES, "
                "touched at MIN 48, recovered by MIN-J.Oliver at PIT 45.",
        "statYardage": -1,
        "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                  "yardsToEndzone": 44},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 45},
    }, "MIN", "PIT", -8),
])
def test_sack_fumble_yards_follow_final_credited_spot(play, offense, defense, expected):
    assert _yards_for_real_play(play, offense, defense) == (expected, expected)


@pytest.mark.parametrize("play,offense,defense,expected", [
    ({
        "id": "4017727473061", "type": {"text": "Fumble Recovery (Opponent)"},
        "text": "K.Murray FUMBLES (Aborted) at TEN 25, "
                "RECOVERED by TEN-D.Jones at TEN 24. D.Jones to TEN 26 for 2 yards.",
        "statYardage": 2,
        "start": {"team": {"id": "1"}, "down": 3, "distance": 12,
                  "yardsToEndzone": 20},
        "end": {"team": {"id": "2"}, "yardsToEndzone": 26},
    }, "ARI", "TEN", 0),
    ({
        "id": "4017727253099", "type": {"text": "Fumble Recovery (Own)"},
        "text": "T.Lawrence FUMBLES (Aborted) at JAX 33, and recovers at JAX 32. "
                "T.Lawrence to JAX 35 for 3 yards.",
        "statYardage": 1,
        "start": {"team": {"id": "1"}, "down": 2, "distance": 1,
                  "yardsToEndzone": 66},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 65},
    }, "JAX", "CIN", 1),
])
def test_aborted_snap_excludes_opponent_return_but_keeps_own_advances(
    play, offense, defense, expected
):
    assert _yards_for_real_play(play, offense, defense) == (expected, expected)


def test_aborted_center_snap_recovered_by_third_teammate_is_fumble_yardage():
    play = {
        "id": "4017726343907", "type": {"text": "Fumble Recovery (Own)"},
        "text": "J.Fields Aborted. J.Myers FUMBLES at NYJ 38, "
                "recovered by NYJ-B.Hall at NYJ 38. B.Hall to 50 for 12 yards.",
        "statYardage": 7,
        "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                  "yardsToEndzone": 57},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 50},
    }
    assert _yards_for_real_play(play, "NYJ", "DEN") == (0, 0)


def test_aborted_center_snap_recovered_by_intended_handler_keeps_advance():
    play = {
        "id": "401772756641", "type": {"text": "Fumble Recovery (Own)"},
        "text": "D.Jones Aborted. T.Bortolini FUMBLES at IND 32, "
                "recovered by IND-D.Jones at IND 30. D.Jones to IND 39 for 9 yards.",
        "statYardage": 3,
        "start": {"team": {"id": "1"}, "down": 3, "distance": 4,
                  "yardsToEndzone": 64},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 61},
    }
    assert _yards_for_real_play(play, "IND", "LAC") == (3, 3)


def test_possession_change_inside_espn_drive_attributes_later_plays_to_new_offense():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "CAR"}},
            {"team": {"id": "2", "abbreviation": "NO"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{
            "team": {"id": "1"}, "start": {"yardsToEndzone": 30},
            "plays": [
                {"id": "1", "type": {"text": "Fumble Recovery (Opponent)"},
                 "text": "QB FUMBLES, RECOVERED by NO-Defender.",
                 "start": {"team": {"id": "1"}, "yardsToEndzone": 30},
                 "end": {"team": {"id": "2"}}, "statYardage": 0},
                {"id": "2", "type": {"text": "Rush"},
                 "text": "Runner right tackle for 8 yards.",
                 "start": {"team": {"id": "2"}, "down": 1, "distance": 10,
                           "yardsToEndzone": 83, "possessionText": "NO 17"},
                 "end": {"team": {"id": "2"}}, "statYardage": 8},
                {"id": "3", "type": {"text": "Pass Reception"},
                 "text": "QB pass to receiver for 35 yards.",
                 "start": {"team": {"id": "2"}, "down": 2, "distance": 2,
                           "yardsToEndzone": 75, "possessionText": "NO 25"},
                 "end": {"team": {"id": "2"}}, "statYardage": 35},
            ],
        }]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    by_team = {row["Team"]: row for row in rows}
    assert by_team["CAR"]["Total Yards"] == 0
    assert by_team["NO"]["Total Yards"] == 43


def test_mislabeled_drive_with_first_play_by_other_team_uses_play_possession():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "CAR"}},
            {"team": {"id": "2", "abbreviation": "NO"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{
            "team": {"id": "1"}, "start": {"yardsToEndzone": 83},
            "plays": [{
                "id": "1", "type": {"text": "Rush"}, "statYardage": 8,
                "text": "Runner right tackle for 8 yards.",
                "start": {"team": {"id": "2"}, "down": 1, "distance": 10,
                          "yardsToEndzone": 83, "possessionText": "NO 17"},
                "end": {"team": {"id": "2"}},
            }],
        }]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    by_team = {row["Team"]: row for row in rows}
    assert by_team["CAR"]["Total Yards"] == 0
    assert by_team["NO"]["Total Yards"] == 8


def test_average_start_field_position_uses_receiving_team_drive_spot_after_kickoff():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "SEA"}},
            {"team": {"id": "2", "abbreviation": "WSH"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{
            "team": {"id": "1"},
            "start": {"yardLine": "SEA 37"},
            "plays": [{
                "id": "kickoff", "type": {"text": "Kickoff"},
                "text": "WSH kicks from SEA 35; return to SEA 37.",
                "start": {"team": {"id": "2"}, "down": 0, "yardsToEndzone": 65},
                "end": {"team": {"id": "1"}},
            }, {
                "id": "rush", "type": {"text": "Rush"}, "statYardage": 4,
                "text": "Runner for 4 yards.",
                "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                          "yardsToEndzone": 63, "possessionText": "SEA 37"},
                "end": {"team": {"id": "1"}},
            }],
        }]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    sea = next(row for row in rows if row["Team"] == "SEA")
    assert sea["Ave Start Field Pos"] == "Own 37"
    assert sea["Drives"] == 1

    game["drives"]["previous"][0]["start"]["yardLine"] = "WSH 32"
    game["drives"]["previous"][0]["plays"][1]["start"].update({
        "yardsToEndzone": 32, "possessionText": "WSH 32",
    })
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    sea = next(row for row in rows if row["Team"] == "SEA")
    assert sea["Ave Start Field Pos"] == "Opp 32"


def test_timeout_appended_to_previous_drive_does_not_create_duplicate_drive():
    drives = [{
        "team": {"id": "1"},
        "plays": [
            {"type": {"text": "Punt"}, "start": {"team": {"id": "1"}, "down": 4}},
            {"type": {"text": "Official Timeout"}, "text": "Official Timeout",
             "start": {"team": {"id": "2"}, "down": 1}},
        ],
    }, {
        "team": {"id": "2"},
        "plays": [{"type": {"text": "Rush"},
                   "start": {"team": {"id": "2"}, "down": 1}}],
    }]

    normalized = _split_drives_on_possession_change(drives)
    assert len(normalized) == 2
    assert [drive["plays"][0]["type"]["text"] for drive in normalized] == ["Punt", "Rush"]


def test_score_only_defensive_fumble_return_does_not_credit_offensive_yards():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "CLE"}},
            {"team": {"id": "2", "abbreviation": "BAL"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "7"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Sack Opp Fumble Recovery"},
            "text": "Roquan Smith 63 Yd Fumble Return (Tyler Loop Kick)",
            "statYardage": 63,
            "start": {"team": {"id": "1"}, "down": 2, "yardsToEndzone": 60},
            "end": {"team": {"id": "2"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == 0


@pytest.mark.parametrize("play,offense,defense,expected", [
    ({
        "id": "4017727744083", "type": {"text": "Fumble Return Touchdown"},
        "text": "J.Flacco pass short right to N.Fant to CIN 33 for 5 yards. "
                "FUMBLES, RECOVERED by PIT-J.Pierre at CIN 34. "
                "J.Pierre for 34 yards, TOUCHDOWN.",
        "statYardage": 34,
        "start": {"team": {"id": "1"}, "down": 2, "distance": 8,
                  "yardsToEndzone": 72},
        "end": {"team": {"id": "2"}},
    }, "CIN", "PIT", 5),
    ({
        "id": "4017729624468", "type": {"text": "Fumble Return Touchdown"},
        "text": "R.Leonard pass to J.Downs to IND 29 for 4 yards. "
                "Lateral to M.Pittman to IND 20 for -9 yards. "
                "Lateral to R.Leonard to IND 21 for 1 yard. FUMBLES, "
                "touched at IND 17, RECOVERED by HST-T.Togiai at IND 17. "
                "T.Togiai for 17 yards, TOUCHDOWN.",
        "statYardage": 17,
        "start": {"team": {"id": "1"}, "down": 3, "distance": 10,
                  "yardsToEndzone": 75},
        "end": {"team": {"id": "2"}},
    }, "IND", "HOU", -8),
])
def test_detailed_fumble_return_score_preserves_prior_offensive_yards(
    play, offense, defense, expected
):
    assert _yards_for_real_play(play, offense, defense)[0] == expected


def test_blocked_field_goal_return_touchdown_is_not_offensive_yardage():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "ATL"}},
            {"team": {"id": "2", "abbreviation": "LAR"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "7"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Blocked Field Goal Touchdown"},
            "text": "Jared Verse 76 Yd Return of Blocked Field Goal (Harrison Mevis Kick)",
            "statYardage": 76,
            "start": {"team": {"id": "1"}, "down": 4, "yardsToEndzone": 24},
            "end": {"team": {"id": "2"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == 0


def test_blocked_field_goal_with_touchdown_in_text_is_still_special_teams():
    assert is_special_teams_play(
        "Field goal is BLOCKED, recovered and returned for a TOUCHDOWN",
        "Blocked Field Goal",
    )


def test_incomplete_pass_does_not_credit_penalty_yardage_as_offense():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "MIN"}},
            {"team": {"id": "2", "abbreviation": "BAL"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Pass Incompletion"},
            "text": (
                "QB pass incomplete short middle. PENALTY on MIN, "
                "Illegal Blindside Block, 15 yards, enforced at BAL 46."
            ),
            "statYardage": -30,
            "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                      "yardsToEndzone": 46},
            "end": {"team": {"id": "1"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == 0
    assert rows[0]["Adjusted Yards Per Play"] == 0


def test_aborted_punt_snap_advanced_for_yards_counts_as_rush():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "NYJ"}},
            {"team": {"id": "2", "abbreviation": "MIA"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Fumble Recovery (Own)"},
            "text": (
                "(Punt formation) M.Moore FUMBLES (Aborted) at NYJ 24, "
                "recovered by NYJ-I.Davis. I.Davis pushed ob at NYJ 44 for 20 yards."
            ),
            "statYardage": 19,
            "start": {"team": {"id": "1"}, "down": 4, "distance": 10,
                      "yardsToEndzone": 76},
            "end": {"team": {"id": "1"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == 19
    assert rows[0]["Adjusted Yards Per Play"] == 19


def test_aborted_snap_loss_is_fumble_yardage_not_rushing_yardage():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "MIN"}},
            {"team": {"id": "2", "abbreviation": "PHI"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [
            {"id": "1", "type": {"text": "Fumble Recovery (Own)"},
             "text": "C.Wentz Aborted. B.Brandel FUMBLES at PHI 25, recovered by MIN-C.Wentz at PHI 41.",
             "statYardage": -22,
             "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
             "end": {"team": {"id": "1"}}},
            {"id": "2", "type": {"text": "Rush"},
             "text": "C.Wentz FUMBLES (Aborted) at MIN 9, ball out of bounds at MIN 9.",
             "statYardage": -8,
             "start": {"team": {"id": "1"}, "down": 2, "distance": 10},
             "end": {"team": {"id": "1"}}},
        ]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == 0
    assert rows[0]["Adjusted Yards Per Play"] == 0


def test_own_fumble_followed_by_completed_pass_uses_final_offensive_yardage():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "MIA"}},
            {"team": {"id": "2", "abbreviation": "NO"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Fumble Recovery (Own)"},
            "text": (
                "QB to MIA 47 for -5 yards. FUMBLES, and recovers at MIA 47. "
                "QB pass short middle to WR to NO 29 for 19 yards."
            ),
            "statYardage": 19,
            "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                      "yardsToEndzone": 48},
            "end": {"team": {"id": "1"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == 19


def test_teammate_recovers_fumble_then_completes_pass_without_sack_yardage():
    # KC-LAC 4017727141394: the recovery moved four yards backward, but the
    # ensuing completion and official team net-passing total credit zero.
    play = {
        "id": "4017727141394", "type": {"text": "Fumble Recovery (Own)"},
        "text": "C.Humphrey to LAC 32 for no gain. FUMBLES, recovered by "
                "KC-P.Mahomes at LAC 36. P.Mahomes pass short right to "
                "M.Brown pushed ob at LAC 32 for no gain.",
        "statYardage": 0,
        "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                  "yardsToEndzone": 32},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 32},
    }
    assert _yards_for_real_play(play, "KC", "LAC") == (0, 0)


def test_forward_pass_penalty_after_fumble_is_not_a_new_completion():
    play = {
        "id": "4017727312050", "type": {"text": "Fumble Recovery (Opponent)"},
        "text": "J.Browning pass to J.Chase to CIN 47 for 15 yards. FUMBLES, "
                "RECOVERED by MIN-J.Okudah at MIN 48. "
                "Penalty on CIN-J.Browning, Illegal Forward Pass, declined.",
        "statYardage": 0,
        "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                  "yardsToEndzone": 68},
        "end": {"team": {"id": "2"}},
    }
    assert _yards_for_real_play(play, "CIN", "MIN")[0] == 15


def test_conversion_pass_after_defensive_touchdown_does_not_erase_sack_loss():
    play = {
        "id": "4017728262987", "type": {"text": "Sack Opp Fumble Recovery"},
        "text": "S.Darnold sacked at SEA -5 for -12 yards. FUMBLES, "
                "RECOVERED by HST-W.Anderson at SEA -5. TOUCHDOWN. "
                "TWO-POINT CONVERSION ATTEMPT. C.Stroud pass to D.Schultz is incomplete.",
        "statYardage": 0,
        "start": {"team": {"id": "1"}, "down": 2, "distance": 10,
                  "yardsToEndzone": 93},
        "end": {"team": {"id": "2"}},
    }
    assert _yards_for_real_play(play, "SEA", "HOU")[0] == -7


def test_end_zone_sack_loss_stops_at_goal_line():
    # SEA-HOU 4017728262987: the ball ended five yards into the end zone,
    # but ESPN credits a seven-yard sack from the SEA 7.
    play = {
        "id": "4017728262987", "type": {"text": "Sack Opp Fumble Recovery"},
        "text": "S.Darnold sacked at SEA -5 for -12 yards. FUMBLES, "
                "RECOVERED by HST-W.Anderson at SEA -5. TOUCHDOWN.",
        "statYardage": 0,
        "start": {"team": {"id": "1"}, "down": 3, "distance": 7,
                  "yardsToEndzone": 93},
        "end": {"team": {"id": "2"}, "yardsToEndzone": 0},
    }
    assert _yards_for_real_play(play, "SEA", "HOU")[0] == -7


def test_later_sack_after_bad_snap_uses_sack_yards():
    play = {
        "id": "4017728111356", "type": {"text": "Fumble Recovery (Own)"},
        "text": "J.Meredith to LAC 18 for -5 yards. FUMBLES, recovered by "
                "LV-G.Smith at LAC 19. G.Smith sacked at LAC 22 for -9 yards.",
        "statYardage": -9,
        "start": {"team": {"id": "1"}, "down": 3, "distance": 6,
                  "yardsToEndzone": 13},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 22},
    }
    assert _yards_for_real_play(play, "LV", "LAC")[0] == -9


def test_later_sack_fumble_first_touch_reduces_loss():
    play = {
        "id": "4017729521501", "type": {"text": "Fumble Recovery (Own)"},
        "text": "S.Darnold to SEA 40 for -6 yards. FUMBLES, and recovers at SEA 39. "
                "S.Darnold sacked at SEA 39 for -7 yards. FUMBLES, "
                "touched at SEA 41, RECOVERED by CAR-A.Robinson at SEA 40.",
        "statYardage": 3,
        "start": {"team": {"id": "1"}, "down": 3, "distance": 5,
                  "yardsToEndzone": 54},
        "end": {"team": {"id": "2"}, "yardsToEndzone": 40},
    }
    assert _yards_for_real_play(play, "SEA", "CAR")[0] == -5


def test_scramble_before_illegal_forward_pass_keeps_rushing_yards():
    play = {
        "id": "4017727252021", "type": {"text": "Rush"},
        "text": "T.Lawrence scrambles left end to CIN 19 for 3 yards. "
                "T.Lawrence pass incomplete deep left. PENALTY on JAX-T.Lawrence, "
                "Illegal Forward Pass, 5 yards, enforced at CIN 19.",
        "statYardage": -7,
        "penalty": {"yards": 5, "type": {"slug": "illegal-forward-pass"},
                    "status": {"slug": "accepted"}},
        "start": {"team": {"id": "1"}, "down": 3, "distance": 10,
                  "yardsToEndzone": 22},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 24},
    }
    assert _yards_for_real_play(play, "JAX", "CIN") == (3, 3)


def test_own_fumble_followed_by_incomplete_pass_has_no_offensive_yards():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "TEN"}},
            {"team": {"id": "2", "abbreviation": "NO"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Fumble Recovery (Own)"},
            "text": (
                "QB to TEN 41 for -16 yards. FUMBLES, and recovers at TEN 37. "
                "QB pass incomplete short left to receiver."
            ),
            "statYardage": 0,
            "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
            "end": {"team": {"id": "1"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == 0
    assert rows[0]["Adjusted Yards Per Play"] == 0


def test_rusher_one_yard_before_teammate_fumble_recovery_counts_one_yard():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "SF"}},
            {"team": {"id": "2", "abbreviation": "CAR"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Fumble Recovery (Own)"},
            "text": (
                "C.McCaffrey left tackle to SF 18 for 1 yard. FUMBLES, "
                "recovered by SF-C.McKivitz at SF 33."
            ),
            "statYardage": 16,
            "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
            "end": {"team": {"id": "1"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == 1
    assert rows[0]["Adjusted Yards Per Play"] == 1


def test_rusher_recovering_own_fumble_keeps_full_rushing_yardage():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "BAL"}},
            {"team": {"id": "2", "abbreviation": "BUF"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Fumble Recovery (Own)"},
            "text": (
                "J.Hill left tackle to BUF 23 for -6 yards. FUMBLES, "
                "and recovers at BUF 29. J.Hill to BUF 32 for -3 yards."
            ),
            "statYardage": -15,
            "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
            "end": {"team": {"id": "1"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == -15
    assert rows[0]["Adjusted Yards Per Play"] == -15


def test_fumble_first_touched_behind_runner_charges_loss_to_touch_spot():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "BAL"}},
            {"team": {"id": "2", "abbreviation": "BUF"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Fumble Recovery (Opponent)"},
            "text": (
                "D.Henry left tackle to BLT 38 for -3 yards. FUMBLES, "
                "touched at BLT 32, RECOVERED by BUF at BLT 30."
            ),
            "statYardage": 0,
            "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                      "yardsToEndzone": 59},
            "end": {"team": {"id": "2"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == -9
    assert rows[0]["Adjusted Yards Per Play"] == -9


@pytest.mark.parametrize("play,offense,defense,expected", [
    ({
        "id": "401772750630", "type": {"text": "Fumble Recovery (Opponent)"},
        "text": "J.Herbert pass short right to O.Gadsden to MIA 49 for 8 yards. "
                "FUMBLES, touched at 50, RECOVERED by MIA-J.Brooks at MIA 49.",
        "statYardage": 2,
        "start": {"team": {"id": "1"}, "down": 2, "distance": 7,
                  "yardsToEndzone": 57},
        "end": {"team": {"id": "2"}, "yardsToEndzone": 49},
    }, "LAC", "MIA", 7),
    ({
        "id": "4017729471625", "type": {"text": "Fumble Recovery (Opponent)"},
        "text": "D.Prescott pass short right to J.Ferguson to DET 49 for 4 yards. "
                "FUMBLES, touched at 50, RECOVERED by DET-B.Branch at DET 47.",
        "statYardage": 0,
        "start": {"team": {"id": "1"}, "down": 3, "distance": 21,
                  "yardsToEndzone": 53},
        "end": {"team": {"id": "2"}, "yardsToEndzone": 53},
    }, "DAL", "DET", 3),
    ({
        "id": "4017728581848", "type": {"text": "Fumble Recovery (Own)"},
        "text": "B.Young pass short middle to X.Legette to DAL 39 for -3 yards. "
                "FUMBLES, recovered by CAR-R.Dowdle at DAL 40. "
                "R.Dowdle to DAL 41 for -1 yards. FUMBLES, touched at DAL 41, "
                "recovered by CAR-X.Legette at DAL 45.",
        "statYardage": -9,
        "start": {"team": {"id": "1"}, "down": 2, "distance": 9,
                  "yardsToEndzone": 36},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 45},
    }, "CAR", "DAL", -4),
])
def test_fumble_yards_stop_at_first_touch_or_first_recovery(
    play, offense, defense, expected
):
    assert _yards_for_real_play(play, offense, defense) == (expected, expected)


def test_rushing_fumble_recovered_back_at_line_has_zero_rushing_yards():
    play = {
        "id": "401772717879", "type": {"text": "Fumble Recovery (Opponent)"},
        "text": "J.Croskey-Merritt left tackle to WAS 33 for -2 yards. "
                "FUMBLES, RECOVERED by CHI-K.Gordon at WAS 35.",
        "statYardage": 0,
        "start": {"team": {"id": "1"}, "down": 2, "distance": 10,
                  "yardsToEndzone": 65},
        "end": {"team": {"id": "2"}},
    }
    assert _yards_for_real_play(play, "WSH", "CHI") == (0, 0)


def test_pass_reception_fumble_out_of_bounds_keeps_pre_fumble_loss():
    play = {
        "id": "4017729442196", "type": {"text": "Pass Reception"},
        "text": "G.Smith pass short left to A.Jeanty to LV 38 for -7 yards. "
                "FUMBLES, ball out of bounds at LV 39.",
        "statYardage": -7,
        "start": {"team": {"id": "1"}, "down": 2, "distance": 10,
                  "yardsToEndzone": 55},
        "end": {"team": {"id": "1"}, "yardsToEndzone": 61},
    }
    assert _yards_for_real_play(play, "LV", "DEN") == (-7, -7)


def test_fumble_recovered_behind_runner_charges_yards_to_recovery_spot():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "NYJ"}},
            {"team": {"id": "2", "abbreviation": "MIA"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Sack Opp Fumble Recovery"},
            "text": (
                "J.Fields sacked at MIA 47 for -11 yards. FUMBLES, "
                "RECOVERED by MIA-Ja.Phillips at NYJ 47."
            ),
            "statYardage": 0,
            "start": {"team": {"id": "1"}, "down": 2, "distance": 10,
                      "yardsToEndzone": 36},
            "end": {"team": {"id": "2"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == -17
    assert rows[0]["Adjusted Yards Per Play"] == -17


def test_sack_fumble_teammate_advance_past_scrimmage_erases_sack_loss():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "SF"}},
            {"team": {"id": "2", "abbreviation": "IND"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Fumble Recovery (Own)"},
            "text": (
                "B.Purdy sacked at SF 10 for -8 yards. FUMBLES, "
                "recovered by SF-L.Farrell at SF 9. L.Farrell to SF 21 for 12 yards."
            ),
            "statYardage": 3,
            "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                      "yardsToEndzone": 82},
            "end": {"team": {"id": "1"}, "yardsToEndzone": 79},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == 0
    assert rows[0]["Adjusted Yards Per Play"] == 0


def test_sack_fumble_recovered_toward_scrimmage_uses_recovery_spot():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "TEN"}},
            {"team": {"id": "2", "abbreviation": "DEN"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Sack Opp Fumble Recovery"},
            "text": (
                "C.Ward sacked at TEN 25 for -11 yards. FUMBLES, "
                "RECOVERED by DEN-J.Barron at TEN 34."
            ),
            "statYardage": 0,
            "start": {"team": {"id": "1"}, "down": 2, "distance": 10,
                      "yardsToEndzone": 64},
            "end": {"team": {"id": "2"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == -2
    assert rows[0]["Adjusted Yards Per Play"] == -2


def test_sack_text_reconstructs_line_when_espn_start_spot_is_inconsistent():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "LV"}},
            {"team": {"id": "2", "abbreviation": "CLE"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [
            {"id": "1", "type": {"text": "Fumble Recovery (Own)"},
             "text": "G.Smith sacked at LV 46 for -10 yards. FUMBLES, recovered by LV-S.Forsythe at LV 44.",
             "statYardage": -12,
             "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                       "yardsToEndzone": 56},
             "end": {"team": {"id": "1"}, "yardsToEndzone": 56}},
            {"id": "2", "type": {"text": "Sack Opp Fumble Recovery"},
             "text": "G.Smith sacked at LV 49 for -8 yards. FUMBLES, RECOVERED by CLV-M.Collins at CLV 49.",
             "statYardage": 0,
             "start": {"team": {"id": "1"}, "down": 1, "distance": 10,
                       "yardsToEndzone": 57},
             "end": {"team": {"id": "2"}, "yardsToEndzone": 51}},
        ]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == -18
    assert rows[0]["Adjusted Yards Per Play"] == -9


def test_pass_lateral_then_fumble_credits_combined_gain_to_first_touch():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "CAR"}},
            {"team": {"id": "2", "abbreviation": "TB"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Pass Reception"},
            "text": (
                "QB pass short middle to WR to CAR 34 for 13 yards. "
                "Lateral to WR2 to CAR 36 for 2 yards. FUMBLES, "
                "touched at CAR 35, RECOVERED by TB at CAR 33."
            ),
            "statYardage": 0,
            "start": {"team": {"id": "1"}, "down": 2, "distance": 10,
                      "yardsToEndzone": 79},
            "end": {"team": {"id": "2"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == 14
    assert rows[0]["Adjusted Yards Per Play"] == 14


def test_fake_punt_completed_pass_counts_as_offense():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "ARI"}},
            {"team": {"id": "2", "abbreviation": "LAR"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "type": {"text": "Pass Reception"},
            "text": "(Punt formation) Punter pass to receiver for 28 yards.",
            "statYardage": 28,
            "start": {"team": {"id": "1"}, "down": 4, "distance": 8,
                      "yardsToEndzone": 71},
            "end": {"team": {"id": "1"}},
        }]}]},
    }
    rows, _ = process_game_stats(game, wp_threshold=1.0)
    assert rows[0]["Total Yards"] == 28
    assert rows[0]["Adjusted Yards Per Play"] == 28


@pytest.mark.parametrize("offense,text,yards_to_endzone", [
    (
        "CLE",
        "(Field Goal formation) C.Bojorquez to BUF 38 for -8 yards. "
        "FUMBLES, and recovers at BUF 38. C.Bojorquez pass incomplete short right.",
        30,
    ),
    (
        "NE",
        "(Punt formation) Direct snap to M.Mapu. M.Mapu sacked at NE 43 for -1 "
        "yards. FUMBLES, recovered by NE-J.Gibbens at NE 44.",
        56,
    ),
])
def test_fake_kick_pass_or_sack_is_offensive_snap(offense, text, yards_to_endzone):
    play = {
        "id": "1", "type": {"text": "Fumble Recovery (Own)"}, "text": text,
        "statYardage": 0,
        "start": {"team": {"id": "1"}, "down": 4, "distance": 10,
                  "yardsToEndzone": yards_to_endzone},
        "end": {"team": {"id": "1"}, "yardsToEndzone": yards_to_endzone},
    }
    row, debug = _single_play_with_debug(play, offense=offense)
    assert debug["statDeltas"][offense]["Plays"] == 1
    assert debug["statDeltas"][offense]["Total Offensive Plays"] == 1
    assert row["Total Yards"] == 0
    assert row["Adjusted Yards Per Play"] == 0


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


def test_full_game_threshold_includes_100_percent_win_probability():
    play = {"id": "1", "period": {"number": 4}}
    probability_map = {"1": {"homeWinPercentage": 1.0, "awayWinPercentage": 0.0}}
    assert is_competitive_play(
        play, probability_map, wp_threshold=1.0,
        start_home_wp=1.0, start_away_wp=0.0,
    ) is True


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

    def test_defender_named_kneeland_is_not_a_kneel(self):
        assert is_spike_or_kneel(
            "s.barkley right end to dal 25 for 4 yards (m.kneeland).", "rush"
        ) is False


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
    @pytest.mark.parametrize("play", [
        {
            "type": {"text": "Pass Reception"},
            "text": "M.Stafford pass short right to T.Higbee to LAR 44 for 14 yards (D.Brunskill).",
        },
        {
            "type": {"text": "Pass Reception"},
            "text": "B.Mayfield pass to M.Evans for 19 yards. The play was reviewed; the runner was down by contact.",
        },
        {
            "type": {"text": "Passing Touchdown"},
            "text": "Q.Back pass to A.Receiver for 16 yards, TOUCHDOWN. TWO-POINT CONVERSION ATTEMPT. Q.Back rushes right end for 2 yards.",
        },
        {
            "type": {"text": "Fumble Recovery (Opponent)"},
            "text": "Q.Back pass short middle to A.Receiver for 14 yards. A.Receiver FUMBLES; the runner was down by contact after review.",
        },
    ])
    def test_pass_caption_remains_only_pass_when_later_text_mentions_run(self, play):
        assert classify_offense_play(play) == (True, False, True)

    @pytest.mark.parametrize("play_type,text,yards,expected", [
        ("Pass Reception", "Q.Back pass to T.Brunskill for 14 yards.", 14, 0),
        ("Pass Reception", "Q.Back pass to A.Receiver for 19 yards. The runner was down by contact.", 19, 0),
        ("Passing Touchdown", "Q.Back pass to A.Receiver for 16 yards, TOUCHDOWN. TWO-POINT CONVERSION ATTEMPT. Q.Back rushes right end.", 16, 0),
        ("Pass Reception", "Q.Back pass to A.Receiver for 20 yards.", 20, 1),
        ("Rush", "A.Runner right end for 11 yards.", 11, 1),
        ("Scramble", "Q.Back scrambles right end for 11 yards.", 11, 0),
    ])
    def test_explosive_threshold_uses_exclusive_play_type(self, play_type, text, yards, expected):
        play = {
            "id": "1", "type": {"text": play_type}, "text": text,
            "statYardage": yards,
            "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
            "end": {"team": {"id": "1"}},
        }
        row, _ = _single_play_with_debug(play)
        assert row["Explosive Plays"] == expected

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

    def test_onside_recovery_charges_receiver_when_drive_belongs_to_kicker(self):
        sample = {
            "boxscore": {"teams": [
                {"team": {"id": "1", "abbreviation": "CHI"}},
                {"team": {"id": "2", "abbreviation": "CIN"}},
            ]},
            "header": {"competitions": [{"competitors": [
                {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
            ]}]},
            "drives": {"previous": [{"team": {"id": "2"}, "plays": [{
                "id": "1",
                "type": {"text": "Kickoff"},
                "text": "E.McPherson kicks onside 8 yards from CIN 35 to CIN 43. RECOVERED by CIN-O.Burks.",
                "start": {"team": {"id": "2"}},
                "end": {"team": {"id": "2"}},
            }]}]},
            "scoringPlays": [],
        }
        rows, details = process_game_stats(sample, expanded=True)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["CHI"]["Turnovers"] == 1
        assert by_team["CIN"]["Turnovers"] == 0
        assert details["1"]["Turnovers"][0]["reason"] == "onside_kick_lost"

    def test_onside_kick_recovered_by_receiving_team_is_not_turnover(self):
        play = {
            "type": {"text": "Kickoff"},
            "text": "AAA kicks onside. RECOVERED by BBB at BBB 45.",
            "end": {"team": {"id": "2"}},
        }
        assert _turnovers_for_single_play(play) == {"AAA": 0, "BBB": 0}

    def test_blocked_field_goal_muffed_catch_charges_receiving_team(self):
        sample = {
            "boxscore": {"teams": [
                {"team": {"id": "1", "abbreviation": "CAR"}},
                {"team": {"id": "2", "abbreviation": "NO"}},
            ]},
            "header": {"competitions": [{"competitors": [
                {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
            ]}]},
            "drives": {"previous": [{
                "team": {"id": "1"},
                "plays": [{
                    "id": "4017728772504",
                    "type": {"text": "Blocked Field Goal"},
                    "text": (
                        "Field goal BLOCKED. The play was REVERSED."
                        "Field goal BLOCKED. C.Jordan MUFFS catch at NO 29, "
                        "RECOVERED by CAR-D.Lewis at NO 30."
                    ),
                    "start": {"team": {"id": "1"}},
                    "end": {"team": {"id": "1"}},
                }],
            }]},
        }
        rows, details = process_game_stats(sample, expanded=True)
        by_team = {row["Team"]: row for row in rows}
        assert by_team["NO"]["Turnovers"] == 1
        assert by_team["CAR"]["Turnovers"] == 0
        assert details["2"]["Turnovers"][0]["reason"] == "muffed_kick"

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
        assert by_team["AAA"]["Adjusted Yards Per Play"] == 4.0

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
        assert by_team["AAA"]["Adjusted Yards Per Play"] == -3.0

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
                {"Team": "AAA", "Explosive Plays": 3, "Adjusted Yards Per Play": 5.5},
                {"Team": "BBB", "Explosive Plays": 1, "Adjusted Yards Per Play": 3.2},
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
