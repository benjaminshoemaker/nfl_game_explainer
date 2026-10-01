import json
import os
import sys
import urllib.error

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from lib import game_analysis as ga
from lib.nfl_core import process_game_stats


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


def test_get_play_probabilities_rejects_partial_paginated_feed(monkeypatch):
    def fake_urlopen(req, timeout=15):
        if "page=2" in req.full_url:
            raise urllib.error.URLError("second page unavailable")
        return FakeResponse({
            "pageCount": 2,
            "items": [{"play": {"$ref": "https://example.com/plays/1"},
                       "homeWinPercentage": 0.6, "awayWinPercentage": 0.4}],
        })

    monkeypatch.setattr(ga.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="page 2"):
        ga.get_play_probabilities("401")


def test_analyze_game_labels_missing_win_probability_as_unavailable(monkeypatch):
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "SEA"}, "statistics": []},
            {"team": {"id": "2", "abbreviation": "LAR"}, "statistics": []},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0", "homeAway": "home", "team": {"abbreviation": "SEA"}},
            {"id": "2", "score": "0", "homeAway": "away", "team": {"abbreviation": "LAR"}},
        ]}]},
        "drives": {"previous": []},
    }
    monkeypatch.setattr(ga, "get_game_data", lambda _game_id: game)
    monkeypatch.setattr(ga, "get_pregame_probabilities", lambda _game_id: (0.5, 0.5))
    monkeypatch.setattr(ga, "get_play_probabilities", lambda _game_id: {})

    payload = ga.analyze_game("401")
    assert payload["wp_filter"]["enabled"] is False
    assert "unavailable" in payload["wp_filter"]["description"].lower()
    assert payload["advanced_table"] == payload["advanced_table_full"]


def test_advanced_output_separates_full_game_official_and_adjusted_ypp(monkeypatch):
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "AAA"}, "statistics": [
                {"name": "yardsPerPlay", "displayValue": "7.6"},
            ]},
            {"team": {"id": "2", "abbreviation": "BBB"}, "statistics": []},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0", "homeAway": "away", "team": {"abbreviation": "AAA"}},
            {"id": "2", "score": "0", "homeAway": "home", "team": {"abbreviation": "BBB"}},
        ]}]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "1", "text": "Runner gains 5 yards", "type": {"text": "Rush"},
            "statYardage": 5, "start": {"team": {"id": "1"}, "down": 1, "distance": 10},
        }]}]},
    }
    monkeypatch.setattr(ga, "get_game_data", lambda _game_id: game)
    monkeypatch.setattr(ga, "get_pregame_probabilities", lambda _game_id: (0.5, 0.5))
    monkeypatch.setattr(ga, "get_play_probabilities", lambda _game_id: {
        "1": {"homeWinPercentage": 0.5, "awayWinPercentage": 0.5},
    })

    payload = ga.analyze_game("123", debug=True)
    full = next(row for row in payload["advanced_table_full"] if row["Team"] == "AAA")
    competitive = next(row for row in payload["advanced_table"] if row["Team"] == "AAA")
    assert full["Official Yards Per Play (Full Game)"] == 7.6
    assert full["Adjusted Yards Per Play"] == 5.0
    assert "Yards Per Play" not in full
    assert "Official Yards Per Play (Full Game)" not in competitive
    assert competitive["Adjusted Yards Per Play"] == 5.0
    assert "Official Yards Per Play (Full Game)" not in payload["debug"]["statsCompetitive"][0]
    assert payload["debug"]["statsFull"][0]["Official Yards Per Play (Full Game)"] == 7.6


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
            "id": "p1", "text": "PENALTY on XYZ, 10 yards", "type": {"text": "Rush"},
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
    assert competitive["BBB"]["Penalty Yards"] is None
    for team_id in ("1", "2"):
        entry = payload["expanded_details"][team_id]["Penalty Yards"][0]
        assert entry["team_attribution_note"] == "Committing team unavailable"


