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


def test_generate_ai_summary_uses_team_keyed_expanded_details(monkeypatch, tmp_path):
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
            {"Team": "AAA", "Success Rate": 0.5, "Turnovers": 1, "Explosive Plays": 2},
            {"Team": "BBB", "Success Rate": 0.4, "Turnovers": 0, "Explosive Plays": 1},
        ],
        "source_gaps": [{"team": "AAA", "yards_gap": 0, "turnovers_gap": 1}],
        # Team-keyed shape (this is what the API returns)
        "expanded_details": {
            "1": {
                "Turnovers": [{"text": "Interception on AAA"}],
                "Explosive Plays": [{"text": "AAA 50-yard pass"}],
            },
            "2": {
                "Turnovers": [{"text": "Fumble by BBB"}],
                "Explosive Plays": [{"text": "BBB 20-yard run"}],
            },
        },
    }

    summary = ai_summary.generate_ai_summary(payload, game_data={}, probability_map={})
    assert summary == "FAKE SUMMARY"
    assert recorder.get("calls") == 1
    assert recorder["model"] == "gpt-5-test-summary-model"
    assert recorder["max_completion_tokens"] == 300
    assert recorder["reasoning_effort"] == "minimal"

    # Verify prompt includes key plays with team abbreviations (AAA/BBB), not team ids.
    user_prompt = recorder["messages"][1]["content"]
    assert "Turnover (AAA): Q?" in user_prompt
    assert "Interception on AAA" in user_prompt
    assert "Turnover (BBB): Q?" in user_prompt
    assert "Fumble by BBB" in user_prompt
    assert "Explosive (AAA): Q?" in user_prompt
    assert "AAA 50-yard pass" in user_prompt
    assert "Explosive (BBB): Q?" in user_prompt
    assert "BBB 20-yard run" in user_prompt
    assert "1 giveaways, 0 takeaways" in user_prompt
    assert "AAA" in user_prompt
    assert "do not invent missing play details" in user_prompt.lower()


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
    assert not _valid_summary("A" * 281, payload)


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
    assert not _valid_summary("The Steelers' two takeaways included a Q2 interception.", payload)


def test_summary_cache_key_changes_with_facts_at_same_score():
    from api.lib.ai_summary import get_cache_key

    first = {"status": "in-progress", "advanced_table_full": [
        {"Team": "BAL", "Turnovers": 1}, {"Team": "CLE", "Turnovers": 0},
    ]}
    second = {"status": "in-progress", "advanced_table_full": [
        {"Team": "BAL", "Turnovers": 2}, {"Team": "CLE", "Turnovers": 0},
    ]}
    assert get_cache_key("401", 14, 7, first) != get_cache_key("401", 14, 7, second)


def test_generate_ai_summary_retries_an_overlong_response(monkeypatch, tmp_path):
    from api.lib import ai_summary

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ai_summary, "CACHE_DIR", str(tmp_path))
    calls = []

    class FakeOpenAI:
        def __init__(self, api_key=None):
            def create(**kwargs):
                calls.append(kwargs)
                content = "A" * 281 if len(calls) == 1 else "AAA beat BBB 7-3."
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
    assert "under 220 characters" in calls[1]["messages"][-1]["content"]
