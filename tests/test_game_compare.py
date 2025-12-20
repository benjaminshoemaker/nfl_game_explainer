import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import game_compare as gc


def test_calculate_success_thresholds():
    assert gc.calculate_success(1, 10, 4) is True
    assert gc.calculate_success(1, 10, 3.9) is False
    assert gc.calculate_success(2, 10, 6) is True
    assert gc.calculate_success(3, 5, 5) is True
    assert gc.calculate_success(4, 1, 0.9) is False


def test_get_pregame_probabilities_from_winprobability(monkeypatch):
    class FakeResponse:
        def __init__(self, payload, status=200):
            self._payload = payload
            self.status_code = status

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise gc.requests.HTTPError("error")

    def fake_get(url, headers=None, timeout=None):
        assert "summary" in url
        return FakeResponse(
            {
                "winprobability": [
                    {"homeWinPercentage": 0.7047, "tiePercentage": 0.0, "playId": "pre"},
                    {"homeWinPercentage": 0.70, "playId": "123"},
                ]
            }
        )

    monkeypatch.setattr(gc.requests, "get", fake_get)
    home_wp, away_wp = gc.get_pregame_probabilities("12345")
    assert home_wp == pytest.approx(0.7047)
    assert away_wp == pytest.approx(0.2953)


def test_get_pregame_probabilities_missing_predictor_returns_even(monkeypatch):
    class FakeResponse:
        def __init__(self, payload, status=200):
            self._payload = payload
            self.status_code = status

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise gc.requests.HTTPError("error")

    def fake_get(url, headers=None, timeout=None):
        return FakeResponse({})

    monkeypatch.setattr(gc.requests, "get", fake_get)
    assert gc.get_pregame_probabilities("abcde") == (0.5, 0.5)


def test_wp_delta_starts_from_pregame_probabilities():
    # Home pregame WP 0.60 -> first play WP 0.65 should yield +0.05 delta.
    game_data = {
        "boxscore": {
            "teams": [
                {"team": {"id": "1", "abbreviation": "HOM"}},
                {"team": {"id": "2", "abbreviation": "AWY"}},
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
                    "team": {"id": "1", "abbreviation": "HOM"},
                    "start": {"yardsToEndzone": 75},
                    "yards": 25,
                    "plays": [
                        {
                            "id": "10",
                            "text": "Pass complete for 25 yards",
                            "type": {"text": "Pass"},
                            "statYardage": 25,
                            "start": {"down": 1, "distance": 10},
                            "period": {"number": 1},
                            "clock": {"displayValue": "15:00"},
                            "team": {"abbreviation": "HOM", "id": "1"},
                        }
                    ],
                }
            ]
        },
        "scoringPlays": [],
    }
    probability_map = {"10": {"homeWinPercentage": 0.65, "awayWinPercentage": 0.35}}

    _, details = gc.process_game_stats(
        game_data,
        expanded=True,
        probability_map=probability_map,
        pregame_probabilities=(0.6, 0.4),
    )

    explosive = details["1"]["Explosive Plays"][0]
    prob = explosive["probability"]
    assert prob["homeWinPercentage"] == pytest.approx(0.65)
    assert prob["homeDelta"] == pytest.approx(0.05)


def test_process_game_stats_basic():
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
        "drives": {
            "previous": [
                {
                    "team": {"id": "1"},
                    "start": {"yardsToEndzone": 75},
                    "yards": 50,
                    "plays": [
                        {
                            "text": "A run for 5 yards",
                            "type": {"text": "Rush"},
                            "statYardage": 5,
                            "start": {"down": 1, "distance": 10},
                            "team": {"abbreviation": "AAA", "id": "1"},
                        },
                        {
                            "text": "Pass for 25 yards",
                            "type": {"text": "Pass"},
                            "statYardage": 25,
                            "start": {"down": 2, "distance": 5},
                            "team": {"abbreviation": "AAA", "id": "1"},
                        },
                        {
                            "text": "Touchdown pass",
                            "type": {"text": "Pass"},
                            "statYardage": 20,
                            "start": {"down": 1, "distance": 10},
                            "team": {"abbreviation": "AAA", "id": "1"},
                            "scoringPlay": True,
                            "scoreValue": 7,
                        },
                    ],
                },
                {
                    "team": {"id": "2"},
                    "start": {"yardsToEndzone": 65},
                    "yards": 30,
                    "plays": [
                        {
                            "text": "Punt",
                            "type": {"text": "Punt"},
                            "statYardage": 40,
                            "start": {"down": 3, "distance": 5},
                            "team": {"abbreviation": "BBB", "id": "2"},
                        },
                        {
                            "text": "INTERCEPTED",
                            "type": {"text": "Pass"},
                            "statYardage": -2,
                            "start": {"down": 2, "distance": 10},
                            "team": {"abbreviation": "BBB", "id": "2"},
                        },
                    ],
                },
            ]
        },
    }

    df = gc.process_game_stats(sample).set_index("Team")
    aaa = df.loc["AAA"]
    bbb = df.loc["BBB"]

    assert aaa["Score"] == 7
    assert aaa["Points per Drive"] == 7
    assert aaa["Points Per Trip (Inside 40)"] == 7
    assert aaa["Explosive Plays"] == 2
    assert aaa["Explosive Play Rate"] > 0
    assert bbb["Turnovers"] == 1
    assert bbb["Net Punting"] == 40
    assert aaa["Turnover Margin"] == 1


