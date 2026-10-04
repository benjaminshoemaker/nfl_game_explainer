"""Live ESPN play EPA using the benchmarked nflfastR expected-points model.

The published EP model and the 2025 field-goal baseline are bundled so a
game refresh never waits for a model download. Only ESPN game/venue data are
used at request time. Values are in the listed play team's perspective.
"""

import hashlib
import json
import logging
import lzma
import re
import urllib.request
from functools import lru_cache
from pathlib import Path

from .epa_transitions import estimate_play_epa, possession_id


DATA = Path(__file__).resolve().parent / 'data'
# Published artifact: https://github.com/nflverse/fastrmodels/blob/master/data/ep_model.rda
MODEL_SHA256 = 'fa45093d478fdd4534fa48860678ff99d597a67c340821db075c47fdab9102af'
EP_WEIGHTS = (7, -7, 3, -3, 2, -2, 0)


@lru_cache(maxsize=1)
def _models():
    import xgboost as xgb

    data = (DATA / 'ep_model.rda').read_bytes()
    if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
        raise RuntimeError('EP model artifact checksum mismatch')
    serialized = lzma.decompress(data)
    if not serialized.startswith(b'RDX3\nX\n') or serialized[52:56] != b'\x00\x00\x00\x18':
        raise RuntimeError('unexpected EP model serialization')
    size = int.from_bytes(serialized[56:60], 'big')
    raw = serialized[60:60 + size]
    if len(raw) != size or not raw.startswith(b'{L'):
        raise RuntimeError('unexpected EP model vector')
    model = xgb.Booster()
    model.load_model(bytearray(raw))
    if model.num_features() != 18:
        raise RuntimeError('unexpected EP model feature count')
    field_goal = json.loads((DATA / 'fg_ep_2025.json').read_text())
    return model, field_goal


def _features(state):
    down = state.get('down')
    roof = state.get('roof')
    keys = ('half_seconds_remaining', 'yardline_100', 'home', 'ydstogo',
            'posteam_timeouts_remaining', 'defteam_timeouts_remaining')
    if down not in (1, 2, 3, 4) or roof not in ('outdoors', 'dome', 'retractable'):
        return None
    if any(state.get(key) is None for key in keys):
        return None
    seconds, yardline, home, distance, offense_to, defense_to = (state[key] for key in keys)
    if not (0 <= seconds <= 1800 and 1 <= yardline <= 99 and 1 <= distance <= 40
            and 0 <= offense_to <= 3 and 0 <= defense_to <= 3):
        return None
    return (seconds, yardline, home, int(roof == 'retractable'),
            int(roof == 'dome'), int(roof == 'outdoors'), distance,
            0, 0, 0, 0, 1, *(int(down == n) for n in (1, 2, 3, 4)),
            offense_to, defense_to)


@lru_cache(maxsize=4096)
def _predict(features):
    import numpy as np
    import xgboost as xgb

    model, _ = _models()
    probabilities = model.predict(xgb.DMatrix(np.asarray([features], dtype=float)))[0]
    return float(sum(float(probability) * weight
                     for probability, weight in zip(probabilities, EP_WEIGHTS)))


def _predict_fg(features):
    _, fg = _models()
    value = fg['baseline']
    for tree in fg['trees']:
        index = 0
        while not tree[index]['leaf']:
            node = tree[index]
            feature = features[node['feature']]
            index = (node['left'] if (feature is None and node['missing_left'])
                     or (feature is not None and feature <= node['threshold'])
                     else node['right'])
        value += tree[index]['value']
    return value


@lru_cache(maxsize=64)
def _venue_roof(venue_id):
    url = f'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/venues/{venue_id}'
    with urllib.request.urlopen(url, timeout=4) as response:
        venue = json.load(response)
    if not venue.get('indoor'):
        return 'outdoors'
    if venue.get('fullName') in ('Lucas Oil Stadium', 'AT&T Stadium'):
        return 'retractable'
    return 'dome'


