import json
import os
import sys

import pytest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import compare_season_games_report as report  # noqa: E402


def test_extract_event_ids_from_core_schedule_parses_refs_and_ids():
    payload = {
        "items": [
            {"$ref": "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/401772896?lang=en&region=us"},
            {"id": "401772900"},
        ]
    }
    assert report.extract_event_ids_from_core_schedule(payload) == ["401772896", "401772900"]


def test_load_game_ids_dedup_and_ignores_comments(tmp_path):
    path = tmp_path / "ids.txt"
    path.write_text(
        "\n".join(
            [
                "# comment",
                "401,foo",
                "401",
                "",
                "402",
            ]
        )
        + "\n"
    )
    assert report.load_game_ids(path) == ["401", "402"]


def test_fetch_season_game_ids_max_week_applies_to_regular_season_only():
    calls = []

    def fake_fetch_week_ids(season: int, season_type: int, week: int):
        calls.append((season, season_type, week))
        return [f"{season_type}-{week}"]

    ids = report.fetch_season_game_ids(
        2025,
        season_types=(2, 3),
        max_week=3,
        max_weeks_by_type={2: 18, 3: 5},
        fetch_week_ids=fake_fetch_week_ids,
    )

    # Regular season capped at week 3; postseason still uses max_weeks_by_type (5).
    assert calls[:3] == [(2025, 2, 1), (2025, 2, 2), (2025, 2, 3)]
    assert (2025, 2, 4) not in calls
    assert (2025, 3, 5) in calls
    assert ids[0] == "2-1"


def _game(game_id: str, away_to: int, home_to: int, away_yd: int, home_yd: int) -> report.GameRecon:
    away = report.TeamLine(
        game_id=game_id,
        team="AWY",
        home_away="away",
        opponent="HME",
        espn_total_yards=0,
        windelta_total_yards=away_yd,
        yards_delta=away_yd,
        espn_turnovers=0,
        windelta_turnovers=away_to,
        turnovers_delta=away_to,
        espn_penalty_yards=0,
        windelta_penalty_yards=0,
        penalty_yards_delta=0,
        windelta_source="test",
    )
    home = report.TeamLine(
        game_id=game_id,
        team="HME",
        home_away="home",
        opponent="AWY",
        espn_total_yards=0,
        windelta_total_yards=home_yd,
        yards_delta=home_yd,
        espn_turnovers=0,
        windelta_turnovers=home_to,
        turnovers_delta=home_to,
        espn_penalty_yards=0,
        windelta_penalty_yards=0,
        penalty_yards_delta=0,
        windelta_source="test",
    )
    return report.GameRecon(
        game_id=game_id,
        away="AWY",
        home="HME",
        raw_source="cache",
        team_lines=(away, home),
        turnover_plays_by_team={},
        potential_turnover_keyword_plays={},
        excluded_yardage_plays={},
        total_yards_corrections_by_team={},
    )


def test_priority_sort_turnovers_then_yards():
    g1 = _game("1", away_to=2, home_to=0, away_yd=5, home_yd=0)   # max TO=2, max Yds=5
    g2 = _game("2", away_to=1, home_to=0, away_yd=100, home_yd=0) # max TO=1, max Yds=100
    g3 = _game("3", away_to=2, home_to=0, away_yd=10, home_yd=0)  # max TO=2, max Yds=10

    ordered = [g.game_id for g in sorted([g1, g2, g3], key=lambda x: x.priority_key())]
    assert ordered == ["3", "1", "2"]


def test_analyze_reconciliation_clues_flags_excluded_return_yards_and_keyword_turnovers():
    raw_data = {
        "boxscore": {
            "teams": [
                {"team": {"id": "1", "abbreviation": "AAA"}},
                {"team": {"id": "2", "abbreviation": "BBB"}},
            ]
        },
        "drives": {
            "previous": [
                {
                    "team": {"id": "1"},
                    "plays": [
                        {
                            "period": {"number": 1},
                            "clock": {"displayValue": "12:00"},
                            "type": {"text": "Pass"},
                            "statYardage": 0,
                            "text": "QB pass short left FUMBLES (forced by X), recovered by BBB at AAA 20.",
                        },
                        {
                            "period": {"number": 1},
                            "clock": {"displayValue": "11:30"},
                            "type": {"text": "Kickoff Return"},
                            "statYardage": 25,
                            "text": "Kickoff returned to BBB 25 for 25 yards.",
                        },
                    ],
                }
            ]
        },
    }

    turnover_plays, potential_keyword, excluded_yards, total_yards_corrections = report.analyze_reconciliation_clues(
        raw_data, details={}
    )

    assert turnover_plays["AAA"] == []
    assert any("fumble" in (p.text or "").lower() for p in potential_keyword["AAA"])
    assert total_yards_corrections["AAA"] == []

    # Return plays are attributed to the opponent by the heuristic.
    assert any(p.reason == "special_teams_return" for p in excluded_yards["BBB"])