def test_penalty_and_spike_excluded_from_rates():
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
                    "start": {"yardsToEndzone": 80},
                    "yards": 0,
                    "plays": [
                        {"text": "Spike to stop the clock", "type": {"text": "Spike"}, "team": {"abbreviation": "AAA", "id": "1"}},
                        {"text": "Penalty on offense", "type": {"text": "Penalty"}, "team": {"abbreviation": "AAA", "id": "1"}},
                        {
                            "text": "Run for 4 yards",
                            "type": {"text": "Rush"},
                            "statYardage": 4,
                            "start": {"down": 1, "distance": 10},
                            "team": {"abbreviation": "AAA", "id": "1"},
                        },
                    ],
                }
            ]
        },
    }
    df = gc.process_game_stats(sample).set_index("Team")
    aaa = df.loc["AAA"]
    # Only the rush should count as a play; success rate from 1/1, YPP from 4 yards.
    assert aaa["Success Rate"] == 1.0
    assert aaa["Yards Per Play"] == 4.0


def test_html_advanced_metrics_payload_alignment():
    sample = {
        "boxscore": {
            "teams": [
                {
                    "team": {"id": "1", "abbreviation": "AAA"},
                    "statistics": [{"label": "Penalties", "name": "totalPenaltiesYards", "displayValue": "2-20"}],
                },
                {
                    "team": {"id": "2", "abbreviation": "BBB"},
                    "statistics": [{"label": "Penalties", "name": "totalPenaltiesYards", "displayValue": "5-55"}],
                },
            ]
        },
        "header": {
            "competitions": [
                {
                    "competitors": [
                        {"id": "1", "score": "0", "homeAway": "home"},
                        {"id": "2", "score": "7", "homeAway": "away"},
                    ]
                }
            ]
        },
        "drives": {
            "previous": [
                {
                    "team": {"id": "1"},
                    "start": {"yardsToEndzone": 70},
                    "yards": 0,
                    "plays": [
                        {
                            "id": "10",
                            "text": "Pick-six by defense",
                            "type": {"text": "Interception Return Touchdown"},
                            "statYardage": -5,
                            "start": {"down": 2, "distance": 8, "team": {"id": "1"}},
                            "team": {"abbreviation": "AAA", "id": "1"},
                            "scoringPlay": True,
                        }
                    ],
                }
            ]
        },
        "scoringPlays": [
            {
                "id": "10",
                "team": {"id": "2"},
                "type": {"text": "Interception Return Touchdown"},
                "text": "Pick-six by BBB",
                "homeScore": 0,
                "awayScore": 7,
                "scoringType": {"name": "touchdown"},
                "period": {"number": 1},
                "clock": {"displayValue": "10:00"},
            }
        ],
    }

    df, details = gc.process_game_stats(sample, expanded=True)
    advanced_table = df[gc.ADVANCED_COLS].to_dict(orient="records")
    table_by_team = {row["Team"]: row for row in advanced_table}

    assert table_by_team["AAA"]["Penalty Yards"] == 20
    assert table_by_team["BBB"]["Penalty Yards"] == 55
    assert table_by_team["BBB"]["Non-Offensive Points"] == 7

    # Expanded details should include the non-offensive score for the scoring team.
    assert details["2"]["Non-Offensive Scores"][0]["points"] == 7


