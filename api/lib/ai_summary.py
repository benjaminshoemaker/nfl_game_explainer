"""AI Summary generation with caching for NFL game analysis."""

import os
import json
import hashlib
from datetime import datetime, timedelta

# Cache directory for Vercel serverless (uses /tmp)
CACHE_DIR = "/tmp/nfl_summaries"

def get_cache_key(game_id: str, home_score: int, away_score: int) -> str:
    """Generate cache key based on game ID and current scores."""
    raw_key = f"{game_id}_{home_score}_{away_score}"
    return hashlib.md5(raw_key.encode()).hexdigest()

def get_cached_summary(game_id: str, home_score: int, away_score: int) -> str | None:
    """Retrieve cached summary if it exists and is not expired."""
    try:
        cache_key = get_cache_key(game_id, home_score, away_score)
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

        return data['summary']
    except Exception:
        return None

def set_cached_summary(game_id: str, home_score: int, away_score: int, summary: str) -> bool:
    """Store summary in cache."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_key = get_cache_key(game_id, home_score, away_score)
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

def generate_ai_summary(payload: dict, game_data: dict, probability_map: dict, wp_threshold: float = 0.975) -> str | None:
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
        advanced_table = payload.get('advanced_table', [])
        expanded_details = payload.get('expanded_details', {})

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
        cached = get_cached_summary(payload.get('gameId', ''), home_score, away_score)
        if cached:
            return cached

        # Get advanced stats
        home_advanced = next((s for s in advanced_table if s['Team'] == home_abbr), {})
        away_advanced = next((s for s in advanced_table if s['Team'] == away_abbr), {})

        # Game status
        game_status = payload.get('status', 'in-progress')
        is_final = game_status == 'final'

        # Build key plays summary
        turnovers = expanded_details.get('Turnovers', {})
        explosives = expanded_details.get('Explosive Plays', {})

        key_plays_text = []
        for team_abbr, plays in turnovers.items():
            for play in plays[:2]:  # Top 2 turnovers per team
                key_plays_text.append(f"- Turnover ({team_abbr}): {play.get('text', '')}")

        for team_abbr, plays in explosives.items():
            for play in plays[:2]:  # Top 2 explosive plays per team
                key_plays_text.append(f"- Explosive ({team_abbr}): {play.get('text', '')}")

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

        # Build user prompt
        user_prompt = f"""Generate a game summary:

{away_name} ({away_abbr}) {away_score} @ {home_name} ({home_abbr}) {home_score}
Status: {'Final' if is_final else 'In Progress'}

Key Stats:
- {home_abbr}: {home_advanced.get('Success Rate', 0):.0%} success rate, {home_advanced.get('Turnovers', 0)} turnovers, {home_advanced.get('Explosive Plays', 0)} explosive plays
- {away_abbr}: {away_advanced.get('Success Rate', 0):.0%} success rate, {away_advanced.get('Turnovers', 0)} turnovers, {away_advanced.get('Explosive Plays', 0)} explosive plays

Key Plays:
{chr(10).join(key_plays_text[:6]) if key_plays_text else 'No key plays recorded'}

Write 2-3 sentences (max 280 chars) explaining {summary_focus}. Focus on turnovers, explosive plays, and efficiency. Be specific about what happened."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an NFL analyst. Write extremely concise game summaries (max 280 characters). Focus on the key factors: turnovers, explosive plays, and efficiency. No hashtags or emojis."
                },
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=100,
            temperature=0.7
        )

        summary = response.choices[0].message.content.strip()

        # Cache the result
        set_cached_summary(payload.get('gameId', ''), home_score, away_score, summary)

        return summary

    except Exception as e:
        print(f"Warning: Could not generate AI summary: {e}")
        return None
