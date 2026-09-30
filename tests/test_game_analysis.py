import json
import os
import sys
import urllib.error

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from lib import game_analysis as ga


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_get_game_data_falls_back_to_playbyplay(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=15):
        url = getattr(req, "full_url", req)
        calls.append(url)
        if "summary" in url:
            raise urllib.error.HTTPError(url, 401, "Unauthorized", None, None)
        return FakeResponse({"gamepackageJSON": {"header": {"id": "fallback"}}})

    monkeypatch.setattr(ga.urllib.request, "urlopen", fake_urlopen)

    data = ga.get_game_data("401772799")

    assert data == {"header": {"id": "fallback"}}
    assert any("summary" in url for url in calls)
    assert any("playbyplay" in url for url in calls)


def test_derive_game_status_pregame_period_zero_is_pregame():
    status, game_clock = ga._derive_game_status({
        "type": {"state": "pre", "completed": False},
        "period": 0,
        "displayClock": "",
    })
    assert status == "pregame"
    assert game_clock is None


def test_derive_game_status_in_progress_uses_period_and_clock():
    status, game_clock = ga._derive_game_status({
        "type": {"state": "in", "completed": False},
        "period": 1,
        "displayClock": "15:00",
    })
    assert status == "in-progress"
    assert game_clock == {"quarter": 1, "clock": "15:00", "displayValue": "Q1 15:00"}


def test_derive_game_status_final_when_completed():
    status, game_clock = ga._derive_game_status({
        "type": {"state": "post", "completed": True},
        "period": 4,
        "displayClock": "0:00",
    })
    assert status == "final"
    assert game_clock is None


def test_competitive_penalty_yards_use_only_wp_selected_plays(monkeypatch):
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "AAA"}, "statistics": [
                {"name": "totalPenaltiesYards", "displayValue": "3-30"},
            ]},
            {"team": {"id": "2", "abbreviation": "BBB"}, "statistics": [
                {"name": "totalPenaltiesYards", "displayValue": "1-5"},
            ]},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0", "homeAway": "away", "team": {"abbreviation": "AAA"}},
            {"id": "2", "score": "0", "homeAway": "home", "team": {"abbreviation": "BBB"}},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [
            {"id": "competitive", "text": "Penalty on AAA, 10 yards", "type": {"text": "Rush"},
             "statYardage": 0, "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
             "penalty": {"yards": 10, "team": {"id": "1"}, "status": {"slug": "accepted"}}},
            {"id": "nullified", "text": "Interception returned for touchdown nullified by penalty on BBB, 5 yards, enforced at AAA 35 - No Play.",
             "type": {"text": "Interception Return Touchdown"}, "statYardage": 41,
             "start": {"team": {"id": "1"}, "down": 3, "distance": 7, "yardsToEndzone": 65},
             "end": {"team": {"id": "2"}, "yardsToEndzone": 60},
             "penalty": {"yards": 5, "team": {"id": "2"}, "status": {"slug": "accepted"}}},
            {"id": "transition", "text": "Runner gains 1 yard", "type": {"text": "Rush"},
             "statYardage": 1, "start": {"team": {"id": "1"}, "down": 1, "distance": 10}},
            {"id": "late", "text": "Penalty on AAA, 20 yards", "type": {"text": "Rush"},
             "statYardage": 0, "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
             "penalty": {"yards": 20, "team": {"id": "1"}, "status": {"slug": "accepted"}}},
        ]}]},
    }
    monkeypatch.setattr(ga, "get_game_data", lambda _game_id: game)
    monkeypatch.setattr(ga, "get_pregame_probabilities", lambda _game_id: (0.5, 0.5))
    monkeypatch.setattr(ga, "get_play_probabilities", lambda _game_id: {
        "competitive": {"homeWinPercentage": 0.5, "awayWinPercentage": 0.5},
        "nullified": {"homeWinPercentage": 0.5, "awayWinPercentage": 0.5},
        "transition": {"homeWinPercentage": 0.99, "awayWinPercentage": 0.01},
        "late": {"homeWinPercentage": 0.99, "awayWinPercentage": 0.01},
    })

    payload = ga.analyze_game("123")
    full = {row["Team"]: row for row in payload["advanced_table_full"]}
    competitive = {row["Team"]: row for row in payload["advanced_table"]}

    assert full["AAA"]["Penalty Yards"] == 30  # ESPN box-score total is preserved.
    assert full["BBB"]["Penalty Yards"] == 5
    assert competitive["AAA"]["Penalty Yards"] == 10  # The 20-yard late penalty is excluded.
    assert competitive["BBB"]["Penalty Yards"] == 5  # Accepted no-play penalty remains in scope.
    penalty_details = payload["expanded_details"]["1"]["Penalty Yards"]
    assert [entry["text"] for entry in penalty_details] == ["Penalty on AAA, 10 yards"]
    assert "accepted ESPN play-level" in payload["metric_scopes"]["Penalty Yards"]["competitive"]


def test_competitive_penalty_yards_are_unavailable_when_play_attribution_is_incomplete(monkeypatch):
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "AAA"}, "statistics": [
                {"name": "totalPenaltiesYards", "displayValue": "1-10"},
            ]},
            {"team": {"id": "2", "abbreviation": "BBB"}, "statistics": []},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0", "homeAway": "away", "team": {"abbreviation": "AAA"}},
            {"id": "2", "score": "0", "homeAway": "home", "team": {"abbreviation": "BBB"}},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "p1", "text": "Penalty accepted, 10 yards", "type": {"text": "Rush"},
            "statYardage": 0, "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
            "penalty": {"yards": 10, "status": {"slug": "accepted"}},
        }]}]},
    }
    monkeypatch.setattr(ga, "get_game_data", lambda _game_id: game)
    monkeypatch.setattr(ga, "get_pregame_probabilities", lambda _game_id: (0.5, 0.5))
    monkeypatch.setattr(ga, "get_play_probabilities", lambda _game_id: {
        "p1": {"homeWinPercentage": 0.5, "awayWinPercentage": 0.5},
    })

    payload = ga.analyze_game("123")
    competitive = {row["Team"]: row for row in payload["advanced_table"]}
    assert competitive["AAA"]["Penalty Yards"] is None
