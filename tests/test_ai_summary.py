import json
import sys
from types import ModuleType, SimpleNamespace

import pytest


def _install_fake_openai(monkeypatch, recorder):
    fake_openai = ModuleType("openai")

    class FakeOpenAI:
        def __init__(self, api_key=None):
            self.api_key = api_key

            def create(**kwargs):
                recorder["calls"] = recorder.get("calls", 0) + 1
                recorder.update(kwargs)
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(message=SimpleNamespace(content="FAKE SUMMARY"))
                    ]
                )

            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)


def test_generate_ai_summary_supplies_factors_and_measured_plays(monkeypatch, tmp_path):
    from api.lib import ai_summary

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5-test-summary-model")
    monkeypatch.setattr(ai_summary, "CACHE_DIR", str(tmp_path))

    recorder = {}
    _install_fake_openai(monkeypatch, recorder)

    payload = {
        "gameId": "401",
        "status": "in-progress",
        "team_meta": [
            {"id": "1", "abbr": "AAA", "name": "Team A", "homeAway": "away"},
            {"id": "2", "abbr": "BBB", "name": "Team B", "homeAway": "home"},
        ],
        "summary_table": [
            {"Team": "AAA", "Score": 7, "Total Yards": 0, "Drives": 0},
            {"Team": "BBB", "Score": 3, "Total Yards": 0, "Drives": 0},
        ],
        "advanced_table": [
            {"Team": "AAA", "Success Rate": 0.5, "Turnovers": 1, "Explosive Play Rate": .15,
             "Adjusted Yards Per Play": 6.0, "Points Per Trip (Inside 40)": 4,
             "Ave Start Field Pos": "Own 32", "Penalty Yards": 25, "Non-Offensive Points": 0},
            {"Team": "BBB", "Success Rate": 0.4, "Turnovers": 0, "Explosive Play Rate": .05,
             "Adjusted Yards Per Play": 4.0, "Points Per Trip (Inside 40)": 2,
             "Ave Start Field Pos": "Own 25", "Penalty Yards": 40, "Non-Offensive Points": 0},
        ],
        "source_gaps": [{"team": "AAA", "yards_gap": 5, "turnovers_gap": 0}],
        "expanded_details": {
            "1": {"Offensive Plays": [{}] * 20, "Drive Starts": [{}] * 5,
                  "Turnovers": [{"type": "Pass Interception Return"}],
                  "Points Per Trip (Inside 40)": [{}] * 2},
            "2": {"Offensive Plays": [{}] * 20, "Drive Starts": [{}] * 5,
                  "Points Per Trip (Inside 40)": [{}] * 2},
        },
        "plays": [
            {"id": "pass", "sourceTeam": "AAA", "type": "Pass", "text": "AAA 50-yard touchdown pass",
             "quarter": 3, "clock": "4:20", "homeWpBefore": .30, "homeWpAfter": .05,
             "homeWpDelta": -.25, "epa": 4.2,
             "badges": ["Top-10 league-week WP swing"]},
            {"id": "timeout", "type": "Timeout", "text": "Timeout AAA", "homeWpDelta": .35, "epa": None},
            {"id": "uncertain", "sourceTeam": "BBB", "type": "Rush", "text": "BBB rush",
             "homeWpDelta": .4, "wpAttributionUncertain": True, "epa": -3.1},
        ],
    }

    summary = ai_summary.generate_ai_summary(payload, game_data={}, probability_map={})
    assert summary == "FAKE SUMMARY"
    assert recorder.get("calls") == 1
    assert recorder["model"] == "gpt-5-test-summary-model"
    assert recorder["max_completion_tokens"] == 300
    assert recorder["reasoning_effort"] == "minimal"

    user_prompt = recorder["messages"][1]["content"]
    facts = json.loads(user_prompt.split('Game data:\n', 1)[1])
    assert len(facts['full_game_factors']) == 8
    factors = {row['factor']: row for row in facts['full_game_factors']}
    assert factors['Success Rate']['gap'] == 10
    assert factors['Success Rate']['large_completed_game_gap'] == 19
    assert factors['Success Rate']['advantage'] == 'AAA'
    assert factors['Ave Start Field Pos']['gap'] == 7
    assert factors['Penalty Yards']['advantage'] == 'AAA'
    assert 'Giveaways by each team' in factors['Turnovers']['meaning']
    assert factors['Turnovers']['turnover_types_by_team']['AAA'] == {"Pass Interception Return": 1}
    assert facts['top_play_candidates'][0]['id'] == 'pass'
    assert facts['top_play_candidates'][0]['wp_change_pp'] == 25
    assert facts['top_play_candidates'][0]['wp_benefited_team'] == 'AAA'
    assert facts['top_play_candidates'][0]['wp_before_percent'] == 70
    assert facts['top_play_candidates'][0]['wp_after_percent'] == 95
    assert facts['top_play_candidates'][0]['epa_for_team_at_start'] == 4.2
    assert facts['top_play_candidates'][0]['badges'] == ['Top-10 league-week WP swing']
    assert 'timeout' not in [play['id'] for play in facts['top_play_candidates']]
    assert next(play for play in facts['top_play_candidates'] if play['id'] == 'uncertain')['wp_change_pp'] is None
    assert 'do not mention individual plays' not in user_prompt.lower()
    assert 'one or two conversational sentences' in user_prompt
    assert 'Lead with the strongest advantages for the team ahead' in user_prompt
    assert 'Check every comparison against the data' in user_prompt


