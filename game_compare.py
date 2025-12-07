import argparse
import os
import io
import csv
import requests
import pandas as pd
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv('.env.local')

GAME_SUMMARY_SYSTEM_PROMPT = """You are a sports analyst generating tweet-length NFL game summaries. Your summaries must be statistically grounded and narratively compelling.

## DECISION FRAMEWORK

Execute this sequence for each game:

1. **Identify the narrative pattern** from the WP trajectory:
   - BLOWOUT: Winner led by 17+ points, WP never competitive after Q1
   - CONTROLLED: Steady WP ramp, no 50% line crossings after early game
   - COMEBACK: Winner's WP dropped below 25% at some point
   - BACK-AND-FORTH: 3+ crossings of the 50% WP line
   - SINGLE-PLAY-DECISIVE: One play with ≥20% WP delta that the game never recovered from

2. **Check for "despite" trigger**: If winning team lost 3+ statistical categories, lead with what DID explain the win (usually turnovers, explosive plays, or non-offensive points).

3. **Select your lead** using these rules:
   - SINGLE PLAY: If any play has ≥20% WP delta AND occurred Q4/OT AND WP never recovered → lead with that play
   - SINGLE PLAY: If max WP delta is 15-19% and no dominant statistical factor → lead with that play
   - DOMINANT FACTOR: If no play ≥15% WP delta AND one factor shows clear dominance (+3 turnovers, 200+ yard advantage) → lead with factor
   - DESPITE NARRATIVE: If winning team lost 3+ stat categories → lead with "wins despite [deficit], [explanation]"
   - SCORE ITSELF: If margin is 30+ points → lead with the historic margin

## WP DELTA THRESHOLDS

| Category | WP Delta | Action |
|----------|----------|--------|
| Game-changing | ≥20% | MUST mention; likely should lead |
| Major impact | 15-19% | Strong mention candidate; lead if no 20%+ plays |
| Key play | 10-14% | Mention if space permits |
| Moderate | 5-9% | Only if exemplifies theme |
| Routine | <5% | Do not mention individually |

## FACTOR HIERARCHY

**Tier 1 (lead with these):**
- Turnovers: ~4 points per turnover; 70% win rate when winning battle
- Non-offensive points: Pick-sixes, fumble returns, ST TDs—rare and narrative-worthy
- Explosive play rate: Drives with explosives see expected points nearly quadruple

**Tier 2 (strong support):**
- Yards per play, Success rate, Points per trip inside 40

**Tier 3 (contextual only):**
- Field position, Raw explosive count, Possession count, Penalty yards

## STYLE RULES

- Start with final score in first sentence (ALWAYS)
- Match verb to margin: "cruised" (17+), "beats" (10-16), "edges" (3-9), "survives/escapes" (1-2), "outlasts" (OT)
- Use correlation language, NOT causation: "won with +3 turnover margin" not "won because of turnovers"
- Include player names for decisive plays
- Every word must add information—no "great game" or "big win"

## ANTI-PATTERNS (DO NOT DO THESE)

- Never lead with penalty yards unless a specific penalty directly decided the game
- Never treat yards as deterministic—teams win despite being outgained 30% of the time
- Never mention possession count without explaining what drove it
- Never ignore that late-game plays matter more (same INT is 25% WP delta in Q4 vs 8% in Q1)
- Never miss cluster patterns—three 8% plays on one drive (24% cumulative) beats one 15% play

## OUTPUT FORMAT

Target exactly 280 characters. Maximum 300 characters. Structure by narrative type:

BLOWOUT: [Team] [cruised/dominated] [opponent], [score]. [Star]: [stat line]. [Control narrative].

CLOSE GAME - SINGLE PLAY: [Team] [edges/survives] [opponent] [score] on [decisive play with context]. [Supporting detail].

DESPITE: [Team] wins [score] despite [deficit]. [What overcame it—turnovers/ST/explosives].

BACK-AND-FORTH: [Team] [survives] [score] over [opponent] in [thriller/OT]. [Volatility description]. [Star line].

DEFENSIVE DOMINANCE: [Team]'s defense [key stat] in [score] win. [Conversion to points] + [supporting stat]."""
SUMMARY_COLS = ['Team', 'Score', 'Total Yards', 'Drives']
ADVANCED_COLS = [
    'Team', 'Score', 'Turnovers', 'Total Yards', 'Yards Per Play',
    'Success Rate', 'Explosive Plays', 'Explosive Play Rate',
    'Points Per Trip (Inside 40)', 'Ave Start Field Pos',
    'Penalty Yards', 'Non-Offensive Points'
]
EXPANDED_CATEGORIES = ['Turnovers', 'Explosive Plays', 'Non-Offensive Scores']


def yardline_to_coord(pos_text, team_abbr):
    """
    Convert a possessionText like 'SEA 24' into a 0-100 coordinate
    from the perspective of team_abbr's own goal line.
    """
    if not pos_text or not team_abbr:
        return None
    parts = pos_text.strip().split()
    if len(parts) != 2:
        return None
    side, yard_str = parts
    try:
        yard = int(yard_str)
    except ValueError:
        return None
    side = side.upper()
    team_abbr = team_abbr.upper()
    if side == team_abbr:
        return yard
    return 100 - yard


def parse_clock_to_seconds(display_value):
    """Convert a clock display like '12:07' to seconds; return None if invalid."""
    if not display_value or ':' not in display_value:
        return None
    try:
        minutes, seconds = display_value.split(':')
        return int(minutes) * 60 + int(seconds)
    except ValueError:
        return None


def get_game_data(game_id):
    """Pull the full game play-by-play JSON from ESPN core API."""
    import time
    cache_buster = int(time.time())
    url = f"https://cdn.espn.com/core/nfl/playbyplay?xhr=1&gameId={game_id}&cb={cache_buster}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data.get('gamepackageJSON', {})

def get_play_probabilities(game_id):
    """
    Pull the v2 probabilities feed and map play_id -> probability payload.
    Returns a dict mapping play_id -> probability payload.
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    base = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{game_id}/competitions/{game_id}/probabilities"
    prob_map = {}

    def extract_play_id(play_ref):
        if not play_ref:
            return None
        from urllib.parse import urlparse
        path = urlparse(play_ref).path
        if not path:
            return None
        return path.rstrip('/').split('/')[-1]

    page = 1
    page_count = 1
    while page <= page_count:
        try:
            resp = requests.get(f"{base}?page={page}", headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            break

        items = data.get('items') or []
        for item in items:
            pid = extract_play_id(item.get('play', {}).get('$ref')) or item.get('id')
            if pid is None:
                continue
            prob_map[str(pid)] = {
                "homeWinPercentage": item.get("homeWinPercentage"),
                "awayWinPercentage": item.get("awayWinPercentage"),
                "tiePercentage": item.get("tiePercentage")
            }
        page_count = data.get('pageCount') or page_count
        page += 1

    return prob_map


def get_pregame_probabilities(game_id):
    """
    Fetch pre-game win probabilities from ESPN summary winprobability array.
    Uses the first entry as the opening WP; returns (home_wp, away_wp).
    Falls back to (0.5, 0.5) if unavailable.
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json() or {}
    except Exception:
        return 0.5, 0.5

    def clamp(val, fallback=0.5):
        try:
            return max(0.0, min(1.0, float(val)))
        except (TypeError, ValueError):
            return fallback

    wp_list = data.get('winprobability') or []
    if not wp_list or not isinstance(wp_list, list):
        return 0.5, 0.5

    first = wp_list[0] or {}
    home_wp = clamp(first.get('homeWinPercentage'), fallback=0.5)
    away_wp = clamp(1.0 - home_wp, fallback=0.5)
    return home_wp, away_wp


