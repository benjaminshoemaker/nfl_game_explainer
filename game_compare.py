import argparse
import os
import requests
import pandas as pd
import json


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

def process_game_stats(game_data, expanded=False, probability_map=None):
    boxscore = game_data.get('boxscore', {})
    teams_info = boxscore.get('teams', [])
    id_to_abbr = {}
    probability_map = probability_map or {}

    # Track previous WP for delta calculation
    prev_home_wp = 0.5
    prev_away_wp = 0.5

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
            'ST Penalties': 0
        }
        if expanded:
            details[t_id] = {
                'Turnovers': [],
                'Explosive Plays': [],
                'Net Punting': [],
                'Net Kickoff': [],
                'Hidden Yards': [],
                'ST Penalties': []
            }

    # --- 1. Get High Level Score/Turnovers ---
    competitions = game_data.get('header', {}).get('competitions', [])
    if competitions:
        header = competitions[0]
        for competitor in header.get('competitors', []):
            t_id = competitor['id']
            if t_id in stats:
                stats[t_id]['Score'] = int(competitor.get('score', 0))
    
    # --- 2. Process Drives and Plays (The "How") ---
    drives = game_data.get('drives', {}).get('previous', [])
    
    for drive in drives:
        team_id = drive.get('team', {}).get('id')
        if team_id not in stats: continue
        
        drive_plays = drive.get('plays', [])
        start_yte = -1
        if drive_plays:
            start_yte = drive_plays[0].get('start', {}).get('yardsToEndzone', -1)
        if start_yte == -1:
            start_yte = drive.get('start', {}).get('yardsToEndzone', -1)

        if start_yte != -1:
            # 100 - yards_to_endzone = own yard line distance from goal
            start_loc = 100 - start_yte
            stats[team_id]['Start Field Pos Sum'] += start_loc
        stats[team_id]['Drives Count'] += 1

        drive_yards = drive.get('yards', 0)
        drive_points = 0
        crossed_40 = False

        # --- Process Plays for Efficiency/Explosives ---
        for play in drive.get('plays', []):
            text = play.get('text', '')
            text_lower = text.lower()
            play_type = play.get('type', {}).get('text', 'Unknown')
            team_abbrev = play.get('team', {}).get('abbreviation', '').lower()
            play_type_lower = play_type.lower()
            
            # Filter out non-plays, nullified, timeouts/end-of-period
            if 'timeout' in play_type_lower or 'end of' in play_type_lower:
                continue
            if is_nullified_play(text_lower):
                continue
            
            # Turnovers
            muffed_punt = 'muffed punt' in text_lower or 'muff' in play_type_lower
            # Broaden interception/fumble detection beyond "Fumble Lost" phrasing.
            interception = 'interception' in play_type_lower or 'intercept' in text_lower
            fumble_phrase = 'fumble' in text_lower
            recovered_by_def = False
            if fumble_phrase and 'recovered by' in text_lower:
                # Treat as turnover if the recovery text does not belong to the offense.
                if team_abbrev:
                    recovered_by_def = f"recovered by {team_abbrev}" not in text_lower
                else:
                    recovered_by_def = True
            fumble_turnover = fumble_phrase and recovered_by_def
            overturned = 'reversed' in text_lower or 'overturned' in text_lower
            
            turnover_on_play = (interception or fumble_turnover or muffed_punt) and not overturned
            if turnover_on_play:
                stats[team_id]['Turnovers'] += 1
                if expanded:
                    details[team_id]['Turnovers'].append({
                        'type': play_type,
                        'text': text,
                        'yards': play.get('statYardage', 0),
                        'quarter': play.get('period', {}).get('number'),
                        'clock': play.get('clock', {}).get('displayValue'),
                        'start_pos': play.get('start', {}).get('possessionText'),
                        'down_dist': play.get('start', {}).get('downDistanceText') or play.get('start', {}).get('shortDownDistanceText'),
                        'probability': lookup_probability_with_delta(play)
                    })
            
            # Track scoring tied to the offense on the drive via scoringPlays map
            play_id = play.get('id')
            if play.get('scoringPlay'):
                if play_id in scoring_map:
                    sp = scoring_map[play_id]
                    if sp.get('team') == team_id:
                        drive_points += sp.get('points', 0)
                else:
                    drive_points += play.get('scoreValue', 0)
            
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

        # Determine if the drive reached opponent 40 and assign points to that trip
        # If start inside 40 OR (start position + yards gained) crosses the 40
        if start_yte != -1:
            if start_yte <= 40:
                crossed_40 = True
            elif (100 - start_yte) + drive_yards >= 60:
                crossed_40 = True
        
        if crossed_40:
            stats[team_id]['Drives Inside 40'] += 1
            stats[team_id]['Points Inside 40'] += drive_points
        
        stats[team_id]['Drive Points'] += drive_points

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
            'ST Penalties': round(stats[t_id]['ST Penalties'], 1)
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
    args = parser.parse_args()

    try:
        print(f"Fetching data for Game ID: {args.game_id}...")
        raw_data = get_game_data(args.game_id)
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
        df, details = process_game_stats(raw_data, expanded=True, probability_map=prob_map)

        if last_play_line:
            print(f"\n{last_play_line}")

        # Build Summary and Advanced tables (teams as columns)
        summary_cols = ['Team', 'Score', 'Total Yards', 'Drives']
        advanced_cols = [
            'Team', 'Score', 'Turnovers', 'Total Yards', 'Yards Per Play',
            'Success Rate', 'Explosive Plays', 'Explosive Play Rate',
            'Points Per Trip (Inside 40)', 'Ave Start Field Pos'
        ]
        df_summary_display = df[summary_cols].set_index('Team').T
        df_advanced_display = df[advanced_cols].set_index('Team').T

        print("\n--- SUMMARY STATS ---")
        print(df_summary_display)

        print("\n--- ADVANCED STATS ---")
        print(df_advanced_display)

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

        df[advanced_cols].to_csv(csv_path, index=False)

        # Build JSON payload with summary, advanced, and expanded details
        expanded_categories = ['Turnovers', 'Explosive Plays']
        filtered_details = {}
        for t_id, team_detail in details.items():
            filtered_details[t_id] = {
                cat: team_detail.get(cat, []) for cat in expanded_categories
            }

        payload = {
            "gameId": game_id,
            "label": fname_base,
            "summary_table": df[summary_cols].to_dict(orient="records"),
            "advanced_table": df[advanced_cols].to_dict(orient="records"),
            "expanded_details": filtered_details,
            "team_meta": team_meta,
            "last_play": last_play_line
        }
        payload["analysis"] = build_analysis_text(payload)
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
            categories = ['Turnovers', 'Explosive Plays']
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
