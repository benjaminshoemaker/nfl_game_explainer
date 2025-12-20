import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import local_server


def test_parse_scoreboard_params_valid():
    week, seasontype = local_server._parse_scoreboard_params({"week": ["15"], "seasontype": ["2"]})
    assert week == 15
    assert seasontype == 2


def test_parse_scoreboard_params_invalid_week():
    week, seasontype = local_server._parse_scoreboard_params({"week": ["0"], "seasontype": ["2"]})
    assert week is None
    assert seasontype == 2