def test_competitive_penalties_resolve_was_alias_and_kickoff_placements(monkeypatch):
    def penalty_play(pid, text, penalty_type, yards=None):
        penalty = {"type": {"slug": penalty_type}, "status": {"slug": "accepted"}}
        if yards is not None:
            penalty["yards"] = yards
        return {
            "id": pid, "text": text, "type": {"text": "Kickoff" if "kickoff" in penalty_type else "Penalty"},
            "start": {"team": {"id": "26"}, "down": 0}, "penalty": penalty,
            "statYardage": 25 if "kickoff" in penalty_type else 0,
        }

    game = {
        "boxscore": {"teams": [
            {"team": {"id": "26", "abbreviation": "SEA"}, "statistics": [
                {"name": "totalPenaltiesYards", "displayValue": "2-5"}]},
            {"team": {"id": "28", "abbreviation": "WSH"}, "statistics": [
                {"name": "totalPenaltiesYards", "displayValue": "2-5"}]},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "26", "score": "0", "homeAway": "away", "team": {"abbreviation": "SEA"}},
            {"id": "28", "score": "0", "homeAway": "home", "team": {"abbreviation": "WSH"}},
        ]}]},
        "drives": {"previous": [{"team": {"id": "26"}, "plays": [
            penalty_play("was-five", "PENALTY on WAS-J.Bates, False Start, 5 yards, enforced at WAS 47 - No Play.", "false-start", 5),
            penalty_play("sea-five", "PENALTY on SEA-A.Barner, False Start, 5 yards, enforced at SEA 21 - No Play.", "false-start", 5),
            penalty_play("was-kick", "Kick out of bounds.PENALTY on WAS-D.Stevens, Kickoff Out of Bounds, placed at SEA 40.", "kickoff-out-of-bounds"),
            penalty_play("sea-kick", "Short kick.PENALTY on SEA-J.Myers, Kickoff Short of Landing Zone, placed at WAS 40.", "kickoff-short-of-landing-zone"),
        ]}]},
    }
    monkeypatch.setattr(ga, "get_game_data", lambda _game_id: game)
    monkeypatch.setattr(ga, "get_pregame_probabilities", lambda _game_id: (0.5, 0.5))
    monkeypatch.setattr(ga, "get_play_probabilities", lambda _game_id: {
        pid: {"homeWinPercentage": 0.5, "awayWinPercentage": 0.5}
        for pid in ("was-five", "sea-five", "was-kick", "sea-kick")
    })

    payload = ga.analyze_game("401872955")
    competitive = {row["Team"]: row for row in payload["advanced_table"]}
    assert competitive["SEA"]["Penalty Yards"] == 5
    assert competitive["WSH"]["Penalty Yards"] == 5
    sea_details = payload["expanded_details"]["26"]["Penalty Yards"]
    wsh_details = payload["expanded_details"]["28"]["Penalty Yards"]
    assert [row["yards"] for row in sea_details] == [-5, 0]
    assert [row["yards"] for row in wsh_details] == [-5, 0]
    assert sea_details[1]["yardage_note"] == "0 penalty yards charged; ball placed at WAS 40"
    assert wsh_details[1]["yardage_note"] == "0 penalty yards charged; ball placed at SEA 40"


def test_game_metadata_uses_boxscore_abbreviation_for_same_team_id(monkeypatch):
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "5", "abbreviation": "CLE"}},
            {"team": {"id": "29", "abbreviation": "CAR"}},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "5", "score": "0", "homeAway": "home", "team": {"abbreviation": "CLV", "displayName": "Cleveland Browns"}},
            {"id": "29", "score": "0", "homeAway": "away", "team": {"abbreviation": "CAR", "displayName": "Carolina Panthers"}},
        ]}]},
        "drives": {"previous": []},
    }
    monkeypatch.setattr(ga, "get_game_data", lambda _game_id: game)
    monkeypatch.setattr(ga, "get_pregame_probabilities", lambda _game_id: (0.5, 0.5))
    monkeypatch.setattr(ga, "get_play_probabilities", lambda _game_id: {})

    payload = ga.analyze_game("game")
    assert [team["abbr"] for team in payload["team_meta"]] == ["CLE", "CAR"]
    assert payload["label"] == "CAR_at_CLE_game"