def test_penalty_yards_from_boxscore():
    sample = {
        "boxscore": {
            "teams": [
                {
                    "team": {"id": "1", "abbreviation": "AAA"},
                    "statistics": [{"label": "Penalties", "name": "totalPenaltiesYards", "displayValue": "4-35"}],
                },
                {
                    "team": {"id": "2", "abbreviation": "BBB"},
                    "statistics": [{"label": "Penalties", "name": "totalPenaltiesYards", "displayValue": "6-60"}],
                },
            ]
        },
        "header": {"competitions": [{"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": []}, {"team": {"id": "2"}, "plays": []}]},
        "scoringPlays": [],
    }

    df = gc.process_game_stats(sample).set_index("Team")
    assert df.loc["AAA"]["Penalty Yards"] == 35
    assert df.loc["BBB"]["Penalty Yards"] == 60


def test_non_offensive_points_pick_six():
    sample = {
        "boxscore": {
            "teams": [
                {"team": {"id": "1", "abbreviation": "AAA"}, "statistics": []},
                {"team": {"id": "2", "abbreviation": "BBB"}, "statistics": []},
            ]
        },
        "header": {
            "competitions": [
                {
                    "competitors": [
                        {"id": "1", "score": "0", "homeAway": "home"},
                        {"id": "2", "score": "7", "homeAway": "away"},
                    ]
                }
            ]
        },
        "drives": {
            "previous": [
                {
                    "team": {"id": "1"},
                    "start": {"yardsToEndzone": 70},
                    "yards": 0,
                    "plays": [
                        {
                            "id": "10",
                            "text": "Pick-six by defense",
                            "type": {"text": "Interception Return Touchdown"},
                            "statYardage": -5,
                            "start": {"down": 2, "distance": 8, "team": {"id": "1"}},
                            "team": {"abbreviation": "AAA", "id": "1"},
                            "scoringPlay": True,
                        }
                    ],
                }
            ]
        },
        "scoringPlays": [
            {
                "id": "10",
                "team": {"id": "2"},
                "type": {"text": "Interception Return Touchdown"},
                "text": "Pick-six by BBB",
                "homeScore": 0,
                "awayScore": 7,
                "scoringType": {"name": "touchdown"},
                "period": {"number": 1},
                "clock": {"displayValue": "10:00"},
            }
        ],
    }

    df = gc.process_game_stats(sample, expanded=True)
    table = df[0].set_index("Team")
    bbb = table.loc["BBB"]
    assert bbb["Non-Offensive Points"] == 7

    details = df[1]
    assert details["2"]["Non-Offensive Scores"][0]["points"] == 7


def test_non_offensive_points_includes_plays_that_make_game_competitive():
    """
    Regression: scoring-play based Non-Offensive Points should include plays that
    make the game competitive (competitive at start OR end of play).
    """
    sample = {
        "boxscore": {
            "teams": [
                {"team": {"id": "1", "abbreviation": "AAA"}, "statistics": []},
                {"team": {"id": "2", "abbreviation": "BBB"}, "statistics": []},
            ]
        },
        "header": {
            "competitions": [
                {
                    "competitors": [
                        {"id": "1", "score": "0", "homeAway": "home"},
                        {"id": "2", "score": "8", "homeAway": "away"},
                    ]
                }
            ]
        },
        "drives": {
            "previous": [
                {
                    # Drive offense is AAA; BBB scores on punt return.
                    "team": {"id": "1"},
                    "plays": [
                        {
                            "id": "9",
                            "text": "AAA run for 0 yards.",
                            "type": {"text": "Rush"},
                            "statYardage": 0,
                            "start": {"down": 1, "distance": 10, "team": {"id": "1"}},
                        },
                        {
                            "id": "10",
                            "text": "AAA punts. BBB return TOUCHDOWN. TWO-POINT CONVERSION ATTEMPT SUCCEEDS.",
                            "type": {"text": "Punt Return Touchdown"},
                            "start": {"down": 4, "distance": 8, "team": {"id": "1"}},
                            "team": {"abbreviation": "AAA", "id": "1"},
                            "scoringPlay": True,
                        },
                    ],
                }
            ]
        },
        "scoringPlays": [
            {
                "id": "10",
                "team": {"id": "2"},
                "type": {"text": "Punt Return Touchdown"},
                "text": "BBB Punt Return Touchdown + 2pt conversion",
                "homeScore": 0,
                "awayScore": 8,
                "scoringType": {"name": "touchdown"},
                "period": {"number": 4},
                "clock": {"displayValue": "08:03"},
            }
        ],
    }

    # Probability map is end-of-play. The start-of-play for play 10 is the end-of-play
    # for play 9. Even though play 10 starts non-competitive, it ends competitive, so it
    # should be included.
    prob_map = {
        "9": {"homeWinPercentage": 0.02, "awayWinPercentage": 0.98, "tiePercentage": 0.0},
        "10": {"homeWinPercentage": 0.11, "awayWinPercentage": 0.89, "tiePercentage": 0.0},
    }

    df, details = gc.process_game_stats(
        sample,
        expanded=True,
        probability_map=prob_map,
        pregame_probabilities=(0.5, 0.5),
        wp_threshold=0.975,
    )
    table = df.set_index("Team")
    assert table.loc["BBB"]["Non-Offensive Points"] == 8
    assert len(details["2"]["Non-Offensive Scores"]) == 1