def test_generate_ai_summary_uses_luna_with_supported_reasoning_effort(monkeypatch, tmp_path):
    from api.lib import ai_summary

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.6-luna")
    monkeypatch.setattr(ai_summary, "CACHE_DIR", str(tmp_path))
    recorder = {}
    _install_fake_openai(monkeypatch, recorder)

    payload = {
        "gameId": "401", "status": "in-progress",
        "team_meta": [
            {"id": "1", "abbr": "AAA", "name": "Team A", "homeAway": "away"},
            {"id": "2", "abbr": "BBB", "name": "Team B", "homeAway": "home"},
        ],
        "summary_table": [{"Team": "AAA", "Score": 7}, {"Team": "BBB", "Score": 3}],
        "advanced_table": [], "expanded_details": {},
    }

    assert ai_summary.generate_ai_summary(payload, {}, {}) == "FAKE SUMMARY"
    assert recorder["model"] == "gpt-5.6-luna"
    assert recorder["reasoning_effort"] == "low"


def test_generate_ai_summary_uses_cache(monkeypatch, tmp_path):
    from api.lib import ai_summary

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ai_summary, "CACHE_DIR", str(tmp_path))

    recorder = {}
    _install_fake_openai(monkeypatch, recorder)

    payload = {
        "gameId": "401",
        "status": "final",
        "team_meta": [
            {"id": "1", "abbr": "AAA", "name": "Team A", "homeAway": "away"},
            {"id": "2", "abbr": "BBB", "name": "Team B", "homeAway": "home"},
        ],
        "summary_table": [
            {"Team": "AAA", "Score": 7, "Total Yards": 0, "Drives": 0},
            {"Team": "BBB", "Score": 3, "Total Yards": 0, "Drives": 0},
        ],
        "advanced_table": [],
        "expanded_details": {},
    }

    assert ai_summary.generate_ai_summary(payload, game_data={}, probability_map={}) == "FAKE SUMMARY"
    assert recorder.get("calls") == 1

    # Second call should use cache and not call the model again.
    assert ai_summary.generate_ai_summary(payload, game_data={}, probability_map={}) == "FAKE SUMMARY"
    assert recorder.get("calls") == 1


def test_summary_validation_rejects_wrong_takeaways_and_overlong_text():
    from api.lib.ai_summary import _valid_summary

    payload = {"advanced_table_full": [
        {"Team": "BAL", "Turnovers": 3},
        {"Team": "CLE", "Turnovers": 1},
    ]}
    assert not _valid_summary("BAL rode 3 takeaways despite 3 giveaways.", payload)
    assert _valid_summary("BAL overcame 3 giveaways and took the ball away once.", payload)
    assert not _valid_summary("A" * 501, payload)


def test_summary_validation_checks_team_names_and_spelled_numbers():
    from api.lib.ai_summary import _valid_summary

    payload = {
        "team_meta": [
            {"abbr": "CIN", "name": "Cincinnati Bengals"},
            {"abbr": "PIT", "name": "Pittsburgh Steelers"},
        ],
        "advanced_table_full": [
            {"Team": "CIN", "Turnovers": 1},
            {"Team": "PIT", "Turnovers": 2},
        ],
    }
    assert not _valid_summary("The Steelers' two takeaways won the game.", payload)
    assert _valid_summary("The Steelers' one takeaway offset two giveaways.", payload)
    assert _valid_summary("The Steelers' one takeaway included a Q2 interception.", payload)


def test_summary_cache_key_changes_with_facts_or_model_at_same_score(monkeypatch):
    from api.lib.ai_summary import get_cache_key

    first = {"status": "in-progress", "advanced_table_full": [
        {"Team": "BAL", "Turnovers": 1}, {"Team": "CLE", "Turnovers": 0},
    ]}
    second = {"status": "in-progress", "advanced_table_full": [
        {"Team": "BAL", "Turnovers": 2}, {"Team": "CLE", "Turnovers": 0},
    ]}
    assert get_cache_key("401", 14, 7, first) != get_cache_key("401", 14, 7, second)
    monkeypatch.setenv('OPENAI_MODEL', 'gpt-5-mini')
    old_model_key = get_cache_key("401", 14, 7, first)
    monkeypatch.setenv('OPENAI_MODEL', 'gpt-5.6-luna')
    assert get_cache_key("401", 14, 7, first) != old_model_key


def test_generate_ai_summary_retries_an_overlong_response(monkeypatch, tmp_path):
    from api.lib import ai_summary

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ai_summary, "CACHE_DIR", str(tmp_path))
    calls = []

    class FakeOpenAI:
        def __init__(self, api_key=None):
            def create(**kwargs):
                calls.append(kwargs)
                content = "A" * 501 if len(calls) == 1 else "AAA beat BBB 7-3."
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    fake_openai = ModuleType("openai")
    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    payload = {
        "gameId": "401", "status": "final",
        "team_meta": [
            {"id": "1", "abbr": "AAA", "name": "Team A", "homeAway": "away"},
            {"id": "2", "abbr": "BBB", "name": "Team B", "homeAway": "home"},
        ],
        "summary_table": [
            {"Team": "AAA", "Score": 7},
            {"Team": "BBB", "Score": 3},
        ],
        "advanced_table": [], "expanded_details": {},
    }

    assert ai_summary.generate_ai_summary(payload, {}, {}) == "AAA beat BBB 7-3."
    assert len(calls) == 2
    assert "under 500 characters" in calls[1]["messages"][-1]["content"]
    assert "one or two conversational sentences" in calls[1]["messages"][-1]["content"]
