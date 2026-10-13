"""Season aggregation regressions. Fixtures only; never call a provider."""
from copy import deepcopy
import pytest

from api.lib.nfl_core import process_game_stats
from api.lib.team_season import FACTORS, aggregate_season, extract_game, measure, pool, select_events
from research.build_team_seasons import apply_independent_audit
from research.audit_team_seasons import audit, reference_rows


def event(gid="g1", week=1, season=2025, season_type=2, final=True):
    return {"id": gid, "date": f"{season}-09-{week:02d}T17:00Z",
            "season": {"year": season, "type": season_type}, "week": {"number": week},
            "status": {"type": {"state": "post" if final else "pre"}},
            "competitions": [{"competitors": [
                {"id": "1", "homeAway": "home", "score": "7", "team": {"id": "1", "abbreviation": "AAA", "displayName": "Team A"}},
                {"id": "2", "homeAway": "away", "score": "0", "team": {"id": "2", "abbreviation": "BBB", "displayName": "Team B"}},
            ]}]}


def record(gid="g1", week=1, values=((1, 2), (1, 4))):
    return {"gameId": gid, "season": 2025, "seasonType": 2, "week": week,
            "kickoff": f"2025-09-{week:02d}T17:00Z", "sourceGaps": [],
            "teams": [{"id": str(i + 1), "factors": {f["id"]: measure(*value) for f in FACTORS}}
                      for i, value in enumerate(values)]}


def minimal_raw():
    comps = deepcopy(event()["competitions"][0]["competitors"])
    for c in comps:
        c["score"] = "0"
    boxes = []
    drives = []
    for c in comps:
        boxes.append({"team": c["team"], "statistics": [
            {"name": "totalYards", "displayValue": "10"},
            {"name": "totalOffensivePlays", "displayValue": "3"},
            {"name": "turnovers", "displayValue": "0"},
            {"name": "totalPenaltiesYards", "displayValue": "0-0"},
        ]})
        drives.append({"team": {"id": c["id"]}, "start": {"text": f"{c['team']['abbreviation']} 20", "yardLine": 20},
                       "plays": [{"id": f"{c['id']}-{i}", "type": {"text": "Rush"},
                                  "text": f"Runner left tackle for {yards} yards.", "statYardage": yards,
                                  "start": {"team": {"id": c["id"]}, "down": 1, "distance": 10, "yardsToEndzone": 80},
                                  "end": {"team": {"id": c["id"]}, "yardsToEndzone": 80 - yards}}
                                 for i, yards in enumerate((4, 3, 3))]})
    return {"header": {"id": "g1", "season": {"year": 2025, "type": 2}, "week": 1,
                       "competitions": [{"id": "g1", "date": "2025-09-01T17:00Z", "competitors": comps,
                                         "status": {"type": {"state": "post", "completed": True}}}]},
            "boxscore": {"teams": boxes}, "drives": {"previous": drives}, "scoringPlays": []}


def test_raw_counters_preserve_precision_and_existing_game_output():
    raw = minimal_raw()
    expected = process_game_stats(raw, expanded=True, wp_threshold=1.0)
    counts = {"old-game-team": {"Plays": 999}}
    assert process_game_stats(raw, expanded=True, wp_threshold=1.0, aggregate_stats=counts) == expected
    assert counts["1"]["Successful Plays"] == 1
    assert counts["1"]["Plays"] == 3
    assert "old-game-team" not in counts
    extracted = extract_game(raw)
    assert extracted["teams"][0]["factors"]["success_rate"]["value"] == 1 / 3
    assert extracted["teams"][0]["factors"]["yards_per_play"]["value"] == 10 / 3


def test_zero_opportunities_are_distinct_from_observed_zero():
    own = extract_game(minimal_raw())["teams"][0]["factors"]
    assert own["points_per_trip"]["value"] is None
    assert own["points_per_trip"]["denominator"] == 0
    assert own["turnovers"]["value"] == 0
    assert own["penalties"]["value"] == 0


def test_box_gap_does_not_silently_repair_derived_factors():
    raw = minimal_raw()
    raw["boxscore"]["teams"][0]["statistics"][0]["displayValue"] = "25"
    result = extract_game(raw)
    assert result["sourceGaps"]
    for team in result["teams"]:
        assert not team["factors"]["success_rate"]["usable"]
        assert team["factors"]["turnovers"]["usable"]
        assert team["factors"]["penalties"]["usable"]


