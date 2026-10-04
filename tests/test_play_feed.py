import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.lib.play_feed import build_play_feed


def test_cached_game_feed_retains_source_context_and_scores():
    raw = json.loads((ROOT / 'tests' / 'fixtures' / '401772633.json').read_text())
    plays = build_play_feed(raw, {}, 0.5)
    assert len(plays) > 100
    assert len({play['id'] for play in plays}) == len(plays)
    assert plays[0]['sourceTeam'] == 'MIN'
    assert plays[0]['ballBefore'] == 'MIN 35'
    assert plays[0]['penalty']['yards'] == 0
    assert plays[1]['sourceTeam'] == 'CLE'
    assert plays[1]['ballBefore'] == 'CLE 40'
    touchdown = next(play for play in plays if play['id'] == '401772633506')
    assert touchdown['scoreBefore'] == {'home': 0, 'away': 0}
    assert touchdown['scoreChange'] == {'team': 'CLE', 'points': 7, 'non_offensive': False}
    assert all(play['epa'] is None for play in plays)


def test_wp_requires_adjacent_measured_entries():
    raw = json.loads((ROOT / 'tests' / 'fixtures' / '401772633.json').read_text())
    first = raw['drives']['previous'][0]['plays'][0]['id']
    second = raw['drives']['previous'][0]['plays'][1]['id']
    third = raw['drives']['previous'][0]['plays'][2]['id']
    plays = build_play_feed(raw, {
        str(first): {'homeWinPercentage': .6},
        str(second): {'homeWinPercentage': .7},
        str(third): {'homeWinPercentage': .8},
    }, .5)
    assert round(plays[0]['homeWpDelta'], 5) == .1
    assert round(plays[1]['homeWpDelta'], 5) == .1
    assert round(plays[2]['homeWpDelta'], 5) == .1
    assert plays[3]['homeWpAfter'] is None
    assert plays[4]['homeWpBefore'] is None
    assert plays[4]['homeWpDelta'] is None


def test_transient_score_regression_does_not_credit_following_kickoff():
    raw = {
        'header': {'competitions': [{'competitors': [
            {'id': '1', 'homeAway': 'home', 'team': {'id': '1', 'abbreviation': 'HOM'}},
            {'id': '2', 'homeAway': 'away', 'team': {'id': '2', 'abbreviation': 'AWY'}},
        ]}]},
        'drives': {'previous': [{'team': {'id': '2'}, 'plays': [
            {'id': 'td', 'homeScore': 24, 'awayScore': 24, 'type': {'text': 'Passing Touchdown'}, 'text': 'Touchdown and two-point conversion', 'clock': {'displayValue': '1:42'}},
            {'id': 'penalty', 'homeScore': 24, 'awayScore': 22, 'type': {'text': 'Penalty'}, 'text': 'Defensive Offside - No Play', 'clock': {'displayValue': '1:42'}},
            {'id': 'kickoff', 'homeScore': 24, 'awayScore': 24, 'type': {'text': 'Kickoff'}, 'text': 'Kickoff to the home team', 'clock': {'displayValue': '1:42'}},
        ]}]},
    }
    plays = build_play_feed(raw, {}, None)
    assert plays[1]['scoreBefore'] == {'home': 24, 'away': 24}
    assert plays[1]['scoreAfter'] == {'home': 24, 'away': 24}
    assert plays[2]['scoreBefore'] == {'home': 24, 'away': 24}
    assert plays[2]['scoreChange'] is None
    assert plays[2]['wpAttributionUncertain'] is True


def test_api_factor_events_resolve_to_canonical_source_play(monkeypatch):
    from api.lib import game_analysis

    raw = json.loads((ROOT / 'tests' / 'fixtures' / '401772633.json').read_text())
    monkeypatch.setattr(game_analysis, 'get_game_data', lambda _game_id: raw)
    monkeypatch.setattr(game_analysis, 'get_pregame_probabilities', lambda _game_id: (.5, .5))
    monkeypatch.setattr(game_analysis, 'get_play_probabilities', lambda _game_id: {})
    payload = game_analysis.analyze_game('401772633')
    by_id = {play['id'] for play in payload['plays']}
    assert len(by_id) == len(payload['plays'])
    assert len(by_id) > 100
    for team_details in payload['expanded_details_full'].values():
        assert team_details['Offensive Plays']
        for category, events in team_details.items():
            for event in events:
                if event.get('source_play_id'):
                    assert event['source_play_id'] in by_id, (category, event)