def test_is_competitive_play_logic():
    prob_map = {
        "1": {"homeWinPercentage": 0.98, "awayWinPercentage": 0.02},
        "2": {"homeWinPercentage": 0.6, "awayWinPercentage": 0.4},
        "3": {"homeWinPercentage": 0.1, "awayWinPercentage": 0.9},
    }

    high_wp_home = {"id": "1", "period": {"number": 2}}
    assert gc.is_competitive_play(high_wp_home, prob_map, wp_threshold=0.97) is False

    balanced = {"id": "2", "period": {"number": 2}}
    assert gc.is_competitive_play(balanced, prob_map, wp_threshold=0.97) is True

    high_wp_away = {"id": "3", "period": {"number": 3}}
    assert gc.is_competitive_play(high_wp_away, prob_map, wp_threshold=0.85) is False

    missing_wp = {"id": "999", "period": {"number": 2}}
    assert gc.is_competitive_play(missing_wp, prob_map, wp_threshold=0.5) is True

    overtime_play = {"id": "1", "period": {"number": 5}}
    assert gc.is_competitive_play(overtime_play, prob_map, wp_threshold=0.5) is True


def test_process_game_stats_filters_noncompetitive_time():
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
                        {"id": "1", "score": "14", "homeAway": "home"},
                        {"id": "2", "score": "7", "homeAway": "away"},
                    ]
                }
            ]
        },
        "drives": {
            "previous": [
                {
                    "team": {"id": "1"},
                    "start": {"yardsToEndzone": 75},
                    "yards": 65,
                    "plays": [
                        {
                            "id": "11",
                            "text": "Run for 5",
                            "type": {"text": "Rush"},
                            "statYardage": 5,
                            "start": {"down": 1, "distance": 10, "yardsToEndzone": 75, "possessionText": "AAA 25"},
                            "team": {"abbreviation": "AAA", "id": "1"},
                        },
                        {
                            "id": "12",
                            "text": "Pass for 25",
                            "type": {"text": "Pass"},
                            "statYardage": 25,
                            "start": {"down": 2, "distance": 5, "yardsToEndzone": 50, "possessionText": "AAA 50"},
                            "team": {"abbreviation": "AAA", "id": "1"},
                        },
                        {
                            "id": "13",
                            "text": "Touchdown pass",
                            "type": {"text": "Pass"},
                            "statYardage": 35,
                            "start": {
                                "down": 1,
                                "distance": 10,
                                "yardsToEndzone": 30,
                                "possessionText": "BBB 30",
                                "downDistanceText": "1st & 10",
                            },
                            "team": {"abbreviation": "AAA", "id": "1"},
                            "scoringPlay": True,
                            "scoreValue": 7,
                        },
                    ],
                },
                {
                    "team": {"id": "2"},
                    "start": {"yardsToEndzone": 70},
                    "yards": 10,
                    "plays": [
                        {
                            "id": "21",
                            "text": "Late rush for 10",
                            "type": {"text": "Rush"},
                            "statYardage": 10,
                            "start": {"down": 1, "distance": 10, "yardsToEndzone": 70, "possessionText": "BBB 30"},
                            "team": {"abbreviation": "BBB", "id": "2"},
                        },
                        {
                            "id": "22",
                            "text": "Garbage time TD",
                            "type": {"text": "Pass"},
                            "statYardage": 10,
                            "start": {"down": 2, "distance": 5, "yardsToEndzone": 20, "possessionText": "AAA 20"},
                            "team": {"abbreviation": "BBB", "id": "2"},
                            "scoringPlay": True,
                            "scoreValue": 7,
                        },
                    ],
                },
            ]
        },
        "scoringPlays": [
            {
                "id": "13",
                "team": {"id": "1"},
                "type": {"text": "Pass Reception Touchdown"},
                "text": "AAA TD",
                "homeScore": 7,
                "awayScore": 0,
                "period": {"number": 1},
                "clock": {"displayValue": "05:00"},
                "scoringType": {"name": "touchdown"},
            },
            {
                "id": "22",
                "team": {"id": "2"},
                "type": {"text": "Pass Reception Touchdown"},
                "text": "BBB TD late",
                "homeScore": 14,
                "awayScore": 7,
                "period": {"number": 4},
                "clock": {"displayValue": "01:00"},
                "scoringType": {"name": "touchdown"},
            },
        ],
    }
    probability_map = {
        "11": {"homeWinPercentage": 0.6, "awayWinPercentage": 0.4},
        "12": {"homeWinPercentage": 0.65, "awayWinPercentage": 0.35},
        "13": {"homeWinPercentage": 0.7, "awayWinPercentage": 0.3},
        "21": {"homeWinPercentage": 0.9, "awayWinPercentage": 0.1},
        "22": {"homeWinPercentage": 0.97, "awayWinPercentage": 0.03},
    }

    df, details = gc.process_game_stats(sample, expanded=True, probability_map=probability_map, wp_threshold=0.8)
    table = df.set_index("Team")

    aaa = table.loc["AAA"]
    assert aaa["Total Yards"] == 65
    assert aaa["Explosive Plays"] == 2
    assert aaa["Points per Drive"] == 7
    assert aaa["Points Per Trip (Inside 40)"] == 7
    assert aaa["Drives"] == 1

    # BBB's plays: play 21 starts with home WP 0.7 (competitive), play 22 starts with home WP 0.9 (non-competitive)
    # So play 21 (10 yards) counts, but play 22 (TD) is filtered out
    bbb = table.loc["BBB"]
    assert bbb["Total Yards"] == 10  # Play 21's 10 yards counts (start WP 0.7 < threshold 0.8)
    assert bbb["Explosive Plays"] == 1  # Play 21 is a 10-yard rush (explosive run >= 10 yards)
    assert bbb["Points per Drive"] == 0  # TD was in non-competitive time
    assert bbb["Drives"] == 1  # Drive started competitive (first play was competitive)
    assert bbb["Points Per Trip (Inside 40)"] == 0  # No points in competitive time

    # Expanded details should only include competitive plays
    assert len(details["1"]["Explosive Plays"]) == 2
    assert len(details["2"]["Explosive Plays"]) == 1  # Play 21's 10-yard rush is explosive


