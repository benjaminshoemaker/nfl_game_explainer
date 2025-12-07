import argparse
import os
import requests
import pandas as pd
import json
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback for environments without python-dotenv
    def load_dotenv(*args, **kwargs):
        return False
from openai import OpenAI

load_dotenv('.env.local')

GAME_SUMMARY_SYSTEM_PROMPT = """You generate 280-character NFL game summaries that explain the score.

## FACTOR PRIORITY

**Tier 1 - Lead with these:**
- Turnovers (~4 points per turnover; 70% win rate when winning the battle)
- Non-offensive points (pick-sixes, fumble returns, ST TDs)
- Explosive plays (drives with explosives see expected points nearly quadruple)

**Tier 2 - Strong support:**
- Success rate, Points per trip inside 40

**Tier 3 - Context only:**
- Field position, Penalty yards (weakest correlation—rarely lead with this)

## WP DELTA THRESHOLDS

- ≥20%: Game-changing. Must mention, likely lead with it.
- 15-19%: Major impact. Mention if no 20%+ plays.
- 10-14%: Key play. Mention if space permits.
- <10%: Don't mention individually.

## NARRATIVE SELECTION

**Single play**: Lead with a specific play if WP delta ≥20% in 4th quarter/OT.
**Despite narrative**: Use when winner/leader lost 2+ stat categories. Explain what overcame the deficit.
**Comeback**: Use when winner/leader dropped below 25% WP at some point.
**Dominant factor**: Use when no play ≥15% delta but one stat shows clear edge (+3 turnovers, etc).

## STYLE

- First sentence must include the score
- Completed games: past tense ("cruised", "edged", "survived")
- In-progress games: present tense ("leads", "controlling", "hanging on")
- Match verb to margin: "cruised" (17+), "beats" (10-16), "edges" (3-9), "survives" (1-2)
- Include player names for key plays
- Use correlation language ("won with +3 turnover margin") not causation ("won because of")

## DO NOT

- Lead with penalty yards unless a specific penalty decided the game
- Say "great game" or "big win"—every word must add information
- Treat yards as deterministic (teams win despite being outgained 30% of the time)
- Miss clusters (three 8% plays on one drive = 24% cumulative)

## OUTPUT

Shoot for ~280 characters. Brevity is key—if you can say it in fewer words, do. No hashtags or emojis."""
SUMMARY_COLS = ['Team', 'Score', 'Total Yards', 'Drives']
ADVANCED_COLS = [
    'Team', 'Score', 'Turnovers', 'Total Yards', 'Yards Per Play',
    'Success Rate', 'Explosive Plays', 'Explosive Play Rate',
    'Points Per Trip (Inside 40)', 'Ave Start Field Pos',
    'Penalty Yards', 'Non-Offensive Points'
]
EXPANDED_CATEGORIES = [
    'Turnovers',
    'Explosive Plays',
    'Non-Offensive Scores',
    'Points Per Trip (Inside 40)',
    'Penalty Yards',
    'Non-Offensive Points'
]


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


def build_top_plays_by_wp(game_data, probability_map, wp_threshold=0.975, limit=10):
    """
    Build a simple list of top plays by WP delta for the LLM.
    Only includes competitive plays with ≥5% WP swing, sorted by impact.
    """
    plays_with_delta = []

    teams_info = game_data.get('boxscore', {}).get('teams', [])
    id_to_abbr = {}
    for t in teams_info:
        tid = t.get('team', {}).get('id')
        abbr = t.get('team', {}).get('abbreviation', '?')
        if tid:
            id_to_abbr[tid] = abbr

    prev_home_wp = 0.5
    drives = game_data.get('drives', {}).get('previous', [])

    for drive in drives:
        drive_team = id_to_abbr.get(drive.get('team', {}).get('id'), '?')

        for play in drive.get('plays', []):
            play_id = str(play.get('id', ''))
            period = play.get('period', {}).get('number', 0)

            prob = probability_map.get(play_id)
            if not prob:
                continue

            home_wp = prob.get('homeWinPercentage', 0.5)
            away_wp = prob.get('awayWinPercentage', 0.5)

            # Skip non-competitive plays (unless OT)
            if period < 5 and (home_wp >= wp_threshold or away_wp >= wp_threshold):
                prev_home_wp = home_wp
                continue

            delta = abs(home_wp - prev_home_wp) * 100

            if delta >= 5:  # Only include plays with meaningful impact
                plays_with_delta.append({
                    'delta': round(delta, 1),
                    'quarter': period,
                    'clock': play.get('clock', {}).get('displayValue', ''),
                    'team': drive_team,
                    'text': (play.get('text', '') or '')[:100]
                })

            prev_home_wp = home_wp

    # Sort by delta descending, take top N
    plays_with_delta.sort(key=lambda x: x['delta'], reverse=True)
    top_plays = plays_with_delta[:limit]

    # Format as simple text lines
    lines = []
    for p in top_plays:
        lines.append(f"{p['delta']}% | Q{p['quarter']} {p['clock']} | {p['team']} | {p['text']}")

    return "\n".join(lines) if lines else "No high-impact plays (5%+ WP delta)"


