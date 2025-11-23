import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import game_compare as gc


def test_calculate_success_thresholds():
    assert gc.calculate_success(1, 10, 4) is True
    assert gc.calculate_success(1, 10, 3.9) is False
    assert gc.calculate_success(2, 10, 6) is True
    assert gc.calculate_success(3, 5, 5) is True
    assert gc.calculate_success(4, 1, 0.9) is False


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
    assert aaa["Pts per Trip (Inside 40)"] == 7
    assert aaa["Explosive Plays"] == 2
    assert aaa["Explosive Rate"] > 0
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
