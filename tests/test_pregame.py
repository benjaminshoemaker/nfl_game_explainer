import copy
import json
import sys
from types import SimpleNamespace

import pytest

from api.lib import pregame


def payload():
    data = json.loads(pregame.DATA_PATH.read_text())
    game_id, game = next(iter(data['games'].items()))
    return {'gameId': game_id, 'season': data['season'], 'status': 'pregame',
            'week': {'number': game['week'], 'seasonType': 2},
            'team_meta': [{'abbr': game[side], 'homeAway': side} for side in ['home', 'away']]}


def test_snapshot_matches_only_exact_pregame():
    p = payload()
    assert pregame.load_preview(p)
    for key, value in [('status', 'in-progress'), ('season', 2025), ('gameId', 'unknown'),
                       ('week', {'number': 11, 'seasonType': 2}), ('week', {'number': 10, 'seasonType': 3})]:
        assert pregame.load_preview({**p, key: value}) is None
    p['team_meta'][0]['abbr'] = 'WRONG'
    assert pregame.load_preview(p) is None


def test_future_and_invalid_snapshot_rejected(tmp_path):
    d = json.loads(pregame.DATA_PATH.read_text())
    d['throughWeek'] += 1
    path = tmp_path / 'data.json'
    path.write_text(json.dumps(d))
    assert pregame.load_preview(payload(), path) is None
    d['throughWeek'] -= 1
    d['publishedAt'] = '2099-01-01T00:00:00+00:00'
    path.write_text(json.dumps(d))
    assert pregame.load_preview(payload(), path) is None


def test_no_key_preserves_stats(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    p = payload()
    pregame.attach_preview(p)
    assert p['pregame_preview']['narrative'] is None
    assert len(p['pregame_preview']['power']) == 2
    assert p['ai_summary'] is None


def install_model(monkeypatch, result, calls):
    def create(**options):
        calls.append(options)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(result)))])
    monkeypatch.setitem(sys.modules, 'openai', SimpleNamespace(OpenAI=lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))))


def narrative(p):
    return {'headline': 'A matchup to watch', 'summary': 'The teams face different tests.',
            'watchPoints': [{'title': 'Can the offense sustain drives?', 'body': 'Watch how the offense handles this defense.',
                             'factIds': list(pregame.evidence(p))[:2]}]}


def test_model_override_structured_output_and_fact_cache(monkeypatch, tmp_path):
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    monkeypatch.setenv('OPENAI_MODEL', 'gpt-5.6-luna')
    monkeypatch.setattr(pregame, 'CACHE_PATH', tmp_path)
    p = pregame.load_preview(payload())
    calls = []
    expected = narrative(p)
    install_model(monkeypatch, expected, calls)
    assert pregame.generate_preview_copy(p) == expected
    assert pregame.generate_preview_copy(p) == expected
    assert len(calls) == 1
    assert calls[0]['model'] == 'gpt-5.6-luna'
    assert calls[0]['response_format']['json_schema']['strict']
    p['teams'][0]['factors']['success_rate']['own']['value'] += .01
    pregame.generate_preview_copy(p)
    assert len(calls) == 2
    monkeypatch.setenv('OPENAI_MODEL', 'another-model')
    pregame.generate_preview_copy(p)
    assert len(calls) == 3


@pytest.mark.parametrize('failure', [TimeoutError(), {'headline': 'bad'}, {'headline': 'x', 'summary': 'y', 'watchPoints': [{'title': 'x', 'body': 'y', 'factIds': ['invented.fact']}]}])
def test_api_failure_or_invalid_copy_falls_back(monkeypatch, tmp_path, failure):
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    monkeypatch.setattr(pregame, 'CACHE_PATH', tmp_path)
    install_model(monkeypatch, failure, [])
    assert pregame.generate_preview_copy(pregame.load_preview(payload())) is None


def test_incomplete_metrics_are_not_ai_evidence():
    p = pregame.load_preview(payload())
    team = p['teams'][0]
    team['factors']['turnovers']['own']['complete'] = False
    assert f"{team['id']}.turnovers.own" not in pregame.evidence(p)


def test_packaged_rating_components_reconcile():
    d = json.loads(pregame.DATA_PATH.read_text())
    assert sum(d['weights'].values()) == pytest.approx(100)
    for team in d['power']:
        assert sum(team['contributions'].values()) == pytest.approx(team['rating'])


def test_api_errors_back_off_without_hiding_stats(monkeypatch, tmp_path):
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    monkeypatch.setattr(pregame, 'CACHE_PATH', tmp_path)
    calls = []
    install_model(monkeypatch, TimeoutError(), calls)
    p = pregame.load_preview(payload())
    assert pregame.generate_preview_copy(p) is None
    assert pregame.generate_preview_copy(p) is None
    assert len(calls) == 1


def test_publisher_rejects_replay_and_future_cutoffs(tmp_path):
    from research.publish_pregame import publish
    (tmp_path / 'predictions.json').write_text(json.dumps({'status': 'retrospective replay'}))
    with pytest.raises(ValueError, match='Only pregame'):
        publish(tmp_path, tmp_path / 'bundle.json')
    (tmp_path / 'predictions.json').write_text(json.dumps({'status': 'pregame', 'season': 2026, 'week': 10, 'inputThroughWeek': 10}))
    with pytest.raises(ValueError, match='prior-week'):
        publish(tmp_path, tmp_path / 'bundle.json')
    assert not (tmp_path / 'bundle.json').exists()
