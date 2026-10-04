import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'api')))
from scoreboard import transform_game, build_response


def game_event(state, name, detail):
    return {
        'id': '123', 'date': '2026-10-04T17:00Z',
        'status': {'type': {'state': state, 'name': name, 'shortDetail': detail}},
        'competitions': [{'competitors': [
            {'homeAway': 'away', 'team': {'id': '1', 'abbreviation': 'AWY'}, 'score': '0'},
            {'homeAway': 'home', 'team': {'id': '2', 'abbreviation': 'HOM'}, 'score': '0'},
        ]}],
    }


def test_nonfinal_espn_states_are_not_presented_as_final():
    for state, name, detail, expected in [
        ('in', 'STATUS_HALFTIME', 'Halftime', 'in-progress'),
        ('in', 'STATUS_DELAYED', 'Weather Delay', 'delayed'),
        ('post', 'STATUS_POSTPONED', 'Postponed', 'postponed'),
        ('post', 'STATUS_CANCELED', 'Canceled', 'canceled'),
    ]:
        game = transform_game(game_event(state, name, detail))
        assert game['status'] == expected
        assert game['statusDetail'] == detail
        assert game['isActive'] is (expected == 'in-progress')


def test_upstream_scoreboard_failure_is_an_error_not_an_empty_week():
    response = build_response({'error': 'ESPN unavailable'})
    assert response['error'] == 'ESPN unavailable'
    assert response['games'] == []
