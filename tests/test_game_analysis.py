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