def test_build_top_plays_by_wp_filters_and_sorts():
    game_data = {
        "boxscore": {
            "teams": [
                {"team": {"id": "1", "abbreviation": "AAA"}},
                {"team": {"id": "2", "abbreviation": "BBB"}},
            ]
        },
        "drives": {
            "previous": [
                {
                    "team": {"id": "1"},
                    "plays": [
                        {"id": "1", "period": {"number": 1}, "clock": {"displayValue": "10:00"}, "text": "Play one big gain"},
                        {"id": "2", "period": {"number": 2}, "clock": {"displayValue": "05:00"}, "text": "Blowout garbage time"},
                    ],
                },
                {
                    "team": {"id": "2"},
                    "plays": [{"id": "3", "period": {"number": 5}, "clock": {"displayValue": "02:00"}, "text": "Overtime swing"}],
                },
            ]
        },
    }
    probability_map = {
        "1": {"homeWinPercentage": 0.98, "awayWinPercentage": 0.02},
        # This play starts in blowout (prev home_wp=0.98) and should be filtered in regulation.
        "2": {"homeWinPercentage": 0.99, "awayWinPercentage": 0.01},
        # OT is always treated as competitive.
        "3": {"homeWinPercentage": 0.7, "awayWinPercentage": 0.3},
    }

    result = gc.build_top_plays_by_wp(game_data, probability_map, wp_threshold=0.975)
    lines = result.splitlines()
    assert lines[0].startswith("48.0% | Q1 10:00 | AAA")
    assert lines[1].startswith("29.0% | Q5 02:00 | BBB")
    assert len(lines) == 2