def _annotate(plays, competitors, roof):
    id_to_team = {str(c['team']['id']): c['team']['abbreviation'] for c in competitors}
    city_to_team = {c['team']['location'].lower(): c['team']['abbreviation']
                    for c in competitors if c['team'].get('location')}
    aliases = {'LA': 'LAR', 'WAS': 'WSH', 'HST': 'HOU', 'ARZ': 'ARI',
               'BLT': 'BAL', 'CLV': 'CLE'}
    normalize = lambda value: aliases.get(value, value)
    counts = {normalize(team): 3 for team in id_to_team.values()}
    home_id = next((str(c['team']['id']) for c in competitors
                    if c.get('homeAway') == 'home'), None)
    last_period = None
    for play in plays:
        period = (play.get('period') or {}).get('number')
        if period == 3 and last_period != 3:
            counts = {team: 3 for team in counts}
        last_period = period
        text = play.get('text') or ''
        challenge = re.search(r'([^.]*) challenged .*\(Timeout #(\d+)\.\)', text, re.I)
        if challenge:
            preceding = challenge.group(1).lower()
            for city, team in city_to_team.items():
                if preceding.endswith(city):
                    counts[normalize(team)] = max(0, 3 - int(challenge.group(2)))
                    break
        start_id = str(((play.get('start') or {}).get('team') or {}).get('id') or '')
        offense = normalize(id_to_team.get(start_id, ''))
        if offense in counts and len(counts) == 2:
            defense = next(team for team in counts if team != offense)
            play['_epa_team_abbreviation'] = offense
            play['_epa_offense_timeouts'] = counts[offense]
            play['_epa_defense_timeouts'] = counts[defense]
            play['_epa_home'] = int(start_id == home_id)
            play['_epa_roof'] = roof
        timeout = re.search(r'Timeout #(\d+) by ([A-Z]{2,3})', text, re.I)
        if timeout:
            team = normalize(timeout.group(2).upper())
            if team in counts:
                counts[team] = max(0, 3 - int(timeout.group(1)))


def _state(play):
    start = play.get('start') or {}
    yardline = start.get('yardsToEndzone')
    kind = ((play.get('type') or {}).get('text') or '').lower()
    if 'punt' in kind:
        spot = re.search(r'\bat\s+([A-Z]{2,3})\s+(\d{1,2})\b',
                         start.get('downDistanceText') or '')
        offense = play.get('_epa_team_abbreviation')
        if spot and offense:
            side, yard = spot.group(1), int(spot.group(2))
            yardline = 100 - yard if side == offense else yard
    period = (play.get('period') or {}).get('number')
    clock = (play.get('clock') or {}).get('displayValue') or ''
    match = re.fullmatch(r'(\d+):(\d{2})', clock)
    seconds = None
    if period in (1, 2, 3, 4) and match:
        seconds = int(match.group(1)) * 60 + int(match.group(2))
        if period in (1, 3):
            seconds += 900
    return {
        'down': start.get('down'), 'ydstogo': start.get('distance'),
        'yardline_100': yardline, 'half_seconds_remaining': seconds,
        'posteam_timeouts_remaining': play.get('_epa_offense_timeouts'),
        'defteam_timeouts_remaining': play.get('_epa_defense_timeouts'),
        'home': play.get('_epa_home'), 'roof': play.get('_epa_roof'),
    }


def calculate_play_epa(raw_data, status, roof=None):
    """Return play-ID EPA estimates; omit unresolved live and invalid states."""
    competition = ((raw_data.get('header') or {}).get('competitions') or [{}])[0]
    competitors = competition.get('competitors') or []
    if len(competitors) != 2:
        return {}
    drives = raw_data.get('drives') or {}
    seen = set()
    plays = []
    for drive in [*(drives.get('previous') or []), *([drives['current']] if drives.get('current') else [])]:
        for play in drive.get('plays') or []:
            play_id = str(play.get('id') or '')
            if play_id and play_id not in seen:
                seen.add(play_id)
                plays.append(dict(play))
    if not plays:
        return {}
    if roof is None:
        venue_id = str(((raw_data.get('gameInfo') or {}).get('venue') or {}).get('id') or '')
        if not venue_id:
            return {}
        try:
            roof = _venue_roof(venue_id)
        except (OSError, ValueError) as error:
            logging.warning('EPA venue lookup failed for %s: %s', venue_id, error)
            return {}
    _annotate(plays, competitors, roof)
    team_ids = {str(c['team']['id']) for c in competitors}

    def predict(state):
        features = _features(state)
        return _predict(features) if features is not None else None

    def predict_fg(state):
        if _features(state) is None:
            return None
        return _predict_fg(tuple(state[key] for key in (
            'down', 'ydstogo', 'yardline_100', 'half_seconds_remaining',
            'posteam_timeouts_remaining', 'defteam_timeouts_remaining',
        )))

    status_type = ((competition.get('status') or {}).get('type') or {})
    marker = f"{status_type.get('name', '')} {status_type.get('shortDetail', '')}".lower()
    result = {}
    for position, play in enumerate(plays):
        period = (play.get('period') or {}).get('number')
        ended = status == 'final' and period == 4 or period == 2 and ('half' in marker or 'ht' == marker.strip())
        estimate = estimate_play_epa(plays, position, team_ids, _state, predict,
                                     predict_fg, period_ended=ended)
        if estimate is None:
            continue
        source_id = str(((play.get('start') or {}).get('team') or {}).get('id') or '')
        if possession_id(play, team_ids) != source_id:
            estimate = -estimate
        result[str(play['id'])] = round(estimate, 4)
    return result
