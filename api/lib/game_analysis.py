"""
Game analysis module for serverless API use.
Imports core analytics from nfl_core and provides HTTP fetching + API entry point.
"""

import json
import urllib.request
import urllib.error
import gzip
import logging
from urllib.parse import urlparse
from .play_feed import build_play_feed
from .epa import calculate_play_epa

# Import shared core analytics functions
from .nfl_core import (
    yardline_to_coord,
    calculate_success,
    any_stat_contains,
    is_penalty_play,
    is_spike_or_kneel,
    is_special_teams_play,
    is_nullified_play,
    classify_offense_play,
    is_competitive_play,
    process_game_stats,
    reconcile_final_boxscore,
    build_analysis_text,
    boxscore_abbreviations_by_id,
)

ESPN_REQUEST_HEADERS = {
    # ESPN currently rejects browser User-Agents from server-to-server clients.
    # Let urllib supply its default User-Agent instead.
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.espn.com/',
    'Origin': 'https://www.espn.com',
}

def _decompress_response(data):
    """Decompress gzip data if needed, return raw data otherwise."""
    if data[:2] == b'\x1f\x8b':  # gzip magic bytes
        return gzip.decompress(data)
    return data


def _derive_game_status(status_obj):
    """
    Derive API status and optional gameClock from ESPN competition status object.

    ESPN uses `status.type.state`:
      - "pre"  => pregame
      - "in"   => in-progress
      - "post" => final

    Some pregame payloads have period=0; treat that as pregame (not "Q0").
    """
    status_obj = status_obj or {}
    status_type = status_obj.get('type', {}) or {}

    state = status_type.get('state')
    marker = f"{status_type.get('name', '')} {status_type.get('shortDetail', '')}".lower()
    completed = bool(status_type.get('completed', False))
    period = status_obj.get('period', 0) or 0
    clock = status_obj.get('displayClock', '') or ''

    if 'cancel' in marker or 'abandon' in marker:
        return "canceled", None
    if 'postpon' in marker or 'reschedul' in marker:
        return "postponed", None
    if 'delay' in marker or 'suspend' in marker or 'interrupt' in marker:
        return "delayed", None
    if state == 'post' or completed:
        return "final", None

    # Use explicit state when present, otherwise fall back to period>0.
    if state == 'in' or (state is None and period > 0):
        if period > 0:
            if period <= 4:
                label = f"Q{period} {clock}".strip()
            else:
                label = f"OT {clock}".strip() if clock else "OT"
            return "in-progress", {"quarter": period, "clock": clock, "displayValue": label}
        return "in-progress", None

    return "pregame", None


SUMMARY_COLS = ['Team', 'Score', 'Total Yards', 'Drives']
ADVANCED_COLS = [
    'Team', 'Score', 'Turnovers', 'Total Yards',
    'Official Yards Per Play (Full Game)', 'Adjusted Yards Per Play',
    'Success Rate', 'Explosive Plays', 'Explosive Play Rate',
    'Points Per Trip (Inside 40)', 'Ave Start Field Pos',
    'Penalty Yards', 'Non-Offensive Points'
]
EXPANDED_CATEGORIES = [
    'All Plays',
    'Offensive Plays',
    'Turnovers',
    'Explosive Plays',
    'Non-Offensive Scores',
    'Points Per Trip (Inside 40)',
    'Drive Starts',
    'Penalty Yards',
    'Non-Offensive Points'
]