def test_unknown_penalty_yards_remain_explicit_and_null_only_own_team():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "AAA"}},
            {"team": {"id": "2", "abbreviation": "BBB"}},
        ]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "unknown", "text": "PENALTY on AAA, unknown enforcement.",
            "type": {"text": "Penalty"}, "start": {"team": {"id": "1"}, "down": 1},
            "penalty": {"type": {"slug": "other"}, "status": {"slug": "accepted"}},
        }]}]},
    }
    stats, details = process_game_stats(game, expanded=True, probability_map={
        "unknown": {"homeWinPercentage": 0.5, "awayWinPercentage": 0.5},
    }, penalty_yards_from_plays=True)
    by_team = {row["Team"]: row for row in stats}
    assert by_team["AAA"]["Penalty Yards"] is None
    assert by_team["BBB"]["Penalty Yards"] == 0
    assert details["1"]["Penalty Yards"][0]["yards"] is None
    assert details["1"]["Penalty Yards"][0]["yardage_note"] == "Penalty yards unavailable"


def test_final_api_uses_espn_totals_but_exposes_play_by_play_gaps(monkeypatch):
    game = {
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
        "header": {"competitions": [{
            "status": {"type": {"state": "post", "completed": True}},
            "competitors": [
                {"id": "1", "score": "0", "homeAway": "away", "team": {"abbreviation": "TEN"}},
                {"id": "2", "score": "0", "homeAway": "home", "team": {"abbreviation": "ARI"}},
            ],
        }]},
        "drives": {"previous": []},
    }
    monkeypatch.setattr(ga, "get_game_data", lambda _game_id: game)
    monkeypatch.setattr(ga, "get_pregame_probabilities", lambda _game_id: (0.5, 0.5))
    monkeypatch.setattr(ga, "get_play_probabilities", lambda _game_id: {})

    payload = ga.analyze_game("401")
    full = {row["Team"]: row for row in payload["advanced_table_full"]}
    assert full["TEN"]["Total Yards"] == 327
    assert full["TEN"]["Turnovers"] == 2
    assert full["ARI"]["Total Yards"] == 360
    assert full["ARI"]["Turnovers"] == 3
    assert {gap["team"] for gap in payload["source_gaps"]} == {"TEN", "ARI"}
    assert payload["source_gaps"][0]["turnovers_gap"] == 2


def test_debug_rows_explain_play_contributions_and_skips():
    game = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "SEA"}, "statistics": []},
            {"team": {"id": "2", "abbreviation": "WAS"}, "statistics": []},
        ]},
        "header": {"competitions": [{"competitors": [
            {"id": "1", "score": "0"}, {"id": "2", "score": "0"},
        ]}]},
        "drives": {"previous": [{
            "team": {"id": "1"}, "start": {"yardsToEndzone": 75},
            "plays": [
                {"id": "10", "text": "Run up the middle for 5 yards", "type": {"text": "Rush"},
                 "statYardage": 5, "start": {"down": 1, "distance": 10, "yardsToEndzone": 75}},
                {"id": "11", "text": "Timeout Seattle", "type": {"text": "Timeout"}},
            ],
        }]},
    }
    debug_rows = []
    rows, _ = process_game_stats(game, expanded=True, debug_rows=debug_rows)

    assert rows[0]["Success Rate"] == 1.0
    assert debug_rows[0]["statDeltas"]["SEA"]["Offensive Yards"] == 5
    assert debug_rows[0]["statDeltas"]["SEA"]["Successful Plays"] == 1
    assert debug_rows[0]["classification"] == "run"
    assert debug_rows[0]["raw"]["id"] == "10"
    assert debug_rows[1]["excludedReason"] == "timeout_or_period_end"
    assert debug_rows[1]["statDeltas"] == {}


def test_analyze_game_includes_raw_sources_only_when_debug_requested(monkeypatch):
    game = {
        "boxscore": {"teams": []},
        "header": {"week": 1, "season": {"type": 2}, "competitions": []},
        "drives": {"previous": []},
    }
    monkeypatch.setattr(ga, "get_game_data", lambda _game_id: game)
    monkeypatch.setattr(ga, "get_pregame_probabilities", lambda _game_id: (0.6, 0.4))
    monkeypatch.setattr(ga, "get_play_probabilities", lambda _game_id: {"p": {"homeWinPercentage": 0.7}})

    normal = ga.analyze_game("401")
    debug = ga.analyze_game("401", debug=True)

    assert "debug" not in normal
    assert debug["debug"]["sources"]["espnSummary"] == game
    assert debug["debug"]["sources"]["playProbabilities"]["p"]["homeWinPercentage"] == 0.7
    assert debug["debug"]["sources"]["pregameProbabilities"]["home"] == 0.6
    assert debug["debug"]["plays"] == []
