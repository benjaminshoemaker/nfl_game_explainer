"""Guard the published EP model's input feature order."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.nflfastr_ep_model import model_features


def test_modern_retractable_home_fourth_down_features():
    features = model_features({
        "half_seconds_remaining": 300, "yardline_100": 39,
        "home": 1, "roof": "retractable", "ydstogo": 8, "down": 4,
        "posteam_timeouts_remaining": 2, "defteam_timeouts_remaining": 1,
    })
    assert features == [300, 39, 1, 1, 0, 0, 8, 0, 0, 0, 0, 1,
                        0, 0, 0, 1, 2, 1]