def get_game_data(game_id):
    """Pull the full game data from ESPN summary API."""
    # Use site.api.espn.com first, then fall back to cdn play-by-play if ESPN blocks the request (401/403).
    summary_url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"
    fallback_url = f"https://cdn.espn.com/core/nfl/playbyplay?xhr=1&gameId={game_id}"

    errors = []

    def fetch_json(url):
        req = urllib.request.Request(url, headers=ESPN_REQUEST_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as response:
            raw_data = _decompress_response(response.read())
            return json.loads(raw_data.decode())

    # Primary: summary endpoint
    try:
        return fetch_json(summary_url)
    except Exception as e:
        if isinstance(e, urllib.error.HTTPError):
            errors.append(f"summary HTTP {e.code}")
        elif isinstance(e, urllib.error.URLError):
            errors.append(f"summary URL error: {e.reason}")
        else:
            errors.append(f"summary error: {e}")

    # Fallback: CDN play-by-play (unwrap gamepackageJSON if present)
    try:
        data = fetch_json(fallback_url)
        if isinstance(data, dict) and data.get('gamepackageJSON'):
            return data.get('gamepackageJSON', {})
        return data
    except Exception as e:
        if isinstance(e, urllib.error.HTTPError):
            errors.append(f"playbyplay HTTP {e.code}")
        elif isinstance(e, urllib.error.URLError):
            errors.append(f"playbyplay URL error: {e.reason}")
        else:
            errors.append(f"playbyplay error: {e}")

    raise Exception(f"Failed to fetch game {game_id}: {'; '.join(errors)}")


def get_play_probabilities(game_id):
    """
    Pull the v2 probabilities feed and map play_id -> probability payload.
    Returns a dict mapping play_id -> probability payload.
    """
    base = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{game_id}/competitions/{game_id}/probabilities"
    prob_map = {}

    def extract_play_id(play_ref):
        if not play_ref:
            return None
        path = urlparse(play_ref).path
        if not path:
            return None
        return path.rstrip('/').split('/')[-1]

    page = 1
    page_count = 1
    while page <= page_count:
        try:
            req = urllib.request.Request(f"{base}?page={page}", headers=ESPN_REQUEST_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw_data = _decompress_response(resp.read())
                data = json.loads(raw_data.decode())
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch win probabilities for game {game_id}, page {page}") from exc

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
    Returns (home_wp, away_wp).
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"

    try:
        req = urllib.request.Request(url, headers=ESPN_REQUEST_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_data = _decompress_response(resp.read())
            data = json.loads(raw_data.decode()) or {}
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


def get_last_play_time(raw_data):
    """
    Extract the wallclock timestamp from the last play.
    Checks current drive first (for live games), then previous drives.
    Returns the ISO timestamp string or None if not found.
    """
    drives_data = raw_data.get('drives', {})
    last_timestamp = None

    # Check current drive first (most recent for live games)
    current_drive = drives_data.get('current', {})
    if current_drive:
        plays = current_drive.get('plays', [])
        if plays:
            last_play = plays[-1]
            last_timestamp = last_play.get('wallclock') or last_play.get('modified')

    # If no timestamp from current drive, check previous drives
    if not last_timestamp:
        previous_drives = drives_data.get('previous', [])
        if previous_drives:
            last_drive = previous_drives[-1]
            plays = last_drive.get('plays', [])
            if plays:
                last_play = plays[-1]
                last_timestamp = last_play.get('wallclock') or last_play.get('modified')

    return last_timestamp


def analyze_game(game_id, wp_threshold=0.975, debug=False):
    """
    Main function to analyze a game and return full payload.
    This is the primary entry point for the API.
    """
    # Fetch data
    raw_data = get_game_data(game_id)
    pregame_home_wp, pregame_away_wp = get_pregame_probabilities(game_id)

    try:
        prob_map = get_play_probabilities(game_id)
    except Exception:
        prob_map = {}
    wp_available = bool(prob_map)

    # Always compute full-game totals. Without a complete WP feed, a purported
    # competitive split would just be full-game data with a misleading label.
    debug_rows = [] if debug else None
    stats_full, details_full = process_game_stats(
        raw_data,
        expanded=True,
        probability_map=prob_map,
        pregame_probabilities=(pregame_home_wp, pregame_away_wp),
        wp_threshold=1.0,
        debug_rows=debug_rows,
        debug_threshold=wp_threshold,
    )
    stats_full, source_gaps = reconcile_final_boxscore(raw_data, stats_full, details_full)
    if wp_available:
        stats_filtered, details_filtered = process_game_stats(
            raw_data,
            expanded=True,
            probability_map=prob_map,
            pregame_probabilities=(pregame_home_wp, pregame_away_wp),
            wp_threshold=wp_threshold,
            penalty_yards_from_plays=True,
        )
    else:
        stats_filtered, details_filtered = stats_full, details_full

    # Extract team metadata
    comps = raw_data.get('header', {}).get('competitions', [])
    team_meta = []
    game_is_final = False
    home_abbr = away_abbr = None
    status = "pregame"
    game_clock = None

    # Extract week info from header
    header = raw_data.get('header', {})
    week_info = header.get('week', 0)
    season_info = header.get('season', {})
    season_type = season_info.get('type', 2) if isinstance(season_info, dict) else 2
    boxscore_abbr_by_id = boxscore_abbreviations_by_id(raw_data)

    if comps:
        comp0 = comps[0]
        status_obj = comp0.get('status', {})
        status, game_clock = _derive_game_status(status_obj)
        game_is_final = status == "final"

        for comp in comp0.get('competitors', []):
            team_id = comp.get('id') or (comp.get('team') or {}).get('id')
            abbr = boxscore_abbr_by_id.get(str(team_id)) or comp.get('team', {}).get('abbreviation')
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

    # Slice details to only include expanded categories
    def slice_details(source):
        return {
            t_id: {cat: source.get(t_id, {}).get(cat, []) for cat in EXPANDED_CATEGORIES}
            for t_id in source
        }

    # Build summary and advanced tables
    summary_filtered = [{k: row[k] for k in SUMMARY_COLS if k in row} for row in stats_filtered]
    advanced_filtered = [{k: row[k] for k in ADVANCED_COLS
                          if k in row and (not wp_available or k != 'Official Yards Per Play (Full Game)')}
                         for row in stats_filtered]
    summary_full = [{k: row[k] for k in SUMMARY_COLS if k in row} for row in stats_full]
    advanced_full = [{k: row[k] for k in ADVANCED_COLS if k in row} for row in stats_full]

    # Build label
    label = f"{away_abbr}_at_{home_abbr}_{game_id}" if away_abbr and home_abbr else f"game_{game_id}"

    # Get last play time for live games display
    last_play_time = get_last_play_time(raw_data)

    try:
        play_epa = calculate_play_epa(raw_data, status)
    except Exception:
        logging.exception('EPA calculation failed for game %s', game_id)
        play_epa = {}

    payload = {
        "gameId": game_id,
        "label": label,
        "status": status,
        "statusDetail": ((comps[0].get('status') or {}).get('type') or {}).get('shortDetail') if comps else None,
        "gameClock": game_clock,
        "lastPlayTime": last_play_time,
        "week": {
            "number": week_info,
            "seasonType": season_type,
        },
        "wp_filter": {
	            "enabled": wp_available,
	            "threshold": wp_threshold,
	            "description": (
	                f"Competitive-play estimate (WP < {wp_threshold * 100:.1f}% at start or end; "
	                f"{len(prob_map)} play probabilities available)"
	                if wp_available else "Win probability unavailable; showing full-game totals"
	            ),
        },
        "metric_scopes": {
            "Penalty Yards": {
                "competitive": (
                    "Sum of accepted ESPN play-level penalties in the WP-selected scope; "
                    "kickoff placement fouls charge zero penalty yards. "
                    "Null when another penalty lacks usable yardage or team attribution. "
                    "Penalties omitted from ESPN play-by-play cannot be counted."
                    if wp_available else "Full-game box-score total; competitive scope unavailable without WP data."
                ),
                "full_game": "ESPN full-game box-score total",
            },
        },
	        "team_meta": team_meta,
	        "summary_table": summary_filtered,
	        "advanced_table": advanced_filtered,
	        "summary_table_full": summary_full,
        "advanced_table_full": advanced_full,
        "expanded_details": slice_details(details_filtered),
        "expanded_details_full": slice_details(details_full),
        "plays": build_play_feed(raw_data, prob_map, pregame_home_wp,
                                 play_epa),
        "source_gaps": source_gaps,
    }

    payload["analysis"] = build_analysis_text(payload)

    if debug:
        payload["debug"] = {
            "statsCompetitive": (
                [{k: v for k, v in row.items()
                  if k != 'Official Yards Per Play (Full Game)'} for row in stats_filtered]
                if wp_available else stats_filtered
            ),
            "statsFull": stats_full,
            "plays": debug_rows,
            "sources": {
                "espnSummary": raw_data,
                "playProbabilities": prob_map,
                "pregameProbabilities": {
                    "home": pregame_home_wp,
                    "away": pregame_away_wp,
                },
            },
        }

    return payload
