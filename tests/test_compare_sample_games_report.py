import json
import os
import sys
from pathlib import Path

import pytest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import compare_sample_games_report as report  # noqa: E402


def test_load_raw_game_data_source_cache_reads_from_cache(monkeypatch, tmp_path: Path):
    cache_dir = tmp_path / "pbp_cache"
    cache_dir.mkdir()
    (cache_dir / "123.json").write_text(json.dumps({"header": {"id": "123"}}))

    def fail_network(_game_id):
        raise AssertionError("Network fetch should not be called")

    monkeypatch.setattr(report, "get_game_data", fail_network)

    data, source = report.load_raw_game_data("123", source="cache", cache_dir=cache_dir)
    assert data == {"header": {"id": "123"}}
    assert source == "cache"


def test_load_raw_game_data_source_auto_uses_cache_first(monkeypatch, tmp_path: Path):
    cache_dir = tmp_path / "pbp_cache"
    cache_dir.mkdir()
    (cache_dir / "123.json").write_text(json.dumps({"header": {"id": "cached"}}))

    def fail_network(_game_id):
        raise AssertionError("Network fetch should not be called")

    monkeypatch.setattr(report, "get_game_data", fail_network)

    data, source = report.load_raw_game_data("123", source="auto", cache_dir=cache_dir)
    assert data == {"header": {"id": "cached"}}
    assert source == "cache"


def test_load_raw_game_data_source_auto_falls_back_to_network(monkeypatch, tmp_path: Path):
    cache_dir = tmp_path / "pbp_cache"
    cache_dir.mkdir()

    calls = []

    def fake_get_game_data(game_id):
        calls.append(game_id)
        return {"header": {"id": game_id}}

    monkeypatch.setattr(report, "get_game_data", fake_get_game_data)

    data, source = report.load_raw_game_data("123", source="auto", cache_dir=cache_dir)
    assert data == {"header": {"id": "123"}}
    assert source == "network"
    assert calls == ["123"]


def test_load_raw_game_data_source_cache_missing_raises(tmp_path: Path):
    cache_dir = tmp_path / "pbp_cache"
    cache_dir.mkdir()

    with pytest.raises(FileNotFoundError):
        report.load_raw_game_data("missing", source="cache", cache_dir=cache_dir)


def test_extract_espn_official_team_stats_returns_yards_and_turnovers():
    raw_data = {
        "header": {
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "away", "team": {"abbreviation": "JAX"}, "score": "17"},
                        {"homeAway": "home", "team": {"abbreviation": "TEN"}, "score": "21"},
                    ]
                }
            ]
        },
        "boxscore": {
            "teams": [
                {
                    "team": {"abbreviation": "JAX"},
                    "statistics": [
                        {"name": "totalYards", "displayValue": "312"},
                        {"name": "turnovers", "displayValue": "1"},
                        {"name": "totalPenaltiesYards", "displayValue": "5-45"},
                    ],
                },
                {
                    "team": {"abbreviation": "TEN"},
                    "statistics": [
                        {"name": "totalYards", "displayValue": "289"},
                        {"name": "turnovers", "displayValue": "0"},
                        {"name": "totalPenaltiesYards", "displayValue": "8-72"},
                    ],
                },
            ]
        },
    }

    espn_stats, meta = report.extract_espn_official_team_stats(raw_data)

    assert meta == {"away": "JAX", "home": "TEN"}
    assert espn_stats["JAX"]["Total Yards"] == 312
    assert espn_stats["JAX"]["Turnovers"] == 1
    assert espn_stats["JAX"]["Penalty Yards"] == 45
    assert espn_stats["JAX"]["Score"] == 17
    assert espn_stats["TEN"]["Total Yards"] == 289
    assert espn_stats["TEN"]["Turnovers"] == 0
    assert espn_stats["TEN"]["Penalty Yards"] == 72
    assert espn_stats["TEN"]["Score"] == 21


def test_print_terminal_report_table_includes_headers(capsys):
    lines = [
        report.TeamLine(
            game_id="401",
            team="JAX",
            home_away="away",
            opponent="TEN",
            espn_total_yards=300,
            windelta_total_yards=310,
            yards_delta=10,
            espn_turnovers=1,
            windelta_turnovers=1,
            turnovers_delta=0,
            espn_penalty_yards=45,
            windelta_penalty_yards=45,
            penalty_yards_delta=0,
            windelta_source="test",
        ),
        report.TeamLine(
            game_id="401",
            team="TEN",
            home_away="home",
            opponent="JAX",
            espn_total_yards=280,
            windelta_total_yards=280,
            yards_delta=0,
            espn_turnovers=0,
            windelta_turnovers=0,
            turnovers_delta=0,
            espn_penalty_yards=72,
            windelta_penalty_yards=70,
            penalty_yards_delta=-2,
            windelta_source="test",
        ),
    ]

    report.print_terminal_report(lines, "mismatches", fmt="table")
    out_lines = capsys.readouterr().out.splitlines()
    assert out_lines, "Expected some terminal output"
    assert "game_id" in out_lines[0]
    assert "matchup" in out_lines[0]
    assert "status" in out_lines[0]
