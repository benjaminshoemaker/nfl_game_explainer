"""Pregame facts and optional, fact-linked OpenAI copy. No live sports calls."""
import hashlib
import json
import logging
import math
import os
import time
from datetime import datetime
from pathlib import Path

DATA_PATH = Path(__file__).with_name('data') / 'pregame.json'
CACHE_PATH = Path('/tmp/nfl_pregame')
PROMPT_VERSION = 1
ALIASES = {'WSH': 'WSH', 'WAS': 'WSH', 'LA': 'LAR'}


def load_preview(payload, path=None):
    if payload.get('status') != 'pregame':
        return None
    try:
        data = json.loads(Path(path or DATA_PATH).read_text())
        game = data['games'].get(str(payload['gameId']))
        if not game or payload.get('week', {}).get('number') != game['week']:
            return None
        if payload.get('week', {}).get('seasonType') != 2:
            return None
        if payload.get('season') != data['season'] or data['throughWeek'] != game['week'] - 1:
            return None
        if datetime.fromisoformat(data['publishedAt']) >= datetime.fromisoformat(game['kickoff']):
            return None
        for side in ['home', 'away']:
            team = next(t for t in payload['team_meta'] if t['homeAway'] == side)
            if ALIASES.get(team['abbr'], team['abbr']) != game[side]:
                return None
        ids = [game['away'], game['home']]
        teams = [next(t for t in data['teams'] if t['id'] == i) for i in ids]
        power = [next(t for t in data['power'] if t['id'] == i) for i in ids]
        if not all(math.isfinite(t['rating']) and math.isclose(sum(t['contributions'].values()), t['rating'], abs_tol=1e-8) for t in power):
            return None
        return {**{k: data[k] for k in ['season', 'throughWeek', 'publishedAt', 'factors', 'weights', 'modelSha256']},
                **game, 'teams': teams, 'power': power, 'narrative': None}
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        logging.warning('Pregame snapshot unavailable or incompatible')
        return None


def evidence(preview):
    """Use stable fact IDs so prose can be paired with source values in the UI."""
    facts = {}
    labels = {f['id']: f['label'] for f in preview['factors']}
    for team in preview['teams']:
        for key, sides in team['factors'].items():
            for side in ['own', 'opponent']:
                metric = sides[side]
                if metric.get('complete') and metric.get('value') is not None and metric.get('rank') is not None:
                    facts[f"{team['id']}.{key}.{side}"] = {
                        'team': team['id'], 'factor': labels[key],
                        'meaning': 'team output' if side == 'own' else 'opponents output against this team',
                        'value': metric['value'], 'rank': metric['rank'], 'rankPool': metric['rankPool'],
                        'tied': metric.get('tied', False),
                    }
    return facts


def valid_narrative(value, facts):
    if not isinstance(value, dict):
        return False
    def text_ok(text, limit):
        return isinstance(text, str) and 0 < len(text.strip()) <= limit
    if not text_ok(value.get('headline'), 150) or not text_ok(value.get('summary'), 450):
        return False
    watches = value.get('watchPoints')
    if not isinstance(watches, list) or not 1 <= len(watches) <= 3:
        return False
    used = set()
    for watch in watches:
        if not isinstance(watch, dict) or not text_ok(watch.get('title'), 120) or not text_ok(watch.get('body'), 450):
            return False
        ids = watch.get('factIds')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 4 or not all(isinstance(i, str) and i in facts for i in ids):
            return False
        key = tuple(sorted(ids))
        if key in used:
            return False
        used.add(key)
    return True


def generate_preview_copy(preview):
    if not os.environ.get('OPENAI_API_KEY'):
        return None
    facts = evidence(preview)
    if not facts:
        return None
    model = os.environ.get('OPENAI_MODEL', 'gpt-5.6-luna')
    context = {k: preview[k] for k in ['season', 'throughWeek', 'home', 'away', 'model', 'power']}
    context['facts'] = facts
    key = hashlib.sha256(json.dumps([PROMPT_VERSION, model, preview['modelSha256'], context], sort_keys=True).encode()).hexdigest()
    cache_file = CACHE_PATH / f'{key}.json'
    try:
        cached = json.loads(cache_file.read_text())
        if isinstance(cached, dict) and isinstance(cached.get('retryAfter'), (int, float)) and cached['retryAfter'] > time.time():
            return None
        if valid_narrative(cached, facts):
            return cached
    except (OSError, ValueError):
        pass
    schema = {'type': 'object', 'additionalProperties': False,
              'properties': {'headline': {'type': 'string'}, 'summary': {'type': 'string'},
                             'watchPoints': {'type': 'array', 'minItems': 1, 'maxItems': 3,
                               'items': {'type': 'object', 'additionalProperties': False,
                                 'properties': {'title': {'type': 'string'}, 'body': {'type': 'string'},
                                   'factIds': {'type': 'array', 'minItems': 1, 'maxItems': 4,
                                               'items': {'type': 'string', 'enum': list(facts)}}},
                                 'required': ['title', 'body', 'factIds']}}},
              'required': ['headline', 'summary', 'watchPoints']}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ['OPENAI_API_KEY'], timeout=18, max_retries=0)
        options = {'model': model, 'max_completion_tokens': 2400,
                   'response_format': {'type': 'json_schema', 'json_schema': {'name': 'pregame_preview', 'strict': True, 'schema': schema}},
                   'messages': [
                       {'role': 'system', 'content': (
                           'Write a concise, conversational NFL pregame preview using ONLY supplied facts. '
                           'Return headline (max 150 characters), summary (max 450), and up to three distinct watchPoints '
                           '(title max 120, body max 450), each citing 1–4 factIds supporting its claims. '
                           'Headline and summary must also be grounded in these facts. '
                           'Compare each offense to the opposing defense. Rank 1 is best; rates are fractions. '
                           'For turnovers, own means giveaways and opponent means takeaways. '
                           'Do not invent injuries, starters, schemes, weather, recent trends, or causes. '
                           'Frame implications as questions or possibilities, not certainties. '
                           'Avoid repeating the same angle across correlated metrics. '
                           'Model margin is HOME minus AWAY; never invent a win probability. '
                           'Model contributions differ from raw season statistics; influence is not predictive accuracy. '
                           'Use words in the prose rather than copying numeric values; the UI displays exact evidence separately.')},
                       {'role': 'user', 'content': json.dumps(context)}]}
        if model.startswith('gpt-5.6') or model.startswith('gpt-6'):
            options['reasoning_effort'] = 'low'
        elif model.startswith('gpt-5'):
            options['reasoning_effort'] = 'minimal'
        response = client.chat.completions.create(**options)
        value = json.loads(response.choices[0].message.content or '')
        if not valid_narrative(value, facts):
            return None
        try:
            CACHE_PATH.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(value))
        except OSError:
            pass  # An unavailable cache must not discard valid copy.
        return value
    except Exception as error:
        logging.warning('Pregame copy unavailable (%s); retaining statistical preview', type(error).__name__)
        try:
            CACHE_PATH.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps({'retryAfter': time.time() + 300}))
        except OSError:
            pass
        return None


def attach_preview(payload):
    preview = load_preview(payload)
    if preview:
        preview['narrative'] = generate_preview_copy(preview)
    payload['pregame_preview'] = preview
    payload['ai_summary'] = None
