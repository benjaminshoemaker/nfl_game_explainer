"""Load nflfastR's published expected-points XGBoost model for research.

The pinned fastrmodels R data object contains a raw XGBoost UBJSON vector.
Its checksum makes the small R-serialization extraction below specific to
the inspected artifact. This module is not used by the deployed application.
"""

import hashlib
import lzma
import urllib.request
from pathlib import Path

import numpy as np
import xgboost as xgb


MODEL_URL = "https://raw.githubusercontent.com/nflverse/fastrmodels/master/data/ep_model.rda"
MODEL_SHA256 = "fa45093d478fdd4534fa48860678ff99d597a67c340821db075c47fdab9102af"
MODEL_CACHE = Path("/tmp/nfl_game_explainer_nflfastr_ep_model.rda")
EP_WEIGHTS = np.asarray([7, -7, 3, -3, 2, -2, 0], dtype=float)


def load_model():
    if not MODEL_CACHE.exists():
        urllib.request.urlretrieve(MODEL_URL, MODEL_CACHE)
    data = MODEL_CACHE.read_bytes()
    if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
        raise RuntimeError("nflfastR EP model artifact changed; inspect before repinning")
    serialized = lzma.decompress(data)
    if not serialized.startswith(b"RDX3\nX\n") or serialized[52:56] != b"\x00\x00\x00\x18":
        raise RuntimeError("unexpected fastrmodels R serialization")
    size = int.from_bytes(serialized[56:60], "big")
    raw = serialized[60:60 + size]
    if len(raw) != size or not raw.startswith(b"{L"):
        raise RuntimeError("unexpected fastrmodels XGBoost vector")
    model = xgb.Booster()
    model.load_model(bytearray(raw))
    if model.num_features() != 18:
        raise RuntimeError("unexpected nflfastR EP feature count")
    return model


def model_features(state):
    """Match nflfastR ep_model_select column order for a modern season."""
    down = state.get("down")
    roof = state.get("roof")
    required = (
        "half_seconds_remaining", "yardline_100", "home", "ydstogo",
        "posteam_timeouts_remaining", "defteam_timeouts_remaining",
    )
    if down not in (1, 2, 3, 4) or roof not in ("outdoors", "dome", "retractable"):
        return None
    if any(state.get(key) is None for key in required):
        return None
    if not (0 <= state["half_seconds_remaining"] <= 1800 and
            1 <= state["yardline_100"] <= 99 and
            1 <= state["ydstogo"] <= 40 and
            0 <= state["posteam_timeouts_remaining"] <= 3 and
            0 <= state["defteam_timeouts_remaining"] <= 3):
        return None
    return [
        state["half_seconds_remaining"], state["yardline_100"], state["home"],
        int(roof == "retractable"), int(roof == "dome"), int(roof == "outdoors"),
        state["ydstogo"], 0, 0, 0, 0, 1,
        *[int(down == value) for value in (1, 2, 3, 4)],
        state["posteam_timeouts_remaining"], state["defteam_timeouts_remaining"],
    ]


def predict_ep(model, state):
    features = model_features(state)
    if features is None:
        return None
    probabilities = model.predict(xgb.DMatrix(np.asarray([features], dtype=float)))[0]
    return float(probabilities @ EP_WEIGHTS)
