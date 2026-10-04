"""AI Summary generation with caching for NFL game analysis."""

import os
import json
import hashlib
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Cache directory for Vercel serverless (uses /tmp)
CACHE_DIR = "/tmp/nfl_summaries"
SUMMARY_CACHE_VERSION = 7
FACTOR_REFERENCES = json.loads(Path(__file__).with_name('factor_gap_references.json').read_text())['full']
RATE_FACTORS = {'Success Rate', 'Explosive Play Rate'}
LOWER_IS_BETTER = {'Turnovers', 'Penalty Yards'}
SAMPLE_REQUIREMENTS = {
    'Success Rate': ('Offensive Plays', 20),
    'Adjusted Yards Per Play': ('Offensive Plays', 20),
    'Explosive Play Rate': ('Offensive Plays', 20),
    'Points Per Trip (Inside 40)': ('Points Per Trip (Inside 40)', 2),
    'Ave Start Field Pos': ('Drive Starts', 5),
}


def _summary_facts(payload: Optional[dict]) -> dict:
    if not payload:
        return {}
    return {
        "status": payload.get("status"),
        "teams": payload.get("team_meta"),
        "scores": payload.get("summary_table_full") or payload.get("summary_table"),
        "stats": payload.get("advanced_table_full") or payload.get("advanced_table"),
        "plays": payload.get("expanded_details_full") or payload.get("expanded_details"),
        "source_gaps": payload.get("source_gaps"),
    }


def _valid_summary(summary: str, payload: Optional[dict] = None) -> bool:
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 500:
        return False
    if not payload:
        return True

    stats = payload.get("advanced_table_full") or payload.get("advanced_table") or []
    turnovers = {row.get("Team"): row.get("Turnovers") for row in stats}
    team_names = {
        team.get("abbr"): team.get("name", "")
        for team in payload.get("team_meta", [])
        if isinstance(team, dict)
    }
    number_words = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    for team, giveaways in turnovers.items():
        if not team or not isinstance(giveaways, (int, float)):
            continue
        opponents = [count for other, count in turnovers.items()
                     if other != team and isinstance(count, (int, float))]
        if len(opponents) != 1:
            continue
        full_name = team_names.get(team, "")
        aliases = {team, full_name}
        if full_name:
            aliases.add(full_name.split()[-1])
        for alias in aliases - {""}:
            for number, noun in re.findall(
                rf"\b{re.escape(alias)}\b[^.!?]{{0,80}}?\b"
                r"(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
                r"(takeaways?|giveaways?)\b",
                summary,
                flags=re.IGNORECASE,
            ):
                expected = opponents[0] if noun.lower().startswith("takeaway") else giveaways
                stated = int(number) if number.isdigit() else number_words[number.lower()]
                if stated != expected:
                    return False
    return True

def get_cache_key(game_id: str, home_score: int, away_score: int, payload: Optional[dict] = None) -> str:
    """Version summaries by the facts they describe, not merely the score."""
    raw_key = json.dumps(
        [SUMMARY_CACHE_VERSION, os.environ.get('OPENAI_MODEL', 'gpt-5.6-luna'),
         game_id, home_score, away_score, _summary_facts(payload)],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw_key.encode()).hexdigest()

def get_cached_summary(game_id: str, home_score: int, away_score: int, payload: Optional[dict] = None) -> Optional[str]:
    """Retrieve cached summary if it exists and is not expired."""
    try:
        cache_key = get_cache_key(game_id, home_score, away_score, payload)
        cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")

        if not os.path.exists(cache_path):
            return None

        with open(cache_path, 'r') as f:
            data = json.load(f)

        # Check if expired (24 hours TTL)
        created = datetime.fromisoformat(data['created'])
        if datetime.now() - created > timedelta(hours=24):
            os.remove(cache_path)
            return None

        summary = data['summary']
        return summary if _valid_summary(summary, payload) else None
    except Exception:
        return None

