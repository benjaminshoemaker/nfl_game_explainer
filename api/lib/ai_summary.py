"""AI Summary generation with caching for NFL game analysis."""

import os
import json
import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional

# Cache directory for Vercel serverless (uses /tmp)
CACHE_DIR = "/tmp/nfl_summaries"
SUMMARY_CACHE_VERSION = 3


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
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 280:
        return False
    # The model receives a few play captions for context, but their attribution
    # is not checked here. Keep published summaries at the aggregate level.
    if re.search(r"\bQ[1-5]\b|\bintercept(?:ion|ed)?\b|\bfumbl\w*\b|\bmuff\w*\b", summary, re.IGNORECASE):
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
        [SUMMARY_CACHE_VERSION, game_id, home_score, away_score, _summary_facts(payload)],
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

def _extract_category_plays_by_team_abbr(expanded_details: dict, team_meta: list, category: str) -> dict:
    """
    Normalize expanded_details into a dict keyed by team abbreviation for one category.

    Supports both shapes:
    1) Team-keyed: {teamId: {category: [plays...]}}
    2) Category-keyed: {category: {teamAbbr: [plays...]}}
    """
    if not expanded_details or not isinstance(expanded_details, dict):
        return {}

    direct = expanded_details.get(category)
    if isinstance(direct, dict):
        return direct

    plays_by_abbr = {}
    for team in team_meta or []:
        team_id = str(team.get("id", "") or "")
        team_abbr = team.get("abbr")
        if not team_id or not team_abbr:
            continue
        team_details = expanded_details.get(team_id) or {}
        if not isinstance(team_details, dict):
            continue
        plays = team_details.get(category) or []
        if isinstance(plays, list):
            plays_by_abbr[team_abbr] = plays
    return plays_by_abbr


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
        advanced_table = payload.get('advanced_table_full') or payload.get('advanced_table', [])
        expanded_details = payload.get('expanded_details_full') or payload.get('expanded_details', {})

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

        # Get advanced stats
        home_advanced = next((s for s in advanced_table if s['Team'] == home_abbr), {})
        away_advanced = next((s for s in advanced_table if s['Team'] == away_abbr), {})

        # Game status
        game_status = payload.get('status', 'in-progress')
        is_final = game_status == 'final'

        # Build key plays summary
        turnovers = _extract_category_plays_by_team_abbr(expanded_details, team_meta, 'Turnovers')
        explosives = _extract_category_plays_by_team_abbr(expanded_details, team_meta, 'Explosive Plays')

        key_plays_text = []
        for team_abbr, plays in turnovers.items():
            for play in plays[:2]:  # Top 2 turnovers per team
                key_plays_text.append(
                    f"- Turnover ({team_abbr}): Q{play.get('quarter', '?')} "
                    f"{play.get('clock', '')} {play.get('text', '')}"
                )

        for team_abbr, plays in explosives.items():
            for play in plays[:2]:  # Top 2 explosive plays per team
                key_plays_text.append(
                    f"- Explosive ({team_abbr}): Q{play.get('quarter', '?')} "
                    f"{play.get('clock', '')} {play.get('text', '')}"
                )

        # Determine summary focus
        score_diff = abs(home_score - away_score)
        if is_final:
            if score_diff >= 14:
                winner = home_abbr if home_score > away_score else away_abbr
                summary_focus = f"why {winner} dominated"
            elif score_diff >= 7:
                winner = home_abbr if home_score > away_score else away_abbr
                summary_focus = f"how {winner} won"
            else:
                summary_focus = "why this was a close game"
        else:
            if home_score == away_score:
                summary_focus = "why the game is tied"
            else:
                leader = home_abbr if home_score > away_score else away_abbr
                summary_focus = f"why {leader} is leading"

        source_gaps = payload.get('source_gaps') or []
        source_note = (
            "Available play-by-play disagrees with ESPN box-score totals or offensive-play counts for "
            + ", ".join(str(gap.get('team')) for gap in source_gaps)
            + "; do not invent missing play details."
            if source_gaps else ""
        )

        # Build user prompt
        user_prompt = f"""Generate a game summary:

{away_name} ({away_abbr}) {away_score} @ {home_name} ({home_abbr}) {home_score}
Status: {'Final' if is_final else 'In Progress'}

Key Stats:
- {home_abbr}: {home_advanced.get('Success Rate', 0):.0%} success rate, {home_advanced.get('Turnovers', 0)} giveaways, {away_advanced.get('Turnovers', 0)} takeaways, {home_advanced.get('Explosive Plays', 0)} explosive plays
- {away_abbr}: {away_advanced.get('Success Rate', 0):.0%} success rate, {away_advanced.get('Turnovers', 0)} giveaways, {home_advanced.get('Turnovers', 0)} takeaways, {away_advanced.get('Explosive Plays', 0)} explosive plays

Key Plays:
{chr(10).join(key_plays_text[:6]) if key_plays_text else 'No key plays recorded'}

{source_note}

Write one sentence under 220 characters explaining {summary_focus}. Compare only the aggregate stats above; do not mention individual plays, quarters, timing, or players. A team's turnovers are its giveaways; its takeaways are the opponent's giveaways."""

        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        completion_options = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an NFL analyst. Write one concise sentence comparing verified aggregate game stats. Do not cite specific plays or players. No hashtags or emojis."
                },
                {"role": "user", "content": user_prompt}
            ],
            "max_completion_tokens": 300 if model.startswith("gpt-5") else 100,
        }
        if model.startswith("gpt-5"):
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
                        "Rewrite as one clear sentence under 220 characters. "
                        "Use only verified aggregate stats from the original game data. "
                        "Do not mention specific plays, players, timing, questions, or unsupported claims."
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
