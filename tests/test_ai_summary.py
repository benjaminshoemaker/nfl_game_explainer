import sys
from types import ModuleType, SimpleNamespace

import pytest


def _install_fake_openai(monkeypatch, recorder):
    fake_openai = ModuleType("openai")

    class FakeOpenAI:
        def __init__(self, api_key=None):
            self.api_key = api_key

            def create(model, messages, max_tokens, temperature):
                recorder["calls"] = recorder.get("calls", 0) + 1
                recorder["model"] = model
                recorder["messages"] = messages
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

    # Verify prompt includes key plays with team abbreviations (AAA/BBB), not team ids.
    user_prompt = recorder["messages"][1]["content"]
    assert "Turnover (AAA): Interception on AAA" in user_prompt
    assert "Turnover (BBB): Fumble by BBB" in user_prompt
    assert "Explosive (AAA): AAA 50-yard pass" in user_prompt
    assert "Explosive (BBB): BBB 20-yard run" in user_prompt


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