def test_absent_penalty_total_is_not_zero():
    raw = minimal_raw()
    raw["boxscore"]["teams"][0]["statistics"].pop()
    penalty = extract_game(raw)["teams"][0]["factors"]["penalties"]
    assert penalty["value"] is None
    assert not penalty["usable"]


def test_malformed_official_counts_do_not_pass_validation():
    raw = minimal_raw()
    for stat in raw["boxscore"]["teams"][0]["statistics"]:
        if stat["name"] in ("turnovers", "totalOffensivePlays"):
            stat["displayValue"] = "--"
    factors = extract_game(raw)["teams"][0]["factors"]
    assert not factors["turnovers"]["usable"]
    assert not factors["success_rate"]["usable"]


def test_incomplete_scoring_is_not_zero_non_offensive_points():
    raw = minimal_raw()
    raw["header"]["competitions"][0]["competitors"][0]["score"] = "7"
    assert not extract_game(raw)["teams"][0]["factors"]["non_offensive_points"]["usable"]


def test_rejects_nonfinal_and_mismatched_team_metadata():
    raw = minimal_raw()
    raw["header"]["competitions"][0]["status"]["type"]["state"] = "in"
    with pytest.raises(ValueError, match="not final"):
        extract_game(raw)
    raw = minimal_raw()
    raw["boxscore"]["teams"].pop()
    with pytest.raises(ValueError, match="team IDs"):
        extract_game(raw)


def test_pool_uses_denominators_not_average_game_percentages():
    result = pool([measure(1, 2), measure(9, 10)], 2)
    assert result["value"] == 10 / 12
    assert result["value"] != (.5 + .9) / 2
    assert result["complete"]


def test_defense_and_net_are_paired_and_lower_is_better_is_inverted():
    s = aggregate_season([record()], [event()], 2025)
    a, b = s["teams"]
    assert a["factors"]["success_rate"]["opponent"]["value"] == .25
    assert a["factors"]["success_rate"]["net"]["value"] == .25
    assert b["factors"]["success_rate"]["net"]["value"] == -.25
    assert a["factors"]["turnovers"]["net"]["value"] == -.25
    assert a["factors"]["success_rate"]["own"]["rank"] == 1
    assert a["factors"]["turnovers"]["own"]["rank"] == 2
    assert a["factors"]["success_rate"]["opponent"]["rank"] == 1


def test_net_uses_same_games_on_both_sides():
    r1, r2 = record(), record("g2", 2, ((9, 10), (1, 10)))
    r2["teams"][1]["factors"]["success_rate"] = measure(1, 10, ["missing_data"])
    a = aggregate_season([r1, r2], [event(), event("g2", 2)], 2025)["teams"][0]
    f = a["factors"]["success_rate"]
    assert f["own"]["value"] == 10 / 12
    assert f["opponent"]["value"] == .25
    assert f["net"]["value"] == .25
    assert f["net"]["gamesIncluded"] == 1
    assert f["net"]["rank"] is None


def test_missing_game_affects_coverage_but_record_comes_from_schedule():
    a = aggregate_season([record()], [event(), event("g2", 2)], 2025)["teams"][0]
    assert a["record"]["wins"] == 2
    assert a["gamesAvailable"] == 1
    assert a["gamesExpected"] == 2
    assert a["factors"]["success_rate"]["own"]["rank"] is None
    assert a["factors"]["success_rate"]["own"]["value"] == .5


def test_ties_share_rank_and_midpoint_percentile():
    s = aggregate_season([record(values=((1, 2), (2, 4)))], [event()], 2025)
    for team in s["teams"]:
        own = team["factors"]["success_rate"]["own"]
        assert own["rank"] == 1
        assert own["tied"]
        assert own["percentile"] == 50


def test_week_cutoff_excludes_future_games_and_other_seasons_or_phases():
    events = [event(), event("g2", 2), event("old", season=2024), event("post", season_type=3)]
    records = [record(), record("g2", 2, ((100, 100), (0, 100)))]
    s = aggregate_season(records, events, 2025, through_week=1)
    assert s["expectedGames"] == 1
    assert s["teams"][0]["factors"]["success_rate"]["own"]["value"] == .5
    assert len(select_events([{"events": events}, {"events": events}], 2025, through_week=1)) == 1