def test_calculate_wp_trajectory_stats_uses_leader(monkeypatch):
    game_data = {
        "drives": {
            "previous": [
                {
                    "plays": [
                        {"id": "1", "period": {"number": 1}, "clock": {"displayValue": "15:00"}, "text": "First play"},
                        {"id": "2", "period": {"number": 2}, "clock": {"displayValue": "10:00"}, "text": "Second swing"},
                        {"id": "3", "period": {"number": 3}, "clock": {"displayValue": "05:00"}, "text": "Third play"},
                    ]
                }
            ]
        }
    }
    probability_map = {
        "1": {"homeWinPercentage": 0.6, "awayWinPercentage": 0.4},
        "2": {"homeWinPercentage": 0.45, "awayWinPercentage": 0.55},
        "3": {"homeWinPercentage": 0.55, "awayWinPercentage": 0.45},
    }

    stats = gc.calculate_wp_trajectory_stats(game_data, probability_map, leader_is_home=False)
    assert stats["leader_min_wp"] == pytest.approx(40.0)
    assert stats["wp_crossings"] == 2
    assert stats["max_wp_delta"] == pytest.approx(15.0)
    assert "Q2 10:00" in stats["max_wp_play_desc"]


def test_generate_game_summary_in_progress(monkeypatch):
    payload = {
        "team_meta": [
            {"id": "1", "abbr": "AWY", "name": "Away Team", "homeAway": "away"},
            {"id": "2", "abbr": "HOM", "name": "Home Team", "homeAway": "home"},
        ],
        "summary_table": [{"Team": "AWY", "Score": 10}, {"Team": "HOM", "Score": 14}],
        "advanced_table": [
            {"Team": "AWY", "Turnovers": 1, "Success Rate": 0.4, "Explosive Plays": 3, "Points Per Trip (Inside 40)": 3.0, "Non-Offensive Points": 0},
            {"Team": "HOM", "Turnovers": 0, "Success Rate": 0.6, "Explosive Plays": 4, "Points Per Trip (Inside 40)": 4.5, "Non-Offensive Points": 7},
        ],
    }
    game_data = {
        "header": {
            "competitions": [
                {
                    "status": {"type": {"completed": False}, "period": 2, "displayClock": "12:00"},
                    "competitors": [
                        {"id": "1", "homeAway": "away", "team": {"abbreviation": "AWY", "displayName": "Away Team"}},
                        {"id": "2", "homeAway": "home", "team": {"abbreviation": "HOM", "displayName": "Home Team"}},
                    ],
                }
            ]
        },
        "boxscore": {"teams": [{"team": {"id": "1", "abbreviation": "AWY"}}, {"team": {"id": "2", "abbreviation": "HOM"}}]},
        "drives": {
            "previous": [
                {"team": {"id": "1"}, "plays": [{"id": "1", "period": {"number": 1}, "clock": {"displayValue": "10:00"}, "text": "Away touchdown"}]},
                {"team": {"id": "2"}, "plays": [{"id": "2", "period": {"number": 2}, "clock": {"displayValue": "08:00"}, "text": "Home response"}]},
            ]
        },
    }
    probability_map = {
        "1": {"homeWinPercentage": 0.3, "awayWinPercentage": 0.7},
        "2": {"homeWinPercentage": 0.55, "awayWinPercentage": 0.45},
    }

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    captured = {}

    class FakeResponse:
        def __init__(self):
            self.choices = [type("obj", (), {"message": type("msg", (), {"content": "Stub summary"})()})]

    class FakeOpenAI:
        def __init__(self, api_key=None):
            self.chat = self
            self.completions = self
            self.api_key = api_key

        def create(self, **kwargs):
            captured["request"] = kwargs
            return FakeResponse()

    monkeypatch.setattr(gc, "OpenAI", FakeOpenAI)

    summary = gc.generate_game_summary(payload, game_data, probability_map, wp_threshold=0.975)
    assert summary == "Stub summary"
    user_prompt = captured["request"]["messages"][1]["content"]
    assert "Status: Q2 12:00" in user_prompt
    assert "HOM leads by 4" in user_prompt
    assert "why HOM leads" in user_prompt