def test_build_season_recon_updates_passed_espn_stats_cache(tmp_path, monkeypatch):
    # Minimal cached payload containing just enough structure for extract_espn_official_team_stats.
    raw = {
        "header": {
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "away", "team": {"abbreviation": "AAA"}, "score": "7"},
                        {"homeAway": "home", "team": {"abbreviation": "BBB"}, "score": "10"},
                    ]
                }
            ]
        },
        "boxscore": {
            "teams": [
                {
                    "team": {"id": "1", "abbreviation": "AAA"},
                    "statistics": [
                        {"name": "totalYards", "displayValue": "200"},
                        {"name": "turnovers", "displayValue": "1"},
                        {"name": "totalPenaltiesYards", "displayValue": "3-30"},
                    ],
                },
                {
                    "team": {"id": "2", "abbreviation": "BBB"},
                    "statistics": [
                        {"name": "totalYards", "displayValue": "250"},
                        {"name": "turnovers", "displayValue": "0"},
                        {"name": "totalPenaltiesYards", "displayValue": "5-55"},
                    ],
                },
            ]
        },
        "drives": {"previous": []},
    }

    cache_dir = tmp_path / "pbp_cache"
    cache_dir.mkdir()
    (cache_dir / "123.json").write_text(json.dumps(raw))

    # Avoid relying on nfl_core internals here; just return minimal stats rows.
    def fake_process_game_stats(_raw_data, expanded, probability_map, pregame_probabilities, wp_threshold):
        rows = [
            {"Team": "AAA", "Total Yards": 200, "Turnovers": 1, "Penalty Yards": 30},
            {"Team": "BBB", "Total Yards": 250, "Turnovers": 0, "Penalty Yards": 55},
        ]
        details = {"1": {"Turnovers": []}, "2": {"Turnovers": []}} if expanded else {}
        return rows, details

    monkeypatch.setattr(report, "process_game_stats", fake_process_game_stats)

    stats_cache = {}
    recon, failures = report.build_season_recon(["123"], source="cache", cache_dir=cache_dir, cache_write=False, espn_stats_cache=stats_cache)
    assert failures == []
    assert len(recon) == 1
    assert "123" in stats_cache
    assert stats_cache["123"]["meta"] == {"away": "AAA", "home": "BBB"}


def test_compute_aggregate_deltas_sums_and_percentages():
    away = report.TeamLine(
        game_id="1",
        team="AAA",
        home_away="away",
        opponent="BBB",
        espn_total_yards=100,
        windelta_total_yards=110,
        yards_delta=10,
        espn_turnovers=2,
        windelta_turnovers=1,
        turnovers_delta=-1,
        espn_penalty_yards=50,
        windelta_penalty_yards=55,
        penalty_yards_delta=5,
        windelta_source="test",
    )
    home = report.TeamLine(
        game_id="1",
        team="BBB",
        home_away="home",
        opponent="AAA",
        espn_total_yards=200,
        windelta_total_yards=190,
        yards_delta=-10,
        espn_turnovers=0,
        windelta_turnovers=0,
        turnovers_delta=0,
        espn_penalty_yards=20,
        windelta_penalty_yards=20,
        penalty_yards_delta=0,
        windelta_source="test",
    )
    recon = [
        report.GameRecon(
            game_id="1",
            away="AAA",
            home="BBB",
            raw_source="cache",
            team_lines=(away, home),
            turnover_plays_by_team={},
            potential_turnover_keyword_plays={},
            excluded_yardage_plays={},
            total_yards_corrections_by_team={},
        )
    ]

    agg = report.compute_aggregate_deltas(recon)
    assert agg["total_yards"]["espn_sum"] == 300
    assert agg["total_yards"]["windelta_sum"] == 300
    assert agg["total_yards"]["delta"] == 0
    assert agg["total_yards"]["pct_delta"] == 0.0

    assert agg["turnovers"]["espn_sum"] == 2
    assert agg["turnovers"]["windelta_sum"] == 1
    assert agg["turnovers"]["delta"] == -1
    assert agg["turnovers"]["pct_delta"] == -50.0

    assert agg["penalty_yards"]["espn_sum"] == 70
    assert agg["penalty_yards"]["windelta_sum"] == 75
    assert agg["penalty_yards"]["delta"] == 5
    assert agg["penalty_yards"]["pct_delta"] == pytest.approx(7.142857, rel=1e-6)