def calculate_wp_trajectory_stats(game_data, probability_map, leader_is_home):
    """
    Calculate WP trajectory statistics.
    Uses 'leader' instead of 'winner' to work for in-progress games.
    """
    leader_min_wp = 100.0
    wp_crossings = 0
    max_wp_delta = 0.0
    max_wp_play_desc = ""

    prev_home_wp = 0.5
    prev_above_50 = None

    drives = game_data.get('drives', {}).get('previous', [])

    for drive in drives:
        for play in drive.get('plays', []):
            play_id = str(play.get('id', ''))
            prob = probability_map.get(play_id)

            if not prob:
                continue

            home_wp = prob.get('homeWinPercentage', 0.5)
            away_wp = prob.get('awayWinPercentage', 0.5)

            # Track leader's minimum WP
            leader_wp = home_wp if leader_is_home else away_wp
            if leader_wp < leader_min_wp:
                leader_min_wp = leader_wp

            # Track 50% line crossings
            currently_above_50 = home_wp > 0.5
            if prev_above_50 is not None and currently_above_50 != prev_above_50:
                wp_crossings += 1
            prev_above_50 = currently_above_50

            # Track max WP delta
            delta = abs(home_wp - prev_home_wp) * 100
            if delta > max_wp_delta:
                max_wp_delta = delta
                play_text = (play.get('text', '') or '')[:60]
                quarter = play.get('period', {}).get('number', '?')
                clock = play.get('clock', {}).get('displayValue', '?')
                max_wp_play_desc = f"Q{quarter} {clock} - {play_text}"

            prev_home_wp = home_wp

    return {
        'leader_min_wp': round(leader_min_wp * 100, 1),
        'wp_crossings': wp_crossings,
        'max_wp_delta': round(max_wp_delta, 1),
        'max_wp_play_desc': max_wp_play_desc
    }


def generate_game_summary(payload, game_data, probability_map, wp_threshold=0.975):
    """
    Generate a concise game summary using OpenAI.
    Handles both completed and in-progress games.
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

        # Determine game status
        game_status = "Final"
        is_final = True
        header = game_data.get('header', {})
        competitions = header.get('competitions', [])
        if competitions:
            status_obj = competitions[0].get('status', {})
            status_type = status_obj.get('type', {})
            is_final = status_type.get('completed', False)

            if not is_final:
                period = status_obj.get('period', 0)
                clock = status_obj.get('displayClock', '')
                if period <= 4:
                    game_status = f"Q{period} {clock}" if clock else f"Q{period}"
                else:
                    game_status = f"OT {clock}" if clock else "OT"
            else:
                game_status = "Final"

        # Determine leader
        if home_score > away_score:
            leader_abbr = home_abbr
            margin = home_score - away_score
            leader_line = f"{home_abbr} {'won' if is_final else 'leads'} by {margin}"
        elif away_score > home_score:
            leader_abbr = away_abbr
            margin = away_score - home_score
            leader_line = f"{away_abbr} {'won' if is_final else 'leads'} by {margin}"
        else:
            leader_abbr = home_abbr  # Default for WP calc
            leader_line = "Tied game"

        # Get advanced stats
        advanced_map = {row.get('Team'): row for row in payload.get('advanced_table', [])}
        away_stats = advanced_map.get(away_abbr, {})
        home_stats = advanced_map.get(home_abbr, {})

        # Calculate WP trajectory stats
        leader_is_home = home_score >= away_score
        wp_stats = calculate_wp_trajectory_stats(game_data, probability_map, leader_is_home)

        # Build top plays list
        top_plays = build_top_plays_by_wp(game_data, probability_map, wp_threshold, limit=10)

        # Summary focus based on game state
        if is_final:
            if home_score != away_score:
                summary_focus = f"why {leader_abbr} won"
            else:
                summary_focus = "how the game ended in a tie"
        else:
            if home_score != away_score:
                summary_focus = f"why {leader_abbr} leads"
            else:
                summary_focus = "why the game is tied"

        # Build compact user prompt
        user_prompt = f"""Generate a game summary:

{away_name} ({away_abbr}) {away_score} @ {home_name} ({home_abbr}) {home_score}
Status: {game_status}
{leader_line}

## STATS (competitive plays only):

{away_abbr}: TO {away_stats.get('Turnovers', 'N/A')} | SR {away_stats.get('Success Rate', 'N/A')} | Exp {away_stats.get('Explosive Plays', 'N/A')} | PPT {away_stats.get('Points Per Trip (Inside 40)', 'N/A')} | Non-Off {away_stats.get('Non-Offensive Points', 'N/A')}
{home_abbr}: TO {home_stats.get('Turnovers', 'N/A')} | SR {home_stats.get('Success Rate', 'N/A')} | Exp {home_stats.get('Explosive Plays', 'N/A')} | PPT {home_stats.get('Points Per Trip (Inside 40)', 'N/A')} | Non-Off {home_stats.get('Non-Offensive Points', 'N/A')}

## KEY WP MOMENTS:

- Largest swing: {wp_stats.get('max_wp_delta', 'N/A')}% ({wp_stats.get('max_wp_play_desc', 'N/A')})
- {leader_abbr}'s lowest WP: {wp_stats.get('leader_min_wp', 'N/A')}%
- Lead changes: {wp_stats.get('wp_crossings', 'N/A')}

## TOP PLAYS BY WP IMPACT:
{top_plays}