def test_january_game_is_assigned_by_nfl_season_not_calendar_year():
    january = event("jan", 18, season=2025)
    january["date"] = "2026-01-04T17:00Z"
    assert select_events([{"events": [january]}], 2025) == [january]
    assert select_events([{"events": [january]}], 2026) == []


def test_duplicate_records_and_schedule_mismatches_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        aggregate_season([record(), record()], [event()], 2025)
    with pytest.raises(ValueError, match="disagrees"):
        aggregate_season([record(week=2)], [event()], 2025)


def test_no_completed_games_have_no_rank_and_live_scores_do_not_enter_record():
    s = aggregate_season([record()], [event(final=False)], 2025)
    assert s["expectedGames"] == 0
    assert s["teams"][0]["record"]["wins"] == 0
    assert s["teams"][0]["factors"]["turnovers"]["own"]["value"] is None


def test_opponent_values_equal_own_league_totals():
    teams = aggregate_season([record(), record("g2", 2)], [event(), event("g2", 2)], 2025)["teams"]
    for factor in FACTORS:
        assert sum(t["factors"][factor["id"]]["own"]["numerator"] for t in teams) == sum(
            t["factors"][factor["id"]]["opponent"]["numerator"] for t in teams)


def test_independent_audit_adds_exclusions_without_overwriting_raw_data():
    records = [{"gameId": "g1", "teams": [{"abbr": "AAA", "factors": {
        f["id"]: measure(1, 2) for f in FACTORS}}]}]
    independent = {"inputs": {"games": "same-hash"}, "differences": [{"gameId": "g1", "team": "AAA"}],
                   "unmatchedOrIncomplete": []}
    checked = apply_independent_audit(records, independent, "same-hash")
    assert records[0]["teams"][0]["factors"]["success_rate"]["usable"]
    assert not checked[0]["teams"][0]["factors"]["success_rate"]["usable"]
    assert checked[0]["teams"][0]["factors"]["penalties"]["usable"]
    with pytest.raises(ValueError, match="exact game records"):
        apply_independent_audit(records, independent, "wrong-hash")


def test_reference_audit_joins_team_identity_and_exposes_unflagged_difference():
    r = extract_game(minimal_raw())
    refs = [{"season": 2025, "week": 1, "home_team": "AAA", "away_team": "BBB", "posteam": team,
             "plays": 3, "yards": yards, "successes": 1, "explosives": 0, "incomplete_plays": 0}
            for team, yards in (("AAA", 10), ("BBB", 11))]
    result = audit([r], refs)
    assert result["teamGamesCompared"] == 2
    assert result["exactCounterMatches"] == 1
    assert result["disagreementsWithoutBoxscoreFlag"] == 1
    assert result["differences"][0]["team"] == "BBB"
    assert result["differences"][0]["rateDeltas"]["yards_per_play"] == pytest.approx(-1 / 3)
    first = result["seasonNetComparison"]["yards_per_play"][0]
    assert first["team"] == "AAA"
    assert first["espnRank"] == 1
    assert first["nflverseRank"] == 2


def test_reference_query_uses_app_success_and_dropback_explosive_rules(tmp_path):
    import duckdb
    path = tmp_path / "fixture.parquet"
    with duckdb.connect() as conn:
        conn.execute("""CREATE TABLE plays AS SELECT
            2025 AS season, 1 AS week, 'AAA' AS home_team, 'BBB' AS away_team,
            'AAA' AS posteam, 'REG' AS season_type, 'run' AS play_type,
            0 AS two_point_attempt, 0 AS play_deleted, 0 AS lateral_reception,
            NULL::DOUBLE AS passing_yards, 12 AS yards_gained, 1 AS down,
            10 AS ydstogo, 1 AS qb_dropback, 0 AS success""")
        # A 12-yard scramble succeeds under 40/60/100 but is not explosive.
        conn.execute("COPY plays TO ? (FORMAT PARQUET)", [str(path)])
    rows = reference_rows(path)
    assert rows[0]["successes"] == 1
    assert rows[0]["explosives"] == 0