def test_write_logic_recommendations_handles_pct_delta_none(tmp_path):
    # Force denom=0 so pct_delta is None, and ensure report still renders cleanly.
    away = report.TeamLine(
        game_id="1",
        team="AAA",
        home_away="away",
        opponent="BBB",
        espn_total_yards=0,
        windelta_total_yards=0,
        yards_delta=0,
        espn_turnovers=0,
        windelta_turnovers=0,
        turnovers_delta=0,
        espn_penalty_yards=0,
        windelta_penalty_yards=0,
        penalty_yards_delta=0,
        windelta_source="test",
    )
    home = report.TeamLine(
        game_id="1",
        team="BBB",
        home_away="home",
        opponent="AAA",
        espn_total_yards=0,
        windelta_total_yards=0,
        yards_delta=0,
        espn_turnovers=0,
        windelta_turnovers=0,
        turnovers_delta=0,
        espn_penalty_yards=0,
        windelta_penalty_yards=0,
        penalty_yards_delta=0,
        windelta_source="test",
    )
    recon = [
        report.GameRecon(
            game_id="1",
            away="AAA",
            home="BBB",
            raw_source="cache",
            team_lines=(away, home),
            turnover_plays_by_team={},
            potential_turnover_keyword_plays={},
            excluded_yardage_plays={},
            total_yards_corrections_by_team={},
        )
    ]

    out_path = tmp_path / "recs.md"
    report.write_logic_recommendations(out_path, recon, season=2025, cache_dir=tmp_path / "pbp_cache")
    text = out_path.read_text()
    assert "Total Yards: N/A" in text


def test_main_write_recommendations_flag_writes_file(tmp_path, monkeypatch):
    out_ids = tmp_path / "ids.txt"
    out_team_csv = tmp_path / "team.csv"
    out_game_csv = tmp_path / "game.csv"
    out_md = tmp_path / "report.md"
    out_recs = tmp_path / "recs.md"
    out_stats_cache = tmp_path / "stats_cache.json"
    cache_dir = tmp_path / "pbp_cache"
    cache_dir.mkdir()

    monkeypatch.setattr(report, "fetch_season_game_ids", lambda *_args, **_kwargs: ["123"])

    fake_recon = _game("123", away_to=1, home_to=0, away_yd=7, home_yd=0)

    def fake_build_season_recon(game_ids, *, source, cache_dir, cache_write, espn_stats_cache=None):
        return [fake_recon], []

    monkeypatch.setattr(report, "build_season_recon", fake_build_season_recon)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare_season_games_report.py",
            "--season",
            "2025",
            "--max-week",
            "15",
            "--source",
            "cache",
            "--cache-dir",
            str(cache_dir),
            "--out-ids",
            str(out_ids),
            "--out-team-csv",
            str(out_team_csv),
            "--out-game-csv",
            str(out_game_csv),
            "--out-md",
            str(out_md),
            "--espn-stats-cache",
            str(out_stats_cache),
            "--write-recommendations",
            "--out-recommendations",
            str(out_recs),
        ],
    )

    rc = report.main()
    assert rc == 0
    assert out_recs.exists()


def test_main_ids_input_does_not_overwrite_default_out_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    input_ids = tmp_path / "ids_in.txt"
    input_ids.write_text("123\n")

    default_out_ids = report.Path("audits") / "season_2025_game_ids.txt"
    existing = "AAA\nBBB\n"
    default_out_ids.parent.mkdir(parents=True, exist_ok=True)
    default_out_ids.write_text(existing)

    cache_dir = tmp_path / "pbp_cache"
    cache_dir.mkdir()

    fake_recon = _game("123", away_to=0, home_to=0, away_yd=0, home_yd=0)

    monkeypatch.setattr(report, "build_season_recon", lambda *args, **kwargs: ([fake_recon], []))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare_season_games_report.py",
            "--season",
            "2025",
            "--ids-input",
            str(input_ids),
            "--source",
            "cache",
            "--cache-dir",
            str(cache_dir),
            "--out-team-csv",
            str(tmp_path / "team.csv"),
            "--out-game-csv",
            str(tmp_path / "game.csv"),
            "--out-md",
            str(tmp_path / "report.md"),
            "--espn-stats-cache",
            str(tmp_path / "stats_cache.json"),
        ],
    )

    rc = report.main()
    assert rc == 0
    assert default_out_ids.read_text() == existing