def latest_play_from_core(game_data):
    """Return (period, clock_seconds) of the last play in drives.previous."""
    drives = game_data.get('drives', {}).get('previous', [])
    if not drives:
        return None, None
    last_drive = drives[-1]
    plays = last_drive.get('plays', [])
    if not plays:
        return None, None
    last_play = plays[-1]
    period = last_play.get('period', {}).get('number')
    clock_display = last_play.get('clock', {}).get('displayValue')
    return period, parse_clock_to_seconds(clock_display)


def latest_play_from_v2(game_id):
    return None, None


def build_competitive_plays_csv(game_data, probability_map, wp_threshold=0.975):
    """
    Build a CSV string of all competitive plays for the LLM.

    Returns:
        str: CSV-formatted string with headers
    """
    output = io.StringIO()
    fieldnames = [
        'quarter', 'clock', 'drive_team', 'play_type', 'text',
        'home_score', 'away_score', 'start_home_wp', 'start_away_wp',
        'end_home_wp', 'end_away_wp', 'home_delta', 'away_delta'
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    # Get team abbrevs
    teams_info = game_data.get('boxscore', {}).get('teams', [])
    id_to_abbr = {}
    for t in teams_info:
        tid = t.get('team', {}).get('id')
        abbr = t.get('team', {}).get('abbreviation')
        if tid and abbr:
            id_to_abbr[tid] = abbr

    prev_home_wp = 0.5
    prev_away_wp = 0.5

    drives = game_data.get('drives', {}).get('previous', [])

    for drive in drives:
        drive_team_id = drive.get('team', {}).get('id')
        drive_team = id_to_abbr.get(drive_team_id, '?')

        for play in drive.get('plays', []):
            play_id = str(play.get('id', ''))
            period = play.get('period', {}).get('number', 0)

            # Get current WP
            prob = probability_map.get(play_id)
            if prob:
                home_wp = prob.get('homeWinPercentage', 0.5)
                away_wp = prob.get('awayWinPercentage', 0.5)
            else:
                home_wp = prev_home_wp
                away_wp = prev_away_wp

            # Check if competitive (OT always competitive)
            if period < 5:
                if home_wp >= wp_threshold or away_wp >= wp_threshold:
                    # Update prev and skip
                    prev_home_wp = home_wp
                    prev_away_wp = away_wp
                    continue

            # Calculate deltas
            home_delta = round((home_wp - prev_home_wp) * 100, 1)
            away_delta = round((away_wp - prev_away_wp) * 100, 1)

            row = {
                'quarter': period,
                'clock': play.get('clock', {}).get('displayValue', ''),
                'drive_team': drive_team,
                'play_type': play.get('type', {}).get('text', 'Unknown'),
                'text': (play.get('text', '') or '')[:150],  # Truncate long plays
                'home_score': play.get('homeScore', ''),
                'away_score': play.get('awayScore', ''),
                'start_home_wp': round(prev_home_wp * 100, 1),
                'start_away_wp': round(prev_away_wp * 100, 1),
                'end_home_wp': round(home_wp * 100, 1),
                'end_away_wp': round(away_wp * 100, 1),
                'home_delta': home_delta,
                'away_delta': away_delta
            }
            writer.writerow(row)

            # Update previous
            prev_home_wp = home_wp
            prev_away_wp = away_wp

    return output.getvalue()


def calculate_wp_trajectory_stats(game_data, probability_map, winner_is_home):
    """
    Calculate WP trajectory statistics for narrative detection.

    Returns:
        dict with:
        - winner_min_wp: Lowest WP the winner had during the game
        - wp_crossings: Number of times WP crossed the 50% line
        - max_wp_delta: Largest single-play WP swing (absolute value)
        - max_wp_play_desc: Description of the max delta play
    """
    winner_min_wp = 100.0
    wp_crossings = 0
    max_wp_delta = 0.0
    max_wp_play_desc = ""

    prev_home_wp = 0.5
    prev_above_50 = None  # Track which side of 50% we're on

    drives = game_data.get('drives', {}).get('previous', [])

    for drive in drives:
        for play in drive.get('plays', []):
            play_id = str(play.get('id', ''))
            prob = probability_map.get(play_id)

            if not prob:
                continue

            home_wp = prob.get('homeWinPercentage', 0.5)
            away_wp = prob.get('awayWinPercentage', 0.5)

            # Track winner's minimum WP
            winner_wp = home_wp if winner_is_home else away_wp
            if winner_wp < winner_min_wp:
                winner_min_wp = winner_wp

            # Track 50% line crossings
            currently_above_50 = home_wp > 0.5
            if prev_above_50 is not None and currently_above_50 != prev_above_50:
                wp_crossings += 1
            prev_above_50 = currently_above_50

            # Track max WP delta
            delta = abs(home_wp - prev_home_wp) * 100
            if delta > max_wp_delta:
                max_wp_delta = delta
                play_text = (play.get('text', '') or '')[:80]
                play_type = play.get('type', {}).get('text', 'Play')
                quarter = play.get('period', {}).get('number', '?')
                clock = play.get('clock', {}).get('displayValue', '?')
                max_wp_play_desc = f"Q{quarter} {clock} - {play_type}: {play_text}"

            prev_home_wp = home_wp

    return {
        'winner_min_wp': round(winner_min_wp * 100, 1),
        'wp_crossings': wp_crossings,
        'max_wp_delta': round(max_wp_delta, 1),
        'max_wp_play_desc': max_wp_play_desc
    }


def generate_game_summary(payload, competitive_plays_csv, wp_trajectory_stats, wp_threshold=0.975):
    """
    Generate a concise game summary using OpenAI.

    Args:
        payload: The game data payload with summary_table, advanced_table, team_meta
        competitive_plays_csv: String containing CSV of all competitive plays
        wp_trajectory_stats: Dict with winner_min_wp, wp_crossings, max_wp_delta, max_wp_play_desc
        wp_threshold: The WP threshold used for filtering

    Returns:
        str: Generated summary, or None if generation fails
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None

    try:
        client = OpenAI(api_key=api_key)

        # Extract game info
        team_meta = payload.get('team_meta', [])
        away = next((t for t in team_meta if t.get('homeAway') == 'away'), {})
        home = next((t for t in team_meta if t.get('homeAway') == 'home'), {})
        away_abbr = away.get('abbr', 'AWAY')
        home_abbr = home.get('abbr', 'HOME')
        away_name = away.get('name', away_abbr)
        home_name = home.get('name', home_abbr)

        # Get scores
        summary_map = {row.get('Team'): row for row in payload.get('summary_table', [])}
        away_score = summary_map.get(away_abbr, {}).get('Score', 0)
        home_score = summary_map.get(home_abbr, {}).get('Score', 0)
        winner_abbr = home_abbr if home_score > away_score else away_abbr

        # Get advanced stats (use filtered stats)
        advanced_map = {row.get('Team'): row for row in payload.get('advanced_table', [])}
        away_stats = advanced_map.get(away_abbr, {})
        home_stats = advanced_map.get(home_abbr, {})

        # Build user prompt
        user_prompt = f"""Generate a game summary for:

{away_name} ({away_abbr}) {away_score} @ {home_name} ({home_abbr}) {home_score}
Winner: {winner_abbr}

## TEAM STATS (competitive plays only, WP < {wp_threshold*100:.1f}%):

{away_abbr}:
- Turnovers: {away_stats.get('Turnovers', 'N/A')}
- Yards Per Play: {away_stats.get('Yards Per Play', 'N/A')}
- Success Rate: {away_stats.get('Success Rate', 'N/A')}
- Explosive Plays: {away_stats.get('Explosive Plays', 'N/A')}
- Explosive Play Rate: {away_stats.get('Explosive Play Rate', 'N/A')}
- Points Per Trip (Inside 40): {away_stats.get('Points Per Trip (Inside 40)', 'N/A')}
- Field Position: {away_stats.get('Ave Start Field Pos', 'N/A')}
- Penalty Yards: {away_stats.get('Penalty Yards', 'N/A')}
- Non-Offensive Points: {away_stats.get('Non-Offensive Points', 'N/A')}
- Possessions: {summary_map.get(away_abbr, {}).get('Drives', 'N/A')}

{home_abbr}:
- Turnovers: {home_stats.get('Turnovers', 'N/A')}
- Yards Per Play: {home_stats.get('Yards Per Play', 'N/A')}
- Success Rate: {home_stats.get('Success Rate', 'N/A')}
- Explosive Plays: {home_stats.get('Explosive Plays', 'N/A')}
- Explosive Play Rate: {home_stats.get('Explosive Play Rate', 'N/A')}
- Points Per Trip (Inside 40): {home_stats.get('Points Per Trip (Inside 40)', 'N/A')}
- Field Position: {home_stats.get('Ave Start Field Pos', 'N/A')}
- Penalty Yards: {home_stats.get('Penalty Yards', 'N/A')}
- Non-Offensive Points: {home_stats.get('Non-Offensive Points', 'N/A')}
- Possessions: {summary_map.get(home_abbr, {}).get('Drives', 'N/A')}

## WP TRAJECTORY ANALYSIS:

- Winner's minimum WP during game: {wp_trajectory_stats.get('winner_min_wp', 'N/A')}%
- Number of 50% line crossings: {wp_trajectory_stats.get('wp_crossings', 'N/A')}
- Largest single-play WP delta: {wp_trajectory_stats.get('max_wp_delta', 'N/A')}% ({wp_trajectory_stats.get('max_wp_play_desc', 'N/A')})

## FULL PLAY-BY-PLAY (competitive plays only):
{competitive_plays_csv}

Instructions:
1. Scan the home_delta and away_delta columns to find high-leverage plays (≥10%)
2. Identify the narrative pattern from the WP trajectory
3. Check if winner lost 3+ stat categories (despite narrative)
4. Apply the decision framework from your system instructions
5. Generate a ~280 character summary (max 300)"""

        model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        # Some models (o-series) require max_completion_tokens and may not support temperature.
        request_params = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": GAME_SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
        }
        # Models that require max_completion_tokens instead of max_tokens
        # Reasoning models (o-series, gpt-5) need higher limits for internal thinking
        if model_name.startswith("o1") or model_name.startswith("o3") or model_name.startswith("gpt-5"):
            request_params["max_completion_tokens"] = 16000
        else:
            request_params["max_tokens"] = 300
            request_params["temperature"] = 0.7

        try:
            response = client.chat.completions.create(**request_params)
        except Exception as inner_e:
            # Fallback: swap token parameter in case of model-specific requirement.
            if "max_tokens" in request_params:
                request_params.pop("max_tokens", None)
                request_params["max_completion_tokens"] = 16000
            else:
                request_params.pop("max_completion_tokens", None)
                request_params["max_tokens"] = 300
            # Some models may not support temperature; drop it on retry.
            request_params.pop("temperature", None)
            response = client.chat.completions.create(**request_params)

        content = response.choices[0].message.content
        summary = (content or "").strip()

        # Remove quotes if the model wrapped the response
        if summary.startswith('"') and summary.endswith('"'):
            summary = summary[1:-1]

        # Truncate if over 300 chars
        if len(summary) > 300:
            summary = summary[:297] + "..."

        return summary

    except Exception as e:
        # Fail silently
        print(f"Warning: Could not generate AI summary: {e}")
        return None

def calculate_success(down, distance, yards_gained):
    """
    Determine if a play was 'successful' based on standard analytics definition:
    - 1st Down: Gained >= 40% of yards to go
    - 2nd Down: Gained >= 60% of yards to go
    - 3rd/4th Down: Gained 100% of yards to go (converted)
    """
    if down == 1:
        return yards_gained >= (0.4 * distance)
    elif down == 2:
        return yards_gained >= (0.6 * distance)
    elif down in [3, 4]:
        return yards_gained >= distance
    return False


def any_stat_contains(play, needles):
    """Check play.statistics for type text/abbreviation hits."""
    for stat in play.get('statistics', []):
        stat_type = stat.get('type', {})
        abbr = str(stat_type.get('abbreviation', '')).lower()
        text = str(stat_type.get('text', '')).lower()
        for n in needles:
            if n in abbr or n in text:
                return True
    return False


def is_penalty_play(play, text_lower, type_lower):
    if play.get('penalty') and 'no play' in text_lower:
        return True
    if play.get('hasPenalty'):
        return True
    if 'no play' in text_lower and ('penalty' in text_lower or 'penalty' in type_lower):
        return True
    return False


def is_spike_or_kneel(text_lower, type_lower):
    if 'spike' in text_lower or 'spike' in type_lower:
        return True
    if 'kneel' in text_lower or 'kneel' in type_lower or 'qb kneel' in text_lower:
        return True
    return False


def is_special_teams_play(text_lower, type_lower):
    if 'touchdown' in text_lower or 'touchdown' in type_lower:
        return False
    st_keywords = ['punt', 'kickoff', 'field goal', 'extra point', 'xp', 'fg', 'onside']
    return any(k in text_lower or k in type_lower for k in st_keywords)


def is_nullified_play(text_lower):
    return 'nullified' in text_lower or 'no play' in text_lower


def classify_offense_play(play):
    """
    Decide if a play should count toward offensive SR/YPP/explosives.
    Returns (is_offense_play, is_run, is_pass) where scrambles/sacks are treated as pass.
    """
    text_lower = play.get('text', '').lower()
    type_lower = play.get('type', {}).get('text', 'unknown').lower()
    if is_nullified_play(text_lower):
        return False, False, False
    if is_penalty_play(play, text_lower, type_lower):
        return False, False, False
    if is_spike_or_kneel(text_lower, type_lower):
        return False, False, False
    if is_special_teams_play(text_lower, type_lower):
        return False, False, False

    pass_hint = any_stat_contains(play, ['pass', 'sack']) or 'pass' in type_lower or 'sack' in type_lower or 'scramble' in type_lower or 'pass' in text_lower or 'sack' in text_lower or 'scramble' in text_lower
    rush_hint = any_stat_contains(play, ['rush']) or 'rush' in type_lower or 'run' in text_lower

    # Scrambles should be treated as pass dropbacks, not runs.
    if pass_hint and rush_hint and ('scramble' in text_lower or 'scramble' in type_lower):
        rush_hint = False

    return True, rush_hint, pass_hint

def is_competitive_play(play, probability_map, wp_threshold=0.975):
    """
    Return True if the play occurred while the game was still competitive.

    Competitive if:
    - Overtime period (period number >= 5)
    - No play id or no probability data (assume competitive)
    - Both teams' win probability are below the threshold at play start
    """
    period = play.get('period', {}).get('number', 0)
    if period >= 5:
        return True

    play_id = play.get('id')
    if play_id is None:
        return True

    prob = (probability_map or {}).get(str(play_id))
    if not prob:
        return True

    home_wp = prob.get('homeWinPercentage', 0.5)
    away_wp = prob.get('awayWinPercentage', 0.5)
    return home_wp < wp_threshold and away_wp < wp_threshold

def process_game_stats(game_data, expanded=False, probability_map=None, pregame_probabilities=None, wp_threshold=0.975):
    boxscore = game_data.get('boxscore', {})
    teams_info = boxscore.get('teams', [])
    id_to_abbr = {}
    probability_map = probability_map or {}
    drives = game_data.get('drives', {}).get('previous', [])
    try:
        preg_home, preg_away = pregame_probabilities or (0.5, 0.5)
    except Exception:
        preg_home, preg_away = 0.5, 0.5

    def sanitize_prob(val, fallback=0.5):
        try:
            return max(0.0, min(1.0, float(val)))
        except (TypeError, ValueError):
            return fallback

    # Map play_id -> drive offensive team for later attribution (e.g., non-offensive scores)
    play_to_drive_team = {}
    for drive in drives:
        drive_team_id = drive.get('team', {}).get('id')
        for play in drive.get('plays', []):
            play_id = play.get('id')
            if play_id:
                play_to_drive_team[str(play_id)] = drive_team_id

    # Track previous WP for delta calculation, seeded from pre-game projections when available
    prev_home_wp = sanitize_prob(preg_home)
    prev_away_wp = sanitize_prob(preg_away, fallback=1 - prev_home_wp)

    def lookup_probability_with_delta(play):
        """Compute WP and delta from previous play. Does NOT update prev."""
        pid = play.get('id')
        if pid is None:
            return None
        prob = probability_map.get(str(pid))
        if not prob:
            return None

        home_wp = prob.get('homeWinPercentage', 0.5)
        away_wp = prob.get('awayWinPercentage', 0.5)

        # Compute delta (positive = good for that team)
        home_delta = home_wp - prev_home_wp
        away_delta = away_wp - prev_away_wp

        return {
            'homeWinPercentage': home_wp,
            'awayWinPercentage': away_wp,
            'tiePercentage': prob.get('tiePercentage', 0),
            'homeDelta': home_delta,
            'awayDelta': away_delta
        }

    def update_prev_wp(play):
        """Update prev WP tracking. Call at end of every play."""
        nonlocal prev_home_wp, prev_away_wp
        pid = play.get('id')
        if pid is None:
            return
        prob = probability_map.get(str(pid))
        if prob:
            prev_home_wp = prob.get('homeWinPercentage', prev_home_wp)
            prev_away_wp = prob.get('awayWinPercentage', prev_away_wp)

    for t in teams_info:
        tid = t.get('team', {}).get('id')
        abbr = t.get('team', {}).get('abbreviation')
        if tid and abbr:
            id_to_abbr[tid] = abbr
    scoring_map = {}
    scoring_plays = game_data.get('scoringPlays', [])
    if scoring_plays:
        prev_home = 0
        prev_away = 0
        # Determine which competitor is home/away
        comps = game_data.get('header', {}).get('competitions', [])
        home_id = away_id = None
        if comps:
            for comp in comps[0].get('competitors', []):
                if comp.get('homeAway') == 'home':
                    home_id = comp.get('id')
                elif comp.get('homeAway') == 'away':
                    away_id = comp.get('id')

        for sp in scoring_plays:
            h = sp.get('homeScore', 0)
            a = sp.get('awayScore', 0)
            dh = h - prev_home
            da = a - prev_away
            prev_home, prev_away = h, a
            points = dh if dh > 0 else da
            scoring_map[sp.get('id')] = {
                'team': sp.get('team', {}).get('id'),
                'points': points
            }
    
    # Initialize storage for both teams
    stats = {}
    details = {}
    for team in teams_info:
        t_id = team['team']['id']
        t_name = team['team']['abbreviation']
        stats[t_id] = {
            'Team': t_name,
            'Score': 0, # Will fill from live score
            'Plays': 0,
            'Total Yards': 0,
            'Successful Plays': 0,
            'Explosive Plays': 0, # Run > 10, Pass > 20
            'Turnovers': 0, # Ints + Fumbles Lost
            'Drives Inside 40': 0,
            'Points Inside 40': 0,
            'Start Field Pos Sum': 0,
            'Drives Count': 0,
            'Drive Points': 0,
            'Punt Net Sum': 0,
            'Punt Plays': 0,
            'Kick Net Sum': 0,
            'Kick Plays': 0,
            'ST Penalties': 0,
            'Penalty Yards': 0,
            'Penalty Count': 0,
            'Non-Offensive Points': 0
        }
        if expanded:
            details[t_id] = {
                'Turnovers': [],
                'Explosive Plays': [],
                'Net Punting': [],
                'Net Kickoff': [],
                'Hidden Yards': [],
                'ST Penalties': [],
                'Non-Offensive Scores': []
            }

    # --- 1. Get High Level Score/Turnovers ---
    competitions = game_data.get('header', {}).get('competitions', [])
    if competitions:
        header = competitions[0]
        for competitor in header.get('competitors', []):
            t_id = competitor['id']
            if t_id in stats:
                stats[t_id]['Score'] = int(competitor.get('score', 0))

    # --- Penalty totals from boxscore (COUNT-YARDS) ---
    for t in teams_info:
        t_id = t.get('team', {}).get('id')
        if not t_id or t_id not in stats:
            continue
        team_stats = t.get('statistics', [])
        for stat in team_stats:
            stat_name = stat.get('name', '')
            # Look specifically for totalPenaltiesYards (format: "COUNT-YARDS")
            if stat_name == 'totalPenaltiesYards':
                display_val = stat.get('displayValue', '')
                if isinstance(display_val, str) and '-' in display_val:
                    parts = display_val.split('-')
                    if len(parts) == 2:
                        try:
                            count = int(parts[0])
                            yards = int(parts[1])
                            stats[t_id]['Penalty Count'] = count
                            stats[t_id]['Penalty Yards'] = yards
                        except ValueError:
                            pass
                break

    # --- Non-Offensive Points (defense/special teams/safeties) ---
    for sp in scoring_plays:
        if not is_competitive_play(sp, probability_map, wp_threshold):
            continue
        play_id = sp.get('id')
        scoring_team_id = sp.get('team', {}).get('id')
        drive_offense_id = play_to_drive_team.get(str(play_id))
        play_text = str(sp.get('text', '')).lower()
        play_type = str(sp.get('type', {}).get('text', '')).lower()
        scoring_type = str(sp.get('scoringType', {}).get('name', '')).lower()

        points = scoring_map.get(play_id, {}).get('points', 0)
        is_safety = 'safety' in play_type or 'safety' in scoring_type or 'safety' in play_text
        is_non_offensive = False

        if is_safety:
            is_non_offensive = True
            points = 2  # Safeties are always 2 points
        elif drive_offense_id and scoring_team_id and drive_offense_id != scoring_team_id:
            is_non_offensive = True

        if is_non_offensive and scoring_team_id in stats:
            stats[scoring_team_id]['Non-Offensive Points'] += points
            if expanded:
                details[scoring_team_id]['Non-Offensive Scores'].append({
                    'type': sp.get('type', {}).get('text', ''),
                    'text': sp.get('text', ''),
                    'points': points,
                    'quarter': sp.get('period', {}).get('number'),
                    'clock': sp.get('clock', {}).get('displayValue'),
                })

    # --- 2. Process Drives and Plays (The "How") ---
    drives = drives or []
    
    for drive in drives:
        team_id = drive.get('team', {}).get('id')
        if team_id not in stats:
            continue
        
        drive_plays = drive.get('plays', [])
        drive_total_yards = drive.get('yards', 0)
        drive_start_yte = drive.get('start', {}).get('yardsToEndzone', -1)
        drive_points_competitive = 0
        drive_crossed_40_competitive = False
        drive_started_competitive = False
        drive_first_play_checked = False

        # --- Process Plays for Efficiency/Explosives ---
        for play in drive_plays:
            text = play.get('text', '')
            text_lower = text.lower()
            play_type = play.get('type', {}).get('text', 'Unknown')
            play_type_lower = play_type.lower()
            start_team_id = play.get('start', {}).get('team', {}).get('id') or team_id
            end_team_id = play.get('end', {}).get('team', {}).get('id')
            team_abbrev = play.get('team', {}).get('abbreviation', '').lower()
            # Fallback to drive team abbreviation when play-level team is missing.
            offense_abbrev = team_abbrev or id_to_abbr.get(team_id, '').lower()
            opponent_id = None
            if len(id_to_abbr) == 2 and start_team_id in id_to_abbr:
                opponent_id = next((tid for tid in id_to_abbr if tid != start_team_id), None)

            competitive = is_competitive_play(play, probability_map, wp_threshold)

            # Track drive start stats only when the opening play was competitive.
            if not drive_first_play_checked:
                drive_first_play_checked = True
                drive_started_competitive = competitive
                start_yte = play.get('start', {}).get('yardsToEndzone', -1)
                if start_yte == -1:
                    start_yte = drive.get('start', {}).get('yardsToEndzone', -1)
                if start_yte != -1:
                    drive_start_yte = start_yte
                if drive_started_competitive and start_yte != -1:
                    start_loc = 100 - start_yte
                    stats[team_id]['Start Field Pos Sum'] += start_loc
                    stats[team_id]['Drives Count'] += 1

            if competitive and drive_started_competitive and not drive_crossed_40_competitive:
                yte = play.get('start', {}).get('yardsToEndzone', 100)
                try:
                    if yte <= 40:
                        drive_crossed_40_competitive = True
                except TypeError:
                    pass
            
            # Filter out non-plays, nullified, timeouts/end-of-period
            if 'timeout' in play_type_lower or 'end of' in play_type_lower:
                update_prev_wp(play)
                continue
            if is_nullified_play(text_lower):
                update_prev_wp(play)
                continue

            if not competitive:
                update_prev_wp(play)
                continue
            
            # Turnovers
            muffed_punt = 'muffed punt' in text_lower or 'muff' in play_type_lower
            muffed_kick = muffed_punt or ('muffed kick' in text_lower) or ('muffed kickoff' in text_lower) or ('muff' in text_lower and 'kickoff' in text_lower)
            # Broaden interception/fumble detection beyond "Fumble Lost" phrasing.
            interception = 'interception' in play_type_lower or 'intercept' in text_lower
            fumble_phrase = 'fumble' in text_lower
            overturned = 'reversed' in text_lower or 'overturned' in text_lower

            # Track turnover events (multiple possible, e.g., INT then fumble back).
            turnover_events = []

            # Possession tracking for attribution.
            current_possessor = start_team_id
            current_off_abbr = offense_abbrev

            # For muffed punts, possession lies with the receiving team.
            if muffed_kick and opponent_id:
                current_possessor = opponent_id
                current_off_abbr = id_to_abbr.get(opponent_id, '').lower()

            # Interception flips possession once.
            if interception and not overturned:
                turnover_events.append((current_possessor, 'interception'))
                if opponent_id:
                    current_possessor = opponent_id
                    current_off_abbr = id_to_abbr.get(opponent_id, '').lower()

            # Fumble logic with recovery/possession change detection.
            recovered_by_def = False
            recovered_team_id = None
            if fumble_phrase:
                if 'recovered by' in text_lower:
                    if current_off_abbr:
                        recovered_by_def = f"recovered by {current_off_abbr}" not in text_lower
                    elif 'fumble recovery (own)' in play_type_lower:
                        recovered_by_def = False
                    else:
                        recovered_by_def = True
                elif 'fumble recovery (own)' in play_type_lower:
                    recovered_by_def = False
                # Possession change fallback when recovery text is missing/ambiguous.
                if start_team_id and end_team_id and start_team_id != end_team_id:
                    recovered_by_def = current_possessor != end_team_id
                    recovered_team_id = end_team_id
                elif end_team_id:
                    recovered_team_id = end_team_id

            fumble_turnover = fumble_phrase and recovered_by_def and not overturned
            if fumble_turnover and not muffed_kick:
                turnover_events.append((current_possessor, 'fumble'))
                if recovered_team_id:
                    current_possessor = recovered_team_id
                    current_off_abbr = id_to_abbr.get(current_possessor, '').lower()

            # Muffed punts/kickoffs are turnovers on the receiving team.
            if muffed_kick and not overturned:
                turnover_events.append((current_possessor, 'muffed_kick'))
                if end_team_id:
                    current_possessor = end_team_id

            # Onside kick recovered by kicking team -> turnover on receiving team.
            if not overturned and 'onside' in text_lower and 'kick' in text_lower and opponent_id:
                if end_team_id == start_team_id:
                    turnover_events.append((opponent_id, 'onside_recovery'))
                    current_possessor = start_team_id

            # Blocked kicks/punts recovered by defense.
            if not overturned and 'blocked' in text_lower and ('punt' in play_type_lower or 'field goal' in play_type_lower or 'fg' in play_type_lower):
                if start_team_id and end_team_id and start_team_id != end_team_id:
                    turnover_events.append((start_team_id, 'blocked_kick'))
                    current_possessor = end_team_id

            turnover_on_play = bool(turnover_events)
            if turnover_on_play:
                for t_event, reason in turnover_events:
                    if t_event not in stats:
                        continue
                    stats[t_event]['Turnovers'] += 1
                    if expanded:
                        details[t_event]['Turnovers'].append({
                            'type': play_type,
                            'text': text,
                            'yards': play.get('statYardage', 0),
                            'quarter': play.get('period', {}).get('number'),
                            'clock': play.get('clock', {}).get('displayValue'),
                            'start_pos': play.get('start', {}).get('possessionText'),
                            'down_dist': play.get('start', {}).get('downDistanceText') or play.get('start', {}).get('shortDownDistanceText'),
                            'probability': lookup_probability_with_delta(play),
                            'reason': reason
                        })
            
            # Track scoring tied to the offense on the drive via scoringPlays map
            play_id = play.get('id')
            if play.get('scoringPlay') and drive_started_competitive:
                if play_id in scoring_map:
                    sp = scoring_map[play_id]
                    if sp.get('team') == team_id:
                        drive_points_competitive += sp.get('points', 0)
                else:
                    drive_points_competitive += play.get('scoreValue', 0)
            
            # Special teams net values computed from field position when available
            start_pos_text = play.get('start', {}).get('possessionText')
            end_pos_text = play.get('end', {}).get('possessionText', '')
            start_coord = yardline_to_coord(start_pos_text, id_to_abbr.get(team_id, ''))
            end_coord = yardline_to_coord(end_pos_text, id_to_abbr.get(team_id, ''))

            if 'punt' in play_type_lower:
                net_yards = play.get('statYardage', 0)
                end_coord_calc = end_coord
                # If a punt is returned for a TD (often missing end_pos_text), treat end at own goal line -> negative net.
                if end_coord_calc is None and start_coord is not None:
                    scored_against_kicking = False
                    if play.get('scoringPlay'):
                        if play_id in scoring_map and scoring_map[play_id].get('team') and scoring_map[play_id]['team'] != team_id:
                            scored_against_kicking = True
                        elif 'touchdown' in text_lower:
                            scored_against_kicking = True
                    if scored_against_kicking:
                        end_coord_calc = 0
                if start_coord is not None and end_coord_calc is not None:
                    net_yards = end_coord_calc - start_coord
                stats[team_id]['Punt Net Sum'] += net_yards
                stats[team_id]['Punt Plays'] += 1
                if expanded:
                        details[team_id]['Net Punting'].append({
                            'yards': net_yards,
                            'text': text,
                            'quarter': play.get('period', {}).get('number'),
                            'clock': play.get('clock', {}).get('displayValue'),
                            'start_pos': play.get('start', {}).get('possessionText'),
                            'down_dist': play.get('start', {}).get('downDistanceText') or play.get('start', {}).get('shortDownDistanceText'),
                            'probability': lookup_probability_with_delta(play)
                        })
                # ST penalties on punts
                pen = play.get('penalty')
                if pen:
                    yards_pen = pen.get('yards', 0) or 0
                    text_pen = text_lower
                    kicked_by = id_to_abbr.get(team_id, '').lower()
                    against_kicking = kicked_by and f"penalty on {kicked_by}" in text_pen
                    against_receiving = False
                    if kicked_by and "penalty on " in text_pen:
                        against_receiving = not against_kicking
                    delta = -yards_pen if against_kicking else yards_pen if against_receiving else 0
                    stats[team_id]['ST Penalties'] += delta
                    if expanded and delta != 0:
                        details[team_id]['ST Penalties'].append({
                            'yards': delta,
                            'text': text,
                            'quarter': play.get('period', {}).get('number'),
                            'clock': play.get('clock', {}).get('displayValue'),
                            'start_pos': play.get('start', {}).get('possessionText'),
                            'down_dist': play.get('start', {}).get('downDistanceText') or play.get('start', {}).get('shortDownDistanceText'),
                            'probability': lookup_probability_with_delta(play)
                        })
            if 'kickoff' in play_type_lower:
                net_yards = play.get('statYardage', 0)
                if start_coord is not None and end_coord is not None:
                    net_yards = end_coord - start_coord
                stats[team_id]['Kick Net Sum'] += net_yards
                stats[team_id]['Kick Plays'] += 1
                if expanded:
                        details[team_id]['Net Kickoff'].append({
                            'yards': net_yards,
                            'text': text,
                            'quarter': play.get('period', {}).get('number'),
                            'clock': play.get('clock', {}).get('displayValue'),
                            'start_pos': play.get('start', {}).get('possessionText'),
                            'down_dist': play.get('start', {}).get('downDistanceText') or play.get('start', {}).get('shortDownDistanceText'),
                            'probability': lookup_probability_with_delta(play)
                        })
                # ST penalties on kickoffs
                pen = play.get('penalty')
                if pen:
                    yards_pen = pen.get('yards', 0) or 0
                    text_pen = text_lower
                    kicked_by = id_to_abbr.get(team_id, '').lower()
                    against_kicking = kicked_by and f"penalty on {kicked_by}" in text_pen
                    against_receiving = False
                    if kicked_by and "penalty on " in text_pen:
                        against_receiving = not against_kicking
                    delta = -yards_pen if against_kicking else yards_pen if against_receiving else 0
                    stats[team_id]['ST Penalties'] += delta
                    if expanded and delta != 0:
                        details[team_id]['ST Penalties'].append({
                            'yards': delta,
                            'text': text,
                            'quarter': play.get('period', {}).get('number'),
                            'clock': play.get('clock', {}).get('displayValue'),
                            'start_pos': play.get('start', {}).get('possessionText'),
                            'down_dist': play.get('start', {}).get('downDistanceText') or play.get('start', {}).get('shortDownDistanceText'),
                            'probability': lookup_probability_with_delta(play)
                        })

            is_offense, is_run, is_pass = classify_offense_play(play)
            if is_offense and (is_run or is_pass):
                stats[team_id]['Plays'] += 1
                yards = play.get('statYardage', 0)
                
                # For turnovers, statYardage can reflect return yards; zero it out to avoid inflating offense.
                if turnover_on_play:
                    yards = 0
                    # For fumbles, try to recover pre-fumble gain from text.
                    if fumble_turnover and not interception:
                        import re
                        m = re.search(r"for (-?\d+) yards", text_lower)
                        if m:
                            try:
                                yards = int(m.group(1))
                            except ValueError:
                                yards = 0
                down = play.get('start', {}).get('down', 1)
                dist = play.get('start', {}).get('distance', 10)
                
                stats[team_id]['Total Yards'] += yards

                # Success Rate
                if calculate_success(down, dist, yards):
                    stats[team_id]['Successful Plays'] += 1
                    
                # Explosives (10+ run, 20+ pass)
                if (is_run and yards >= 10) or (is_pass and yards >= 20):
                    stats[team_id]['Explosive Plays'] += 1
                    if expanded:
                        details[team_id]['Explosive Plays'].append({
                            'yards': yards,
                            'text': text,
                            'type': 'Run' if is_run else 'Pass',
                            'quarter': play.get('period', {}).get('number'),
                            'clock': play.get('clock', {}).get('displayValue'),
                            'start_pos': play.get('start', {}).get('possessionText'),
                            'down_dist': play.get('start', {}).get('downDistanceText') or play.get('start', {}).get('shortDownDistanceText'),
                            'probability': lookup_probability_with_delta(play)
                        })

            # Always update prev WP at end of every play for accurate delta tracking
            update_prev_wp(play)

        if drive_started_competitive:
            if not drive_crossed_40_competitive and drive_start_yte != -1:
                try:
                    if drive_start_yte <= 40:
                        drive_crossed_40_competitive = True
                    elif (100 - drive_start_yte) + (drive_total_yards or 0) >= 60:
                        drive_crossed_40_competitive = True
                except TypeError:
                    pass
            if drive_crossed_40_competitive:
                stats[team_id]['Drives Inside 40'] += 1
                stats[team_id]['Points Inside 40'] += drive_points_competitive
            stats[team_id]['Drive Points'] += drive_points_competitive

    # --- 3. Format Data for Output ---
    
    # Calculate Turnover Margins
    turnover_margin = {}
    ids = list(stats.keys())
    if len(ids) == 2:
        a, b = ids[0], ids[1]
        turnover_margin[a] = stats[b]['Turnovers'] - stats[a]['Turnovers']
        turnover_margin[b] = stats[a]['Turnovers'] - stats[b]['Turnovers']
    else:
        for t_id in ids:
            turnover_margin[t_id] = 0

    # Calculate Hidden Yards (Field Position Advantage)
    # Formula: (Avg Start YardLine - 25) * Number of Drives
    # This captures the holistic result of ST return yards, ST coverage, and defensive stops.
    fp_hidden_yards = {}
    for t_id, d in stats.items():
        drives_total = max(d['Drives Count'], 1)
        avg_start = d['Start Field Pos Sum'] / drives_total
        fp_hidden_yards[t_id] = (avg_start - 25) * drives_total

    # Calculate Differential for 2-team games (Head-to-Head Advantage)
    fp_diff = {x: 0 for x in ids}
    if len(ids) == 2:
        a, b = ids[0], ids[1]
        diff_val = fp_hidden_yards[a] - fp_hidden_yards[b]
        fp_diff[a] = diff_val
        fp_diff[b] = -diff_val

    # Precompute Net Punting/Kickoff averages for display (Informational only, not summed into Hidden Yards)
    punt_net_avg = {
        t_id: (d['Punt Net Sum'] / max(d['Punt Plays'], 1)) for t_id, d in stats.items()
    }
    kick_net_avg = {
        t_id: (d['Kick Net Sum'] / max(d['Kick Plays'], 1)) for t_id, d in stats.items()
    }

    # Populate Expanded Details for Hidden Yards if requested
    if expanded:
        for t_id in ids:
            if t_id in details:
                combined = []
                combined.extend(details[t_id].get('Net Punting', []))
                combined.extend(details[t_id].get('Net Kickoff', []))
                # Add a summary entry to explain the total calculation
                combined.append({
                    'text': f"Total Field Position Value: {round(fp_hidden_yards[t_id], 1)} yds (vs Baseline Own 25)",
                    'yards': round(fp_hidden_yards[t_id], 1),
                    'quarter': '-', 'clock': '-'
                })
                details[t_id]['Hidden Yards'] = combined

    final_rows = []
    for t_id, d in stats.items():
        plays = max(d['Plays'], 1)
        drives_in_40 = max(d['Drives Inside 40'], 1)
        drives_total = max(d['Drives Count'], 1)
        
        row = {
            'Team': d['Team'],
            'Score': d['Score'],
            'Turnovers': d['Turnovers'],
            'Total Yards': d['Total Yards'],
            'Yards Per Play': round(d['Total Yards'] / plays, 2),
            'Success Rate': round((d['Successful Plays'] / plays), 3),
            'Explosive Plays': d['Explosive Plays'],
            'Explosive Play Rate': round(d['Explosive Plays'] / plays, 3),
            'Points Per Trip (Inside 40)': round(d['Points Inside 40'] / drives_in_40, 2),
            'Ave Start Field Pos': f"Own {int(d['Start Field Pos Sum'] / drives_total)}",
            'Drives': d['Drives Count'],
            # Preserve computed values not shown in the table for now
            'Turnover Margin': turnover_margin.get(t_id, 0),
            'Points per Drive': round(d['Drive Points'] / drives_total, 2),
            'Hidden Yards (Total)': round(fp_hidden_yards[t_id], 1),
            'Hidden Yards (Diff)': round(fp_diff[t_id], 1),
            'Net Punting': round(punt_net_avg[t_id], 1),
            'Net Kickoff': round(kick_net_avg[t_id], 1),
            'ST Penalties': round(stats[t_id]['ST Penalties'], 1),
            'Penalty Yards': d.get('Penalty Yards', 0),
            'Non-Offensive Points': d.get('Non-Offensive Points', 0)
        }
        final_rows.append(row)

    df = pd.DataFrame(final_rows)
    if expanded:
        return df, details
    return df

def build_analysis_text(payload):
    """Create a short plain-text summary for the HTML template."""
    team_meta = payload.get("team_meta", [])
    summary_map = {row.get("Team"): row for row in payload.get("summary_table", [])}
    advanced_map = {row.get("Team"): row for row in payload.get("advanced_table", [])}

    away = next((t for t in team_meta if t.get("homeAway") == "away"), {})
    home = next((t for t in team_meta if t.get("homeAway") == "home"), {})

    away_abbr = away.get("abbr", "Away")
    home_abbr = home.get("abbr", "Home")

    away_summary = summary_map.get(away_abbr, {})
    home_summary = summary_map.get(home_abbr, {})
    away_score = away_summary.get("Score")
    home_score = home_summary.get("Score")

    parts = []
    if isinstance(away_score, (int, float)) and isinstance(home_score, (int, float)):
        if away_score > home_score:
            parts.append(f"{away_abbr} lead {home_abbr} {away_score}-{home_score}.")
        elif home_score > away_score:
            parts.append(f"{home_abbr} lead {away_abbr} {home_score}-{away_score}.")
        else:
            parts.append(f"All square at {away_score}-{home_score}.")
    else:
        parts.append(f"{away_abbr} vs {home_abbr}.")

    away_adv = advanced_map.get(away_abbr, {})
    home_adv = advanced_map.get(home_abbr, {})

    def add_stat_line(label, key, suffix=""):
        a_val = away_adv.get(key)
        h_val = home_adv.get(key)
        if a_val is None or h_val is None:
            return
        if isinstance(a_val, float):
            a_display = round(a_val, 2)
        else:
            a_display = a_val
        if isinstance(h_val, float):
            h_display = round(h_val, 2)
        else:
            h_display = h_val
        parts.append(f"{label}: {away_abbr} {a_display}{suffix} vs {home_abbr} {h_display}{suffix}.")

    add_stat_line("Explosive plays", "Explosive Plays")
    add_stat_line("Yards per play", "Yards Per Play")

    return " ".join(parts)

def main():
    parser = argparse.ArgumentParser(description="NFL game advanced stats")
    parser.add_argument("game_id", help="ESPN gameId to fetch (from game URL)")
    parser.add_argument("--expanded", action="store_true", help="Show detailed play lists for select categories")
    parser.add_argument(
        "--wp-threshold",
        type=float,
        default=0.975,
        help="WP threshold for competitive plays (default: 0.975). Plays where either team's WP >= this value are excluded from stats.",
    )
    args = parser.parse_args()

    try:
        print(f"Fetching data for Game ID: {args.game_id}...")
        raw_data = get_game_data(args.game_id)
        pregame_home_wp, pregame_away_wp = get_pregame_probabilities(args.game_id)
        prob_map = {}
        try:
            prob_map = get_play_probabilities(args.game_id)
        except Exception:
            prob_map = {}
        # Last play timestamp/lag (core feed) shown at the top
        last_core_play = None
        drives_prev = raw_data.get('drives', {}).get('previous', [])
        if drives_prev:
            plays = drives_prev[-1].get('plays', [])
            if plays:
                last_core_play = plays[-1]
        last_play_line = None
        if last_core_play:
            from datetime import datetime, timezone
            modified_raw = last_core_play.get('modified')
            lag_str = ""
            if modified_raw:
                try:
                    ts = datetime.fromisoformat(modified_raw.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    diff_sec = int((now - ts).total_seconds())
                    minutes = diff_sec // 60
                    seconds = diff_sec % 60
                    lag_str = f" ({minutes}m {seconds}s ago)"
                except Exception:
                    lag_str = ""
            last_play_line = f"Last play recorded (core feed) at {modified_raw}{lag_str}"

        # Always compute expanded data to support downloadable summary file
        df_filtered, details_filtered = process_game_stats(
            raw_data,
            expanded=True,
            probability_map=prob_map,
            pregame_probabilities=(pregame_home_wp, pregame_away_wp),
            wp_threshold=args.wp_threshold
        )
        df_full, details_full = process_game_stats(
            raw_data,
            expanded=True,
            probability_map=prob_map,
            pregame_probabilities=(pregame_home_wp, pregame_away_wp),
            wp_threshold=1.0
        )
        df = df_filtered
        details = details_filtered

        # Prepare downloadable files (CSV for tables, JSON for expanded detail)
        comps = raw_data.get('header', {}).get('competitions', [])
        game_date_str = None
        game_id = args.game_id
        home_abbr = away_abbr = None
        team_meta = []
        if comps:
            comp0 = comps[0]
            game_date_str = comp0.get('date', '')
            for comp in comp0.get('competitors', []):
                abbr = comp.get('team', {}).get('abbreviation')
                display_name = comp.get('team', {}).get('displayName', abbr or "")
                if comp.get('homeAway') == 'home':
                    home_abbr = abbr
                elif comp.get('homeAway') == 'away':
                    away_abbr = abbr
                team_meta.append({
                    "id": comp.get('id'),
                    "abbr": abbr,
                    "name": display_name,
                    "homeAway": comp.get('homeAway')
                })
        # Build filename base
        date_part = ""
        if game_date_str:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(game_date_str.replace('Z', '+00:00'))
                date_part = dt.strftime("%Y%m%d")
            except Exception:
                date_part = ""
        teams_part = ""
        if home_abbr and away_abbr:
            teams_part = f"{away_abbr}_at_{home_abbr}"
        fname_parts = [p for p in [teams_part, date_part, game_id] if p]
        fname_base = "_".join(fname_parts) if fname_parts else f"game_{game_id}"

        output_dir = os.path.join(os.getcwd(), "game_summaries")
        os.makedirs(output_dir, exist_ok=True)

        template_path = os.path.join(os.path.dirname(__file__), "templates", "game_summary_template.html")
        csv_path = os.path.join(output_dir, f"{fname_base}_advanced.csv")
        json_path = os.path.join(output_dir, f"{fname_base}_expanded.json")
        html_path = os.path.join(output_dir, f"{fname_base}.html")

        df[ADVANCED_COLS].to_csv(csv_path, index=False)

        # Build JSON payload with summary, advanced, and expanded details
        def slice_details(source):
            return {
                t_id: {cat: source.get(t_id, {}).get(cat, []) for cat in EXPANDED_CATEGORIES}
                for t_id in source
            }

        filtered_details = slice_details(details_filtered)
        filtered_details_full = slice_details(details_full)

        payload = {
            "gameId": game_id,
            "label": fname_base,
            "wp_filter": {
                "enabled": True,
                "threshold": args.wp_threshold,
                "description": f"Stats reflect competitive plays only (WP < {args.wp_threshold * 100:.1f}%)",
            },
            "summary_table": df_filtered[SUMMARY_COLS].to_dict(orient="records"),
            "advanced_table": df_filtered[ADVANCED_COLS].to_dict(orient="records"),
            "summary_table_full": df_full[SUMMARY_COLS].to_dict(orient="records"),
            "advanced_table_full": df_full[ADVANCED_COLS].to_dict(orient="records"),
            "expanded_details": filtered_details,
            "expanded_details_full": filtered_details_full,
            "team_meta": team_meta,
            "last_play": last_play_line
        }
        # Build AI summary context
        summary_map = {row.get('Team'): row for row in payload.get('summary_table', [])}
        home_meta = next((t for t in team_meta if t.get('homeAway') == 'home'), {})
        away_meta = next((t for t in team_meta if t.get('homeAway') == 'away'), {})
        home_score_val = summary_map.get(home_meta.get('abbr'), {}).get('Score', 0)
        away_score_val = summary_map.get(away_meta.get('abbr'), {}).get('Score', 0)
        winner_is_home = home_score_val > away_score_val

        wp_trajectory_stats = calculate_wp_trajectory_stats(raw_data, prob_map, winner_is_home)
        competitive_csv = build_competitive_plays_csv(raw_data, prob_map, args.wp_threshold)
        ai_summary = generate_game_summary(payload, competitive_csv, wp_trajectory_stats, args.wp_threshold)
        payload["ai_summary"] = ai_summary
        payload["analysis"] = build_analysis_text(payload)

        if last_play_line:
            print(f"\n{last_play_line}")
        if args.expanded and ai_summary:
            print("\n--- AI SUMMARY (LLM) ---")
            print(ai_summary)

        # Build Summary and Advanced tables (teams as columns)
        df_summary_display = df[SUMMARY_COLS].set_index('Team').T
        df_advanced_display = df[ADVANCED_COLS].set_index('Team').T

        print("\n--- SUMMARY STATS ---")
        print(df_summary_display)

        print("\n--- ADVANCED STATS ---")
        print(df_advanced_display)
        try:
            with open(json_path, "w") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            print(f"Warning: could not write JSON summary: {e}")

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_html = f.read()
            rendered_html = template_html.replace("__GAME_DATA_JSON__", json.dumps(payload, indent=2))
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(rendered_html)
        except FileNotFoundError:
            print(f"Warning: HTML template not found at {template_path}")
        except Exception as e:
            print(f"Warning: could not write HTML summary: {e}")

        if args.expanded and details:
            print("\n--- EXPANDED PLAYS ---")
            categories = EXPANDED_CATEGORIES
            team_id_to_abbr = {}
            for t in raw_data.get('boxscore', {}).get('teams', []):
                tid = t.get('team', {}).get('id')
                abbr = t.get('team', {}).get('abbreviation')
                if tid and abbr:
                    team_id_to_abbr[tid] = abbr

            def format_wp(prob):
                if not prob or not isinstance(prob, dict):
                    return ""
                def pct(val):
                    if isinstance(val, (int, float)):
                        return round(val * 100, 1)
                    return None
                def delta_str(val):
                    if isinstance(val, (int, float)):
                        d = round(val * 100, 1)
                        if d == 0:
                            return "0.0"
                        return f"+{d}" if d > 0 else str(d)
                    return None
                home_pct = pct(prob.get('homeWinPercentage'))
                away_pct = pct(prob.get('awayWinPercentage'))
                home_delta = delta_str(prob.get('homeDelta'))
                away_delta = delta_str(prob.get('awayDelta'))
                parts = []
                if away_pct is not None and away_abbr:
                    delta_part = f" ({away_delta})" if away_delta else ""
                    parts.append(f"{away_abbr} {away_pct}%{delta_part}")
                if home_pct is not None and home_abbr:
                    delta_part = f" ({home_delta})" if home_delta else ""
                    parts.append(f"{home_abbr} {home_pct}%{delta_part}")
                if not parts:
                    return ""
                return "WP " + " / ".join(parts)

            for t_id, team_detail in details.items():
                team_label = team_id_to_abbr.get(t_id, t_id)
                print(f"\nTeam: {team_label}")
                for cat in categories:
                    plays = team_detail.get(cat, [])
                    print(f"  {cat}:")
                    if not plays:
                        print("    (none)")
                        continue
                    for p in plays:
                        desc_parts = []
                        if 'yards' in p and p['yards'] is not None:
                            desc_parts.append(f"{p['yards']} yds")
                        if 'type' in p and p['type']:
                            desc_parts.append(p['type'])
                        desc = " - ".join(desc_parts) if desc_parts else ""
                        prefix_parts = []
                        if p.get('quarter'):
                            prefix_parts.append(f"Q{p['quarter']}")
                        if p.get('clock'):
                            prefix_parts.append(p['clock'])
                        if p.get('down_dist'):
                            prefix_parts.append(p['down_dist'])
                        elif p.get('start_pos'):
                            prefix_parts.append(p['start_pos'])
                        prefix = " | ".join(prefix_parts)
                        suffix_parts = []
                        wp_text = format_wp(p.get('probability'))
                        if wp_text:
                            suffix_parts.append(wp_text)
                        suffix = " ".join(suffix_parts)
                        if prefix:
                            print(f"    {prefix} | {desc} {p.get('text','')} {suffix}".rstrip())
                        else:
                            print(f"    {desc} {p.get('text','')} {suffix}".rstrip())
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