def test_points_per_trip_details_use_drive_finisher():
    sample = {
        "boxscore": {
            "teams": [
                {"team": {"id": "1", "abbreviation": "AAA"}},
                {"team": {"id": "2", "abbreviation": "BBB"}},
            ]
        },
        "header": {
            "competitions": [
                {"competitors": [{"id": "1", "score": "7", "homeAway": "home"}, {"id": "2", "score": "0", "homeAway": "away"}]}
            ]
        },
        "drives": {
            "previous": [
                {
                    "team": {"id": "1"},
                    "start": {"yardsToEndzone": 35},
                    "plays": [
                        {
                            "id": "10",
                            "text": "Run to the 20",
                            "type": {"text": "Rush"},
                            "statYardage": 15,
                            "start": {"down": 1, "distance": 10, "yardsToEndzone": 35, "possessionText": "AAA 35"},
                            "period": {"number": 1},
                            "clock": {"displayValue": "10:00"},
                            "team": {"abbreviation": "AAA", "id": "1"},
                        },
                        {
                            "id": "11",
                            "text": "Touchdown catch",
                            "type": {"text": "Pass"},
                            "statYardage": 20,
                            "start": {"down": 2, "distance": 5, "yardsToEndzone": 20, "possessionText": "BBB 20"},
                            "period": {"number": 1},
                            "clock": {"displayValue": "08:00"},
                            "team": {"abbreviation": "AAA", "id": "1"},
                            "scoringPlay": True,
                            "scoreValue": 7,
                        },
                    ],
                }
            ]
        },
        "scoringPlays": [
            {
                "id": "11",
                "team": {"id": "1"},
                "type": {"text": "Pass Reception Touchdown"},
                "text": "Touchdown catch",
                "homeScore": 7,
                "awayScore": 0,
                "period": {"number": 1},
                "clock": {"displayValue": "08:00"},
                "scoringType": {"name": "touchdown"},
            }
        ],
    }

    df, details = gc.process_game_stats(sample, expanded=True)
    finisher = details["1"]["Points Per Trip (Inside 40)"][0]
    assert finisher["text"] == "Touchdown catch"
    assert finisher.get("points") == 7


def test_points_per_trip_skips_timeouts_as_finisher():
    sample = {
        "boxscore": {
            "teams": [
                {"team": {"id": "1", "abbreviation": "AAA"}},
                {"team": {"id": "2", "abbreviation": "BBB"}},
            ]
        },
        "header": {"competitions": [{"competitors": [{"id": "1", "score": "3"}, {"id": "2", "score": "0"}]}]},
        "drives": {
            "previous": [
                {
                    "team": {"id": "1"},
                    "start": {"yardsToEndzone": 30},
                    "plays": [
                        {
                            "id": "31",
                            "text": "Field goal good",
                            "type": {"text": "Field Goal"},
                            "statYardage": 0,
                            "start": {"down": 4, "distance": 5, "yardsToEndzone": 20, "possessionText": "BBB 20"},
                            "period": {"number": 2},
                            "clock": {"displayValue": "01:00"},
                            "team": {"abbreviation": "AAA", "id": "1"},
                            "scoringPlay": True,
                            "scoreValue": 3,
                        },
                        {
                            "id": "32",
                            "text": "Official Timeout",
                            "type": {"text": "Timeout"},
                            "start": {"down": 1, "distance": 10, "yardsToEndzone": 65, "possessionText": "AAA 35"},
                            "period": {"number": 2},
                            "clock": {"displayValue": "00:55"},
                            "team": {"abbreviation": "AAA", "id": "1"},
                        },
                    ],
                }
            ]
        },
        "scoringPlays": [
            {
                "id": "31",
                "team": {"id": "1"},
                "type": {"text": "Field Goal"},
                "text": "Field goal good",
                "homeScore": 3,
                "awayScore": 0,
                "period": {"number": 2},
                "clock": {"displayValue": "01:00"},
                "scoringType": {"name": "field goal"},
            }
        ],
    }

    df, details = gc.process_game_stats(sample, expanded=True)
    finisher = details["1"]["Points Per Trip (Inside 40)"][0]
    assert finisher["text"] == "Field goal good"


def test_points_per_trip_excludes_drives_without_40_entry():
    sample = {
        "boxscore": {
            "teams": [
                {"team": {"id": "1", "abbreviation": "SEA"}},
                {"team": {"id": "2", "abbreviation": "DAL"}},
            ]
        },
        "header": {"competitions": [{"competitors": [{"id": "1", "score": "0"}, {"id": "2", "score": "0"}]}]},
        "drives": {
            "previous": [
                {
                    "team": {"id": "1"},
                    "start": {"yardsToEndzone": 69},
                    "plays": [
                        {
                            "id": "40",
                            "text": "Punt",
                            "type": {"text": "Punt"},
                            "statYardage": 40,
                            "start": {"down": 4, "distance": 8, "yardsToEndzone": 69, "possessionText": "SEA 31"},
                            "end": {"yardsToEndzone": 30},
                            "period": {"number": 1},
                            "clock": {"displayValue": "05:58"},
                            "team": {"abbreviation": "SEA", "id": "1"},
                        }
                    ],
                }
            ]
        },
        "scoringPlays": [],
    }

    df, details = gc.process_game_stats(sample, expanded=True)
    assert details["1"]["Points Per Trip (Inside 40)"] == []


