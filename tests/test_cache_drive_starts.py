import os
import sys


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

