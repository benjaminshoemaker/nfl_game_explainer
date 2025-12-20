import argparse
import os
import sys
import requests
import pandas as pd
import json
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback for environments without python-dotenv
    def load_dotenv(*args, **kwargs):
        return False
from openai import OpenAI

# Add api/ to path for shared core imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))
from lib.nfl_core import (
    yardline_to_coord,
    calculate_success,
    any_stat_contains,
    is_penalty_play,
    is_spike_or_kneel,
    is_special_teams_play,
    is_nullified_play,
    classify_offense_play,
    is_competitive_play,
    process_game_stats as _process_game_stats,
    build_analysis_text,
)

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
    prev_away_wp = 0.5
    drives = game_data.get('drives', {}).get('previous', [])

    for drive in drives:
        drive_team = id_to_abbr.get(drive.get('team', {}).get('id'), '?')

        for play in drive.get('plays', []):
            play_id = str(play.get('id', ''))
            period = play.get('period', {}).get('number', 0)

            prob = probability_map.get(play_id)
            if not prob:
                continue

            start_home_wp = prev_home_wp
            start_away_wp = prev_away_wp

            home_wp = prob.get('homeWinPercentage', 0.5)
            away_wp = prob.get('awayWinPercentage', 0.5)

            # Skip non-competitive plays (unless OT)
            if period < 5 and (start_home_wp >= wp_threshold or start_away_wp >= wp_threshold):
                prev_home_wp = home_wp
                prev_away_wp = away_wp
                continue

            delta = abs(home_wp - prev_home_wp) * 100

            if delta >= 5:  # Only include plays with meaningful impact
                plays_with_delta.append({
                    'delta': round(delta, 1),
                    'quarter': period,
                    'clock': play.get('clock', {}).get('displayValue', ''),
                    'team': drive_team,
                    'text': play.get('text', '') or ''
                })

            prev_home_wp = home_wp
            prev_away_wp = away_wp

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
                play_text = play.get('text', '') or ''
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


def process_game_stats(game_data, expanded=False, probability_map=None, pregame_probabilities=None, wp_threshold=0.975):
    """Wrapper that calls shared core and returns pandas DataFrame."""
    rows, details = _process_game_stats(
        game_data,
        expanded=expanded,
        probability_map=probability_map,
        pregame_probabilities=pregame_probabilities,
        wp_threshold=wp_threshold
    )
    df = pd.DataFrame(rows)
    if expanded:
        return df, details
    return df



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
