"""Keep unit tests independent of ESPN's venue endpoint."""

import pytest


@pytest.fixture(autouse=True)
def no_live_venue_requests(monkeypatch):
    from api.lib import epa

    monkeypatch.setattr(epa, '_venue_roof', lambda _venue_id: 'outdoors')
