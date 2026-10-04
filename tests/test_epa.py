import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.lib.epa import calculate_play_epa
from api.lib.play_feed import build_play_feed


def sample_game():
    return json.loads((ROOT / 'pbp_cache' / '401772633.json').read_text())


def test_completed_game_epa_is_attached_to_canonical_plays():
    raw = sample_game()
    values = calculate_play_epa(raw, 'final', roof='outdoors')
    cards = build_play_feed(raw, {}, 0.5, values)
    assert len(values) > 150
    assert len([card for card in cards if card['epa'] is not None]) == len(values)
    assert cards[0]['sourceTeam'] == 'MIN'
    assert cards[0]['epa'] == -0.9262  # kickoff receiver gains 0.9262 EP
    assert values['40177263379'] == -0.0619
    assert values['4017726332299'] == 0.1581  # field-goal baseline uses six state features


def test_game_api_populates_epa_from_espn_play_feed(monkeypatch):
    from api.lib import game_analysis

    raw = sample_game()
    monkeypatch.setattr(game_analysis, 'get_game_data', lambda _game_id: raw)
    monkeypatch.setattr(game_analysis, 'get_pregame_probabilities', lambda _game_id: (.5, .5))
    monkeypatch.setattr(game_analysis, 'get_play_probabilities', lambda _game_id: {})
    payload = game_analysis.analyze_game('401772633')
    assert len([play for play in payload['plays'] if play['epa'] is not None]) > 150
    assert payload['plays'][0]['epa'] == -0.9262


def test_epa_failure_does_not_block_game_page(monkeypatch):
    from api.lib import game_analysis

    raw = sample_game()
    monkeypatch.setattr(game_analysis, 'get_game_data', lambda _game_id: raw)
    monkeypatch.setattr(game_analysis, 'get_pregame_probabilities', lambda _game_id: (.5, .5))
    monkeypatch.setattr(game_analysis, 'get_play_probabilities', lambda _game_id: {})
    monkeypatch.setattr(game_analysis, 'calculate_play_epa',
                        lambda *_args: (_ for _ in ()).throw(RuntimeError('model missing')))
    payload = game_analysis.analyze_game('401772633')
    assert len(payload['plays']) > 100
    assert all(play['epa'] is None for play in payload['plays'])


def test_live_edge_waits_for_a_successor_without_using_future_plays():
    raw = sample_game()
    first_drive = raw['drives']['previous'][0]
    raw['drives']['previous'] = [{**first_drive, 'plays': first_drive['plays'][:2]}]
    raw['drives']['current'] = None
    values = calculate_play_epa(raw, 'in-progress', roof='outdoors')
    assert first_drive['plays'][0]['id'] in values
    assert first_drive['plays'][1]['id'] not in values


def test_last_q4_play_does_not_receive_end_of_half_epa_while_live():
    raw = sample_game()
    q4_play = next(play for drive in raw['drives']['previous']
                   for play in drive['plays']
                   if (play.get('period') or {}).get('number') == 4
                   and (play.get('type') or {}).get('text') == 'Rush')
    raw['drives']['previous'] = [{'plays': [q4_play]}]
    raw['drives']['current'] = None
    assert q4_play['id'] not in calculate_play_epa(raw, 'in-progress', roof='outdoors')
    assert q4_play['id'] in calculate_play_epa(raw, 'final', roof='outdoors')


def test_halftime_resolves_the_last_second_quarter_play():
    raw = sample_game()
    q2_play = next(play for drive in raw['drives']['previous']
                   for play in drive['plays']
                   if (play.get('period') or {}).get('number') == 2
                   and (play.get('type') or {}).get('text') == 'Rush')
    raw['drives']['previous'] = [{'plays': [q2_play]}]
    raw['drives']['current'] = None
    competition = raw['header']['competitions'][0]
    competition['status'] = {'type': {'name': 'STATUS_IN_PROGRESS'}}
    assert q2_play['id'] not in calculate_play_epa(raw, 'in-progress', roof='outdoors')
    competition['status'] = {'type': {'name': 'STATUS_HALFTIME'}}
    assert q2_play['id'] in calculate_play_epa(raw, 'in-progress', roof='outdoors')