Write a concise summary (~280 chars) explaining {summary_focus}."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Update to gpt-5-mini when available
            messages=[
                {"role": "system", "content": GAME_SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )

        summary = response.choices[0].message.content.strip()

        # Clean up response
        if summary.startswith('"') and summary.endswith('"'):
            summary = summary[1:-1]
        # No hard truncation - we trust the model to be concise

        return summary

    except Exception as e:
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

    # Kickoff/punt return TDs are special teams plays, not offensive plays
    # (is_special_teams_play excludes TDs to not block offensive TDs)
    if ('kickoff' in text_lower or 'kickoff' in type_lower) and 'return' in type_lower:
        return False, False, False
    if ('punt' in text_lower or 'punt' in type_lower) and 'return' in type_lower:
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
    abbr_to_id = {abbr.lower(): tid for tid, abbr in id_to_abbr.items()}
    scoring_map = {}
    non_offensive_play_map = {}
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
                'points': points,
                'is_non_offensive': False
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
                'Non-Offensive Scores': [],
                'Points Per Trip (Inside 40)': [],
                'Penalty Yards': [],
                'Non-Offensive Points': []
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

        # Detect kickoff/punt return TDs - these are special teams scores
        has_touchdown = 'touchdown' in play_text or 'touchdown' in play_type or 'touchdown' in scoring_type
        is_kick_return_td = ('kickoff' in play_text or 'kickoff' in play_type) and has_touchdown
        is_punt_return_td = ('punt' in play_text or 'punt' in play_type) and has_touchdown and ('return' in play_text or 'return' in play_type)

        if is_safety:
            is_non_offensive = True
            points = 2  # Safeties are always 2 points
        elif is_kick_return_td or is_punt_return_td:
            is_non_offensive = True
        elif drive_offense_id and scoring_team_id and drive_offense_id != scoring_team_id:
            is_non_offensive = True

        if is_non_offensive and scoring_team_id in stats:
            stats[scoring_team_id]['Non-Offensive Points'] += points
            if play_id in scoring_map:
                scoring_map[play_id]['is_non_offensive'] = True
            non_offensive_play_map[str(play_id)] = {
                'team_id': scoring_team_id,
                'points': points,
                'type': sp.get('type', {}).get('text', ''),
                'text': sp.get('text', ''),
                'quarter': sp.get('period', {}).get('number'),
                'clock': sp.get('clock', {}).get('displayValue'),
            }
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
        drive_has_offensive_play = False  # Track if drive had any offensive plays
        last_competitive_play = None
        last_competitive_prob = None
        current_yte_est = drive_start_yte if isinstance(drive_start_yte, (int, float)) else None

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
            probability_snapshot = lookup_probability_with_delta(play)

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

            # Capture penalty plays for key-play surfacing
            penalty_info = play.get('penalty') or {}
            has_penalty_flag = bool(penalty_info) or play.get('hasPenalty') or 'penalty' in text_lower
            if expanded and has_penalty_flag:
                commit_team_id = penalty_info.get('team', {}).get('id')
                if not commit_team_id:
                    for abbr_lower, tid in abbr_to_id.items():
                        if f"penalty on {abbr_lower}" in text_lower:
                            commit_team_id = tid
                            break
                if not commit_team_id:
                    if 'on defense' in text_lower and opponent_id:
                        commit_team_id = opponent_id
                    else:
                        commit_team_id = team_id
                yards_pen = penalty_info.get('yards')
                if isinstance(yards_pen, (int, float)):
                    yards_pen = -abs(yards_pen)
                if commit_team_id not in details:
                    commit_team_id = team_id
                details[commit_team_id]['Penalty Yards'].append({
                    'yards': yards_pen,
                    'text': play.get('text', ''),
                    'type': play_type,
                    'quarter': play.get('period', {}).get('number'),
                    'clock': play.get('clock', {}).get('displayValue'),
                    'start_pos': play.get('start', {}).get('possessionText'),
                    'down_dist': play.get('start', {}).get('downDistanceText') or play.get('start', {}).get('shortDownDistanceText'),
                    'probability': probability_snapshot
                })

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
            last_competitive_play = play
            last_competitive_prob = probability_snapshot

            if competitive and drive_started_competitive:
                is_offense_play, _, _ = classify_offense_play(play)
                if is_offense_play:
                    drive_has_offensive_play = True
                if is_offense_play and not drive_crossed_40_competitive:
                    yte_start = play.get('start', {}).get('yardsToEndzone')
                    gained = play.get('statYardage')
                    if isinstance(yte_start, (int, float)):
                        current_yte_est = yte_start
                    yte_for_check = yte_start if isinstance(yte_start, (int, float)) else current_yte_est
                    try:
                        if yte_for_check is not None and yte_for_check <= 40:
                            drive_crossed_40_competitive = True
                        elif isinstance(yte_for_check, (int, float)) and isinstance(gained, (int, float)):
                            if yte_for_check - gained <= 40:
                                drive_crossed_40_competitive = True
                            current_yte_est = yte_for_check - gained
                    except TypeError:
                        pass
            
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

            non_off_entry = non_offensive_play_map.get(str(play_id))
            if expanded and non_off_entry:
                target_team = non_off_entry.get('team_id')
                if target_team in details:
                    details[target_team]['Non-Offensive Points'].append({
                        'type': non_off_entry.get('type') or play_type,
                        'text': non_off_entry.get('text') or text,
                        'points': non_off_entry.get('points'),
                        'quarter': play.get('period', {}).get('number'),
                        'clock': play.get('clock', {}).get('displayValue'),
                        'start_pos': play.get('start', {}).get('possessionText'),
                        'down_dist': play.get('start', {}).get('downDistanceText') or play.get('start', {}).get('shortDownDistanceText'),
                        'probability': probability_snapshot
                    })
            
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
            # Consider drives that started already inside the 40 (but only if they had offensive plays)
            if drive_has_offensive_play and drive_start_yte != -1 and drive_start_yte <= 40:
                drive_crossed_40_competitive = True
            # Only count drives with offensive plays for "inside 40" stats
            if drive_crossed_40_competitive and drive_has_offensive_play:
                stats[team_id]['Drives Inside 40'] += 1
                stats[team_id]['Points Inside 40'] += drive_points_competitive
            stats[team_id]['Drive Points'] += drive_points_competitive
            if expanded and drive_crossed_40_competitive and drive_has_offensive_play and last_competitive_play:
                details[team_id]['Points Per Trip (Inside 40)'].append({
                    'text': last_competitive_play.get('text', ''),
                    'type': last_competitive_play.get('type', {}).get('text', ''),
                    'yards': last_competitive_play.get('statYardage'),
                    'quarter': last_competitive_play.get('period', {}).get('number'),
                    'clock': last_competitive_play.get('clock', {}).get('displayValue'),
                    'start_pos': last_competitive_play.get('start', {}).get('possessionText'),
                    'down_dist': last_competitive_play.get('start', {}).get('downDistanceText') or last_competitive_play.get('start', {}).get('shortDownDistanceText'),
                    'points': drive_points_competitive,
                    'probability': last_competitive_prob
                })

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
        game_status_label = "Final"
        game_is_final = True
        if comps:
            comp0 = comps[0]
            game_date_str = comp0.get('date', '')
            status_obj = comp0.get('status', {})
            status_type = status_obj.get('type', {})
            game_is_final = status_type.get('completed', False)
            if not game_is_final:
                period = status_obj.get('period', 0)
                clock = status_obj.get('displayClock', '')
                if period <= 4:
                    game_status_label = f"Q{period} {clock}".strip()
                else:
                    game_status_label = f"OT {clock}".strip() if clock else "OT"
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
            "last_play": last_play_line,
            "game_status": game_status_label,
            "is_final": game_is_final
        }
        ai_summary = generate_game_summary(payload, raw_data, prob_map, args.wp_threshold)
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