def test_penalty_details_exclude_declined_penalties():
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
                            "id": "21",
                            "text": "Penalty on offense, holding",
                            "type": {"text": "Penalty"},
                            "start": {"down": 1, "distance": 10, "yardsToEndzone": 60, "possessionText": "AAA 40"},
                            "period": {"number": 2},
                            "clock": {"displayValue": "05:00"},
                            "team": {"abbreviation": "AAA", "id": "1"},
                            "penalty": {"yards": 10, "team": {"id": "1"}, "status": {"slug": "accepted"}},
                        },
                        {
                            "id": "22",
                            "text": "Penalty on BBB defense, declined.",
                            "type": {"text": "Pass"},
                            "start": {"down": 2, "distance": 15, "yardsToEndzone": 50, "possessionText": "AAA 50"},
                            "period": {"number": 2},
                            "clock": {"displayValue": "04:30"},
                            "team": {"abbreviation": "AAA", "id": "1"},
                            "hasPenalty": True,
                        },
                        {
                            "id": "23",
                            "text": "Pass incomplete. PENALTY on BBB-Player, Roughing the Passer, 15 yards, enforced at AAA 50 - No Play. Penalty on BBB-Player, Unnecessary Roughness, declined.",
                            "type": {"text": "Pass"},
                            "start": {"down": 3, "distance": 10, "yardsToEndzone": 50, "possessionText": "AAA 50"},
                            "period": {"number": 2},
                            "clock": {"displayValue": "04:00"},
                            "team": {"abbreviation": "AAA", "id": "1"},
                            "penalty": {"yards": 15, "team": {"id": "2"}, "status": {"slug": "accepted"}},
                        },
                    ],
                }
            ]
        },
        "scoringPlays": [],
    }

    _, details = gc.process_game_stats(sample, expanded=True)
    penalties_offense = details["1"]["Penalty Yards"]
    penalties_defense = details["2"]["Penalty Yards"]
    assert len(penalties_offense) == 1
    assert penalties_offense[0]["yards"] == -10
    assert "holding" in penalties_offense[0]["text"]
    assert len(penalties_defense) == 1
    assert penalties_defense[0]["yards"] == -15
    assert "Roughing the Passer" in penalties_defense[0]["text"]


def test_non_offensive_points_details_show_scoring_play():
    sample = {
        "boxscore": {
            "teams": [
                {"team": {"id": "1", "abbreviation": "AAA"}, "statistics": []},
                {"team": {"id": "2", "abbreviation": "BBB"}, "statistics": []},
            ]
        },
        "header": {
            "competitions": [
                {
                    "competitors": [
                        {"id": "1", "score": "0", "homeAway": "home"},
                        {"id": "2", "score": "7", "homeAway": "away"},
                    ]
                }
            ]
        },
        "drives": {
            "previous": [
                {
                    "team": {"id": "1"},
                    "start": {"yardsToEndzone": 70},
                    "plays": [
                        {
                            "id": "10",
                            "text": "Pick-six by defense",
                            "type": {"text": "Interception Return Touchdown"},
                            "statYardage": -5,
                            "start": {"down": 2, "distance": 8, "team": {"id": "1"}},
                            "team": {"abbreviation": "AAA", "id": "1"},
                            "scoringPlay": True,
                        }
                    ],
                }
            ]
        },
        "scoringPlays": [
            {
                "id": "10",
                "team": {"id": "2"},
                "type": {"text": "Interception Return Touchdown"},
                "text": "Pick-six by BBB",
                "homeScore": 0,
                "awayScore": 7,
                "scoringType": {"name": "touchdown"},
                "period": {"number": 1},
                "clock": {"displayValue": "10:00"},
            }
        ],
    }

    df, details = gc.process_game_stats(sample, expanded=True)
    non_off = details["2"]["Non-Offensive Points"]
    assert non_off[0]["points"] == 7
    assert "Pick-six" in non_off[0]["text"]
