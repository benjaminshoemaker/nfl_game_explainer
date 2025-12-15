"""
Game analysis module - ported from game_compare.py for serverless API use.
Removes file I/O, CLI parsing, and returns data structures directly.
"""

import json
import urllib.request
import urllib.error
from urllib.parse import urlparse


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


def get_game_data(game_id):
    """Pull the full game play-by-play JSON from ESPN core API."""
    import time
    cache_buster = int(time.time())
    url = f"https://cdn.espn.com/core/nfl/playbyplay?xhr=1&gameId={game_id}&cb={cache_buster}"

    # Full browser-like headers to avoid 401 errors from ESPN CDN
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.espn.com/',
        'Origin': 'https://www.espn.com',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
        return data.get('gamepackageJSON', {})
    except urllib.error.HTTPError as e:
        raise Exception(f"Failed to fetch game {game_id}: HTTP {e.code}")
    except urllib.error.URLError as e:
        raise Exception(f"Failed to connect to ESPN for game {game_id}: {e.reason}")


def get_play_probabilities(game_id):
    """
    Pull the v2 probabilities feed and map play_id -> probability payload.
    Returns a dict mapping play_id -> probability payload.
    """
    # Full browser-like headers to avoid 401 errors from ESPN
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.espn.com/',
        'Origin': 'https://www.espn.com',
    }
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
            req = urllib.request.Request(f"{base}?page={page}", headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
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
    Returns (home_wp, away_wp).
    """
    # Full browser-like headers to avoid 401 errors from ESPN
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.espn.com/',
        'Origin': 'https://www.espn.com',
    }
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode()) or {}
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


def yardline_to_coord(pos_text, team_abbr):
    """Convert possessionText like 'SEA 24' into a 0-100 coordinate."""
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


def calculate_success(down, distance, yards_gained):
    """Determine if a play was 'successful' based on standard analytics definition."""
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
    Returns (is_offense_play, is_run, is_pass).
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
    if ('kickoff' in text_lower or 'kickoff' in type_lower) and 'return' in type_lower:
        return False, False, False
    if ('punt' in text_lower or 'punt' in type_lower) and 'return' in type_lower:
        return False, False, False

    pass_hint = (any_stat_contains(play, ['pass', 'sack']) or
                 'pass' in type_lower or 'sack' in type_lower or
                 'scramble' in type_lower or 'pass' in text_lower or
                 'sack' in text_lower or 'scramble' in text_lower)

    rush_patterns = ['up the middle', 'left end', 'right end', 'left tackle',
                     'right tackle', 'left guard', 'right guard', 'middle for',
                     'around left', 'around right']
    rush_hint = (any_stat_contains(play, ['rush']) or 'rush' in type_lower or
                 'run' in text_lower or any(p in text_lower for p in rush_patterns))

    if pass_hint and rush_hint and ('scramble' in text_lower or 'scramble' in type_lower):
        rush_hint = False

    return True, rush_hint, pass_hint


def is_competitive_play(play, probability_map, wp_threshold=0.975):
    """Return True if the play occurred while the game was still competitive."""
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


def process_game_stats(game_data, expanded=False, probability_map=None,
                       pregame_probabilities=None, wp_threshold=0.975):
    """
    Process game data and return stats as dict rows (not DataFrame).
    Returns (stats_rows, details) where stats_rows is a list of dicts.
    """
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

    # Map play_id -> drive offensive team
    play_to_drive_team = {}
    for drive in drives:
        drive_team_id = drive.get('team', {}).get('id')
        for play in drive.get('plays', []):
            play_id = play.get('id')
            if play_id:
                play_to_drive_team[str(play_id)] = drive_team_id

    prev_home_wp = sanitize_prob(preg_home)
    prev_away_wp = sanitize_prob(preg_away, fallback=1 - prev_home_wp)

    def lookup_probability_with_delta(play):
        pid = play.get('id')
        if pid is None:
            return None
        prob = probability_map.get(str(pid))
        if not prob:
            return None

        home_wp = prob.get('homeWinPercentage', 0.5)
        away_wp = prob.get('awayWinPercentage', 0.5)

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

    # Initialize storage
    stats = {}
    details = {}
    for team in teams_info:
        t_id = team['team']['id']
        t_name = team['team']['abbreviation']
        stats[t_id] = {
            'Team': t_name,
            'Score': 0,
            'Plays': 0,
            'Total Yards': 0,
            'Successful Plays': 0,
            'Explosive Plays': 0,
            'Turnovers': 0,
            'Drives Inside 40': 0,
            'Points Inside 40': 0,
            'Start Field Pos Sum': 0,
            'Drives Count': 0,
            'Drive Points': 0,
            'Penalty Yards': 0,
            'Penalty Count': 0,
            'Non-Offensive Points': 0
        }
        if expanded:
            details[t_id] = {
                'Turnovers': [],
                'Explosive Plays': [],
                'Non-Offensive Scores': [],
                'Points Per Trip (Inside 40)': [],
                'Penalty Yards': [],
                'Non-Offensive Points': []
            }

    # Get scores
    competitions = game_data.get('header', {}).get('competitions', [])
    if competitions:
        header = competitions[0]
        for competitor in header.get('competitors', []):
            t_id = competitor['id']
            if t_id in stats:
                stats[t_id]['Score'] = int(competitor.get('score', 0))

    # Penalty totals from boxscore
    for t in teams_info:
        t_id = t.get('team', {}).get('id')
        if not t_id or t_id not in stats:
            continue
        team_stats = t.get('statistics', [])
        for stat in team_stats:
            stat_name = stat.get('name', '')
            if stat_name == 'totalPenaltiesYards':
                display_val = stat.get('displayValue', '')
                if isinstance(display_val, str) and '-' in display_val:
                    parts = display_val.split('-')
                    if len(parts) == 2:
                        try:
                            stats[t_id]['Penalty Count'] = int(parts[0])
                            stats[t_id]['Penalty Yards'] = int(parts[1])
                        except ValueError:
                            pass
                break

    # Non-Offensive Points
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

        has_touchdown = 'touchdown' in play_text or 'touchdown' in play_type or 'touchdown' in scoring_type
        is_kick_return_td = ('kickoff' in play_text or 'kickoff' in play_type) and has_touchdown
        is_punt_return_td = ('punt' in play_text or 'punt' in play_type) and has_touchdown and ('return' in play_text or 'return' in play_type)

        if is_safety:
            is_non_offensive = True
            points = 2
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

    # Process drives and plays
    for drive in drives:
        team_id = drive.get('team', {}).get('id')
        if team_id not in stats:
            continue

        drive_plays = drive.get('plays', [])
        drive_start_yte = drive.get('start', {}).get('yardsToEndzone', -1)
        drive_points_competitive = 0
        drive_crossed_40_competitive = False
        drive_started_competitive = False
        drive_first_play_checked = False
        drive_has_offensive_play = False
        last_competitive_play = None
        last_competitive_prob = None
        current_yte_est = drive_start_yte if isinstance(drive_start_yte, (int, float)) else None

        for play in drive_plays:
            text = play.get('text', '')
            text_lower = text.lower()
            play_type = play.get('type', {}).get('text', 'Unknown')
            play_type_lower = play_type.lower()
            start_team_id = play.get('start', {}).get('team', {}).get('id') or team_id
            end_team_id = play.get('end', {}).get('team', {}).get('id')
            team_abbrev = play.get('team', {}).get('abbreviation', '').lower()
            offense_abbrev = team_abbrev or id_to_abbr.get(team_id, '').lower()
            opponent_id = None
            if len(id_to_abbr) == 2 and start_team_id in id_to_abbr:
                opponent_id = next((tid for tid in id_to_abbr if tid != start_team_id), None)

            competitive = is_competitive_play(play, probability_map, wp_threshold)
            probability_snapshot = lookup_probability_with_delta(play)

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

            # Handle penalty plays for expanded details
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
                    'probability': probability_snapshot
                })

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
            muffed_kick = muffed_punt or ('muffed kick' in text_lower) or ('muffed kickoff' in text_lower)
            interception = 'interception' in play_type_lower or 'intercept' in text_lower
            fumble_phrase = 'fumble' in text_lower
            overturned = 'reversed' in text_lower or 'overturned' in text_lower

            turnover_events = []
            current_possessor = start_team_id
            current_off_abbr = offense_abbrev

            if muffed_kick and opponent_id:
                current_possessor = opponent_id
                current_off_abbr = id_to_abbr.get(opponent_id, '').lower()

            if interception and not overturned:
                turnover_events.append((current_possessor, 'interception'))
                if opponent_id:
                    current_possessor = opponent_id

            recovered_by_def = False
            recovered_team_id = None
            if fumble_phrase:
                if 'recovered by' in text_lower:
                    if current_off_abbr:
                        recovered_by_def = f"recovered by {current_off_abbr}" not in text_lower
                    else:
                        recovered_by_def = True
                if start_team_id and end_team_id and start_team_id != end_team_id:
                    recovered_by_def = current_possessor != end_team_id
                    recovered_team_id = end_team_id

            fumble_turnover = fumble_phrase and recovered_by_def and not overturned
            if fumble_turnover and not muffed_kick:
                turnover_events.append((current_possessor, 'fumble'))

            if muffed_kick and not overturned:
                turnover_events.append((current_possessor, 'muffed_kick'))

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
                            'probability': lookup_probability_with_delta(play),
                            'reason': reason
                        })

            # Scoring
            play_id = play.get('id')
            if play.get('scoringPlay') and drive_started_competitive:
                if play_id in scoring_map:
                    sp = scoring_map[play_id]
                    if sp.get('team') == team_id:
                        drive_points_competitive += sp.get('points', 0)
                else:
                    drive_points_competitive += play.get('scoreValue', 0)

            # Non-offensive points details
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
                        'probability': probability_snapshot
                    })

            # Offensive stats
            is_offense, is_run, is_pass = classify_offense_play(play)
            if is_offense and (is_run or is_pass):
                stats[team_id]['Plays'] += 1
                yards = play.get('statYardage', 0)

                if turnover_on_play:
                    yards = 0
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

                if calculate_success(down, dist, yards):
                    stats[team_id]['Successful Plays'] += 1

                if (is_run and yards >= 10) or (is_pass and yards >= 20):
                    stats[team_id]['Explosive Plays'] += 1
                    if expanded:
                        details[team_id]['Explosive Plays'].append({
                            'yards': yards,
                            'text': text,
                            'type': 'Run' if is_run else 'Pass',
                            'quarter': play.get('period', {}).get('number'),
                            'clock': play.get('clock', {}).get('displayValue'),
                            'probability': lookup_probability_with_delta(play)
                        })

            update_prev_wp(play)

        if drive_started_competitive:
            if drive_has_offensive_play and drive_start_yte != -1 and drive_start_yte <= 40:
                drive_crossed_40_competitive = True
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
                    'points': drive_points_competitive,
                    'probability': last_competitive_prob
                })

    # Build final rows
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
            'Penalty Yards': d.get('Penalty Yards', 0),
            'Non-Offensive Points': d.get('Non-Offensive Points', 0)
        }
        final_rows.append(row)

    if expanded:
        return final_rows, details
    return final_rows, {}


def build_analysis_text(payload):
    """Create a short plain-text summary for the UI."""
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

    def add_stat_line(label, key):
        a_val = away_adv.get(key)
        h_val = home_adv.get(key)
        if a_val is None or h_val is None:
            return
        a_display = round(a_val, 2) if isinstance(a_val, float) else a_val
        h_display = round(h_val, 2) if isinstance(h_val, float) else h_val
        parts.append(f"{label}: {away_abbr} {a_display} vs {home_abbr} {h_display}.")

    add_stat_line("Explosive plays", "Explosive Plays")
    add_stat_line("Yards per play", "Yards Per Play")

    return " ".join(parts)


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


def analyze_game(game_id, wp_threshold=0.975):
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

    # Process both filtered and full stats
    stats_filtered, details_filtered = process_game_stats(
        raw_data,
        expanded=True,
        probability_map=prob_map,
        pregame_probabilities=(pregame_home_wp, pregame_away_wp),
        wp_threshold=wp_threshold
    )
    stats_full, details_full = process_game_stats(
        raw_data,
        expanded=True,
        probability_map=prob_map,
        pregame_probabilities=(pregame_home_wp, pregame_away_wp),
        wp_threshold=1.0
    )

    # Extract team metadata
    comps = raw_data.get('header', {}).get('competitions', [])
    team_meta = []
    game_status_label = "Final"
    game_is_final = True
    home_abbr = away_abbr = None

    if comps:
        comp0 = comps[0]
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

    # Determine status for API response
    if game_is_final:
        status = "final"
    elif game_status_label.startswith("Q") or game_status_label.startswith("OT"):
        status = "in-progress"
    else:
        status = "pregame"

    # Slice details to only include expanded categories
    def slice_details(source):
        return {
            t_id: {cat: source.get(t_id, {}).get(cat, []) for cat in EXPANDED_CATEGORIES}
            for t_id in source
        }

    # Build summary and advanced tables
    summary_filtered = [{k: row[k] for k in SUMMARY_COLS if k in row} for row in stats_filtered]
    advanced_filtered = [{k: row[k] for k in ADVANCED_COLS if k in row} for row in stats_filtered]
    summary_full = [{k: row[k] for k in SUMMARY_COLS if k in row} for row in stats_full]
    advanced_full = [{k: row[k] for k in ADVANCED_COLS if k in row} for row in stats_full]

    # Build label
    label = f"{away_abbr}_at_{home_abbr}_{game_id}" if away_abbr and home_abbr else f"game_{game_id}"

    # Extract game clock info
    game_clock = None
    if not game_is_final and comps:
        status_obj = comps[0].get('status', {})
        period = status_obj.get('period', 0)
        clock = status_obj.get('displayClock', '')
        if period > 0:
            game_clock = {
                "quarter": period,
                "clock": clock,
                "displayValue": game_status_label
            }

    # Get last play time for live games
    last_play_time = get_last_play_time(raw_data) if not game_is_final else None

    payload = {
        "gameId": game_id,
        "label": label,
        "status": status,
        "gameClock": game_clock,
        "lastPlayTime": last_play_time,
        "wp_filter": {
            "enabled": True,
            "threshold": wp_threshold,
            "description": f"Stats reflect competitive plays only (WP < {wp_threshold * 100:.1f}%)",
        },
        "team_meta": team_meta,
        "summary_table": summary_filtered,
        "advanced_table": advanced_filtered,
        "summary_table_full": summary_full,
        "advanced_table_full": advanced_full,
        "expanded_details": slice_details(details_filtered),
        "expanded_details_full": slice_details(details_full),
    }

    payload["analysis"] = build_analysis_text(payload)

    return payload
