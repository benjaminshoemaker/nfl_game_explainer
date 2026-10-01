import os
import sys

import pytest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from lib import cache  # noqa: E402


def test_rebuild_expanded_details_includes_drive_starts():
    meta = {
        "home_team": {"id": "1", "abbr": "AAA", "name": "A Team"},
        "away_team": {"id": "2", "abbr": "BBB", "name": "B Team"},
    }
    plays = {
        "drive_starts": [
            {
                "drive_team": "AAA",
                "quarter": 1,
                "clock": "15:00",
                "text": "Kickoff return to AAA 25.",
                "type": "Kickoff",
                "start_pos": "AAA 25",
                "start_home_wp": 0.5,
                "start_away_wp": 0.5,
            }
        ],
        "plays": [],
    }

    expanded = cache._rebuild_expanded_details_from_cache(plays, meta, 0.975)
    assert len(expanded["1"]["Drive Starts"]) == 1
    assert expanded["1"]["Drive Starts"][0]["start_pos"] == "AAA 25"


@pytest.mark.parametrize("play_abbr, metadata_abbr", [
    ("CLV", "CLE"), ("BLT", "BAL"), ("HST", "HOU"),
    ("ARZ", "ARI"), ("WAS", "WSH"), ("LA", "LAR"),
    ("JAC", "JAX"),
])
def test_cache_recovery_uses_shared_team_aliases(play_abbr, metadata_abbr):
    raw = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": metadata_abbr}},
            {"team": {"id": "2", "abbreviation": "OPP"}},
        ]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "recovery", "text": f"Runner FUMBLES, RECOVERED by {play_abbr}-Player at {play_abbr} 20.",
            "type": {"text": "Rush"}, "statYardage": 0,
            "end": {"possessionText": f"{play_abbr} 20"},
        }]}]},
    }
    row = cache.build_cache_plays(raw, {}, (0.5, 0.5))["plays"][0]
    assert row["is_turnover"] is False
    assert row["end_pos"] == f"{metadata_abbr} 20"


def test_cache_unknown_recovery_abbreviation_is_explicit():
    raw = {
        "boxscore": {"teams": [
            {"team": {"id": "1", "abbreviation": "CLE"}},
            {"team": {"id": "2", "abbreviation": "CAR"}},
        ]},
        "drives": {"previous": [{"team": {"id": "1"}, "plays": [{
            "id": "recovery", "text": "Runner FUMBLES, RECOVERED by XYZ-Player at CLE 20.",
            "type": {"text": "Rush"}, "statYardage": 0,
        }]}]},
    }
    row = cache.build_cache_plays(raw, {}, (0.5, 0.5))["plays"][0]
    assert row["is_turnover"] is False
    assert row["unresolved_team_abbr"] == "XYZ"