def set_cached_summary(game_id: str, home_score: int, away_score: int, summary: str,
                       payload: Optional[dict] = None) -> bool:
    """Store summary in cache."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_key = get_cache_key(game_id, home_score, away_score, payload)
        cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")

        data = {
            'game_id': game_id,
            'home_score': home_score,
            'away_score': away_score,
            'summary': summary,
            'created': datetime.now().isoformat()
        }

        with open(cache_path, 'w') as f:
            json.dump(data, f)

        return True
    except Exception:
        return False

def _field_position_yards(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r'(Own|Opp)\s+(\d{1,2})', value)
    if not match:
        return None
    return int(match.group(2)) if match.group(1) == 'Own' else 100 - int(match.group(2))


def _factor_context(payload: dict, home: dict, away: dict) -> list:
    """Full-game factor gaps with the same reference values used by the UI."""
    rows = payload.get('advanced_table_full') or payload.get('advanced_table') or []
    details = payload.get('expanded_details_full') or payload.get('expanded_details') or {}
    by_team = {row.get('Team'): row for row in rows if isinstance(row, dict)}
    result = []
    for factor, reference in FACTOR_REFERENCES.items():
        values = {team['abbr']: by_team.get(team['abbr'], {}).get(factor) for team in (away, home)}
        a, h = values[away['abbr']], values[home['abbr']]
        if factor == 'Ave Start Field Pos':
            a, h = _field_position_yards(a), _field_position_yards(h)
        if not isinstance(a, (int, float)) or not isinstance(h, (int, float)):
            state = 'unavailable'
            gap = leader = None
        else:
            gap = round(abs(a - h) * (100 if factor in RATE_FACTORS else 1), 2)
            leader = None if a == h else (
                away['abbr'] if (a > h) != (factor in LOWER_IS_BETTER) else home['abbr']
            )
            state = 'available'
        requirement = SAMPLE_REQUIREMENTS.get(factor)
        samples = None
        if requirement:
            category, minimum = requirement
            samples = {
                team['abbr']: len((details.get(str(team.get('id'))) or {}).get(category) or [])
                for team in (away, home)
            }
            if state == 'available' and any(count < minimum for count in samples.values()):
                state = 'limited_sample'
        if factor == 'Penalty Yards' and state == 'available':
            for team in (away, home):
                penalties = (details.get(str(team.get('id'))) or {}).get('Penalty Yards') or []
                if any(p.get('penalty_status') == 'accepted' and
                       (p.get('yards') is None or p.get('team_attribution_note')) for p in penalties):
                    state = 'unresolved'
                    break
        unit = 'percentage points' if factor in RATE_FACTORS else (
            'yards per play' if factor == 'Adjusted Yards Per Play' else
            'points per trip' if factor == 'Points Per Trip (Inside 40)' else
            'yards' if factor in {'Ave Start Field Pos', 'Penalty Yards'} else
            'points' if factor == 'Non-Offensive Points' else 'turnovers'
        )
        row = {
            'factor': factor,
            'away': round(a * 100, 1) if a is not None and factor in RATE_FACTORS else values[away['abbr']],
            'home': round(h * 100, 1) if h is not None and factor in RATE_FACTORS else values[home['abbr']],
            'value_unit': 'percent' if factor in RATE_FACTORS else unit,
            'advantage': leader, 'gap': gap, 'unit': unit, 'state': state,
            'sample_counts': samples,
            'large_completed_game_gap': round(reference * (100 if factor in RATE_FACTORS else 1), 2),
            'gap_vs_reference': round(gap / (reference * (100 if factor in RATE_FACTORS else 1)), 2)
            if gap is not None and state == 'available' else None,
        }
        if factor == 'Turnovers':
            row['meaning'] = 'Giveaways by each team; fewer is better. A team’s takeaways equal its opponent’s giveaways.'
            unresolved = {gap.get('team') for gap in payload.get('source_gaps') or []
                          if gap.get('turnovers_gap')}
            breakdown = {}
            for team in (away, home):
                abbr = team['abbr']
                events = (details.get(str(team.get('id'))) or {}).get('Turnovers') or []
                count = values[abbr]
                breakdown[abbr] = dict(Counter(event.get('type') or 'Unknown' for event in events)) \
                    if abbr not in unresolved and isinstance(count, (int, float)) and len(events) == count else None
            row['turnover_types_by_team'] = breakdown
        result.append(row)
    return result


def _top_play_context(payload: dict, home: dict, away: dict) -> list:
    """Provide a few measured candidates, without treating a routine play as notable."""
    plays = [play for play in payload.get('plays') or [] if isinstance(play, dict)
             and not re.search(r'timeout|end of|warning|coin toss|kneel|spike', play.get('type') or '', re.I)
             and not re.search(r'\bNo Play\b', play.get('text') or '', re.I)]
    wp_plays = sorted(
        (play for play in plays if isinstance(play.get('homeWpDelta'), (int, float))
         and abs(play['homeWpDelta']) >= .05 and not play.get('wpAttributionUncertain')),
        key=lambda play: abs(play['homeWpDelta']), reverse=True,
    )[:4]
    epa_plays = sorted(
        (play for play in plays if isinstance(play.get('epa'), (int, float))),
        key=lambda play: abs(play['epa']), reverse=True,
    )[:2]
    selected = list(dict((str(play.get('id')), play) for play in [*wp_plays, *epa_plays]).values())
    context = []
    for play in selected:
        delta = play.get('homeWpDelta')
        wp_reliable = isinstance(delta, (int, float)) and not play.get('wpAttributionUncertain')
        badges = play.get('badges') or []
        if not isinstance(badges, list):
            badges = []
        context.append({
            'id': play.get('id'), 'quarter': play.get('quarter'), 'clock': play.get('clock'),
            'team_at_start': play.get('sourceTeam'), 'type': play.get('type'),
            'description': (play.get('text') or '')[:350],
            'wp_change_pp': round(abs(delta) * 100, 1) if wp_reliable else None,
            'wp_benefited_team': (home if delta > 0 else away)['abbr'] if wp_reliable and delta else None,
            'wp_before_percent': round((play.get('homeWpBefore') if delta > 0 else 1 - play.get('homeWpBefore')) * 100, 1)
            if wp_reliable and isinstance(play.get('homeWpBefore'), (int, float)) else None,
            'wp_after_percent': round((play.get('homeWpAfter') if delta > 0 else 1 - play.get('homeWpAfter')) * 100, 1)
            if wp_reliable and isinstance(play.get('homeWpAfter'), (int, float)) else None,
            'wp_attribution_uncertain': bool(play.get('wpAttributionUncertain')),
            'epa_for_team_at_start': round(play['epa'], 2) if isinstance(play.get('epa'), (int, float)) else None,
            'score_change': play.get('scoreChange'),
            'badges': [badge for badge in badges if isinstance(badge, (str, dict))],
        })
    return context


def generate_ai_summary(payload: dict, game_data: dict, probability_map: dict, wp_threshold: float = 0.975) -> Optional[str]:
    """
    Generate a concise game summary using OpenAI.
    Handles both completed and in-progress games.
    """
    try:
        from openai import OpenAI
    except ImportError:
        return None

    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None

    try:
        client = OpenAI(api_key=api_key)

        # Extract game info
        team_meta = payload.get('team_meta', [])
        summary_table = payload.get('summary_table', [])

        home_team = next((t for t in team_meta if t['homeAway'] == 'home'), None)
        away_team = next((t for t in team_meta if t['homeAway'] == 'away'), None)

        if not home_team or not away_team:
            return None

        home_abbr = home_team['abbr']
        away_abbr = away_team['abbr']
        home_name = home_team['name']
        away_name = away_team['name']

        # Get scores from summary table
        home_summary = next((s for s in summary_table if s['Team'] == home_abbr), {})
        away_summary = next((s for s in summary_table if s['Team'] == away_abbr), {})
        home_score = home_summary.get('Score', 0)
        away_score = away_summary.get('Score', 0)

        # Check cache first
        cached = get_cached_summary(payload.get('gameId', ''), home_score, away_score, payload)
        if cached:
            return cached

        game_status = payload.get('status', 'in-progress')

        story_facts = {
            'status': game_status,
            'clock': payload.get('gameClock'),
            'away': {'name': away_name, 'abbr': away_abbr, 'score': away_score},
            'home': {'name': home_name, 'abbr': home_abbr, 'score': home_score},
            'full_game_factors': _factor_context(payload, home_team, away_team),
            'top_play_candidates': _top_play_context(payload, home_team, away_team),
            'source_gaps': payload.get('source_gaps') or [],
        }
        user_prompt = (
            'In one or two conversational sentences, explain the score through the few factors that matter most. '
            'Lead with the strongest advantages for the team ahead; mention opposing advantages only as contrasts. '
            'If the factors do not explain the score, say so. Check every comparison against the data; do not invent causes or repeat the score. '
            'Mention a play only if unusually decisive. Treat live and incomplete data with appropriate caution.\n\n'
            f'Game data:\n{json.dumps(story_facts, ensure_ascii=False, indent=2)}'
        )

        model = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")
        completion_options = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You write concise, evidence-grounded NFL game stories."
                },
                {"role": "user", "content": user_prompt}
            ],
            "max_completion_tokens": 500 if model.startswith("gpt-5.6") else 300 if model.startswith("gpt-5") else 200,
        }
        if model.startswith("gpt-5.6"):
            completion_options["reasoning_effort"] = "low"
        elif model.startswith("gpt-5"):
            completion_options["reasoning_effort"] = "minimal"

        response = client.chat.completions.create(**completion_options)
        summary = (response.choices[0].message.content or "").strip()
        if not _valid_summary(summary, payload):
            retry_options = {
                **completion_options,
                "messages": [
                    *completion_options["messages"],
                    {"role": "assistant", "content": summary},
                    {"role": "user", "content": (
                        "Rewrite in one or two conversational sentences under 500 characters. "
                        "Keep claims grounded in the provided game data."
                    )},
                ],
            }
            response = client.chat.completions.create(**retry_options)
            summary = (response.choices[0].message.content or "").strip()
            if not _valid_summary(summary, payload):
                return None

        # Cache the result
        set_cached_summary(payload.get('gameId', ''), home_score, away_score, summary, payload)

        return summary

    except Exception as e:
        print(f"Warning: Could not generate AI summary: {e}")
        return None
