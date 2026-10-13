"""Time, coverage, market isolation, and append-only forecast contracts."""
from datetime import datetime, timezone
import json
import pytest
from research.weekly_team_ratings import (kickoff, completed_week, forecasts, score_predictions,
    validate_coverage, write_new, seal, verify_archive, earlier_forecasts, run_weekly)

AT = datetime(2026, 10, 13, 6, tzinfo=timezone.utc)


def game(week=6, **overrides):
    return {'game_id':'2026_06_BUF_NYJ', 'season':'2026', 'week':str(week),
            'home_team':'NYJ', 'away_team':'BUF', 'gameday':'2026-10-18', 'gametime':'13:00',
            'home_score':'', 'away_score':'', 'spread_line':'3', **overrides}


def model_input():
    power = {'throughWeek':5, 'teams':[{'id':'NYJ','features':{'strength':2,'neutral':0}},
                                     {'id':'BUF','features':{'strength':5,'neutral':0}}]}
    model = {'featureNames':['strength','neutral'], 'coefficients':[2,-1], 'intercept':2}
    baseline = {'featureNames':['strength'], 'coefficients':[1], 'intercept':2}
    context = {'2026_06_BUF_NYJ':{'restDifference':0,'neutral':0,'restMissing':0}}
    return power, model, baseline, context


def test_kickoff_uses_eastern_dst():
    assert kickoff(game()).isoformat() == '2026-10-18T17:00:00+00:00'
    assert kickoff(game(gameday='2026-11-15')).hour == 18


def test_cutoff_stops_before_partial_week_and_future_scores():
    rows = [game(1, gameday='2026-09-10', home_score='17', away_score='10'),
            game(2, gameday='2026-09-17', home_score='20', away_score='10'),
            game(2, game_id='unfinished')]
    assert completed_week(rows, AT) == 1
    with pytest.raises(ValueError, match='No fully completed'):
        completed_week([game(1, home_score='20', away_score='10')], AT)


def test_forecast_is_market_and_outcome_blind_and_before_kickoff():
    power, model, baseline, context = model_input()
    first = forecasts(power, [game()], context, model, baseline, AT)
    assert first[0]['model'] == -4
    assert first[0]['pointBaseline'] == -1
    assert forecasts(power, [game(spread_line='999')], context, model, baseline, AT) == first
    with pytest.raises(ValueError, match='Pregame cutoff missed'):
        forecasts(power, [game(home_score='42')], context, model, baseline, AT)
    with pytest.raises(ValueError, match='Pregame cutoff missed'):
        forecasts(power, [game(gameday='2026-10-11')], context, model, baseline, AT)
    with pytest.raises(ValueError, match='previous-week'):
        forecasts(power, [game(7)], context, model, baseline, AT)


def test_replay_label_required_for_completed_targets():
    power, model, baseline, context = model_input()
    a = forecasts(power, [game(home_score='42', away_score='17')], context, model, baseline, AT, True)
    b = forecasts(power, [game(home_score='3', away_score='80')], context, model, baseline, AT, True)
    assert a == b


def test_vegas_sign_missing_lines_ties_and_equal_sample():
    predictions = [{'gameId':str(i),'home':'H','away':'A','model':4.,'pointBaseline':2.} for i in range(4)]
    rows = [game(game_id='0', gameday='2026-10-11', home_score='24', away_score='20', spread_line='3'),
            game(game_id='1', gameday='2026-10-11', home_score='10', away_score='10', spread_line='0'),
            game(game_id='2', gameday='2026-10-11', home_score='14', away_score='17', spread_line=''),
            game(game_id='3')]
    result = score_predictions(predictions, rows, AT)
    assert result['metrics']['vegas']['mae'] == .5  # +3 home margin, not -3
    assert result['metrics']['model']['mae'] == 2
    assert all(m['games']==2 and m['winnerGames']==1 and m['tiesExcluded']==1 for m in result['metrics'].values())
    assert result['missingClosingLine'] == ['2']
    assert result['pending'] == ['3']


def test_reject_pbp_week_clamping_or_scoring_mismatch():
    rows = [game(1, gameday='2026-09-10', home_score='17', away_score='10')]
    audit = {'errors':{},'games':1,'expected':1,'scoring':1,'teams':32}
    assert validate_coverage({'throughWeek':1}, audit, rows, 1, AT) == {'2026_06_BUF_NYJ'}
    with pytest.raises(ValueError, match='coverage'):
        validate_coverage({'throughWeek':0}, audit, rows, 1, AT)
    with pytest.raises(ValueError, match='coverage'):
        validate_coverage({'throughWeek':1}, {**audit,'scoring':0}, rows, 1, AT)


def test_write_once_and_tamper_detection(tmp_path):
    path = tmp_path/'predictions.json'
    write_new(path, {'x':1})
    with pytest.raises(FileExistsError):
        write_new(path, {'x':2})
    seal(tmp_path)
    verify_archive(tmp_path)
    path.write_text('{}')
    with pytest.raises(ValueError, match='Archive changed'):
        verify_archive(tmp_path)


def test_first_pregame_prediction_kept_and_replay_excluded(tmp_path):
    for i, status in enumerate(['retrospective replay','pregame','pregame']):
        run = tmp_path/'weekly-archive'/str(i)
        write_new(run/'predictions.json', {'status':status,'publishedAt':f'2026-10-1{i}T06:00:00+00:00',
            'games':[{'gameId':'test','model':i,'kickoff':'2026-10-18T17:00:00+00:00'}]})
        seal(run)
    assert earlier_forecasts(tmp_path)[0]['model'] == 1


def test_failure_never_advances_published_pointer(tmp_path, monkeypatch):
    write_new(tmp_path/'weekly-latest.json', {'archive':'old-valid-publication'})
    def fail(*args):
        raise ValueError('source unavailable')
    monkeypatch.setattr('research.weekly_team_ratings.ensure_file', fail)
    with pytest.raises(ValueError, match='source unavailable'):
        run_weekly(tmp_path)
    assert json.loads((tmp_path/'weekly-latest.json').read_text()) == {'archive':'old-valid-publication'}
    assert json.loads((tmp_path/'weekly-status.json').read_text())['status'] == 'failed'


@pytest.mark.parametrize('line', ['', 'NA', 'nan', 'inf'])
def test_invalid_market_line_is_missing_not_zero(line):
    result = score_predictions([{'gameId':'g','home':'H','away':'A','model':1.,'pointBaseline':2.}],
        [game(game_id='g', gameday='2026-10-11', home_score='14', away_score='7', spread_line=line)], AT)
    assert result['missingClosingLine'] == ['g']
    assert result['games'][0]['vegas'] is None
    assert result['metrics']['model']['mae'] is None
