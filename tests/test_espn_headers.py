import os
import sys


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

import scoreboard
import game_compare
from lib import game_analysis


def test_scoreboard_headers_do_not_impersonate_a_browser():
    assert "User-Agent" not in scoreboard.ESPN_REQUEST_HEADERS


def test_game_analysis_headers_do_not_impersonate_a_browser():
    assert "User-Agent" not in game_analysis.ESPN_REQUEST_HEADERS


def test_cli_headers_do_not_impersonate_a_browser():
    assert "User-Agent" not in game_compare.ESPN_REQUEST_HEADERS
