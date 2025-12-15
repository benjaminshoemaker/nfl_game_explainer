"""
NFL Game Analysis Core Module

Shared pure analytics functions used by both CLI (game_compare.py) and API (game_analysis.py).
No I/O or HTTP dependencies - just data transformation logic.
"""

import re


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
    """Detect if a play is a penalty play that should be excluded from stats."""
    if play.get('penalty') and 'no play' in text_lower:
        return True
    if play.get('hasPenalty'):
        return True
    if 'no play' in text_lower and ('penalty' in text_lower or 'penalty' in type_lower):
        return True
    return False


def is_spike_or_kneel(text_lower, type_lower):
    """Detect clock-management plays (spikes, QB kneels)."""
    if 'spike' in text_lower or 'spike' in type_lower:
        return True
    if 'kneel' in text_lower or 'kneel' in type_lower or 'qb kneel' in text_lower:
        return True
    return False


def is_special_teams_play(text_lower, type_lower):
    """
    Identify special teams plays (punts, kickoffs, FGs, XPs).
    Returns False for touchdowns to avoid filtering offensive TDs.
    """
    if 'touchdown' in text_lower or 'touchdown' in type_lower:
        return False
    st_keywords = ['punt', 'kickoff', 'field goal', 'extra point', 'xp', 'fg', 'onside']
    return any(k in text_lower or k in type_lower for k in st_keywords)


def is_nullified_play(text_lower):
    """Detect plays that didn't happen (nullified, no play)."""
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
    if ('kickoff' in text_lower or 'kickoff' in type_lower) and 'return' in type_lower:
        return False, False, False
    if ('punt' in text_lower or 'punt' in type_lower) and 'return' in type_lower:
        return False, False, False

    pass_hint = (any_stat_contains(play, ['pass', 'sack']) or
                 'pass' in type_lower or 'sack' in type_lower or
                 'scramble' in type_lower or 'pass' in text_lower or
                 'sack' in text_lower or 'scramble' in text_lower)

    # Detect rushing plays - include common rush direction phrases
    rush_patterns = ['up the middle', 'left end', 'right end', 'left tackle',
                     'right tackle', 'left guard', 'right guard', 'middle for',
                     'around left', 'around right']
    rush_hint = (any_stat_contains(play, ['rush']) or 'rush' in type_lower or
                 'run' in text_lower or any(p in text_lower for p in rush_patterns))

    # Scrambles should be treated as pass dropbacks, not runs
    if pass_hint and rush_hint and ('scramble' in text_lower or 'scramble' in type_lower):
        rush_hint = False

    return True, rush_hint, pass_hint


def is_competitive_play(play, probability_map, wp_threshold=0.975, start_home_wp=None, start_away_wp=None):
    """
    Return True if the play occurred while the game was still competitive.

    Competitive if:
    - Overtime period (period number >= 5)
    - No play id or no probability data (assume competitive)
    - Both teams' win probability are below the threshold at play start

    Uses start_home_wp/start_away_wp (start-of-play) when provided.
    Falls back to probability_map data when start probabilities not available.
    """
    period = play.get('period', {}).get('number', 0)
    if period >= 5:
        return True

    # Use start-of-play probabilities if provided (preferred)
    if start_home_wp is not None and start_away_wp is not None:
        return start_home_wp < wp_threshold and start_away_wp < wp_threshold

    # Fall back to probability_map (end-of-play approximation)
    play_id = play.get('id')
    prob = (probability_map or {}).get(str(play_id)) if play_id is not None else None
    if prob:
        home_wp = prob.get('homeWinPercentage', 0.5)
        away_wp = prob.get('awayWinPercentage', 0.5)
        return home_wp < wp_threshold and away_wp < wp_threshold

    return True


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

            competitive = is_competitive_play(play, probability_map, wp_threshold, prev_home_wp, prev_away_wp)
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
                if play.get('scoringPlay') and 'field goal' in play_type_lower:
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

            # Special teams tracking (punts, kickoffs)
            if 'punt' in play_type_lower and 'return' not in play_type_lower:
                yards = play.get('statYardage', 0)
                if isinstance(yards, (int, float)):
                    stats[team_id]['Punt Net Sum'] += yards
                    stats[team_id]['Punt Plays'] += 1
            if 'kickoff' in play_type_lower and 'return' not in play_type_lower:
                yards = play.get('statYardage', 0)
                if isinstance(yards, (int, float)):
                    stats[team_id]['Kick Net Sum'] += yards
                    stats[team_id]['Kick Plays'] += 1

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

    # Calculate turnover margins
    ids = list(stats.keys())
    turnover_margin = {}
    if len(ids) == 2:
        a, b = ids[0], ids[1]
        turnover_margin[a] = stats[b]['Turnovers'] - stats[a]['Turnovers']
        turnover_margin[b] = stats[a]['Turnovers'] - stats[b]['Turnovers']
    else:
        for t_id in ids:
            turnover_margin[t_id] = 0

    # Build final rows
    final_rows = []
    for t_id, d in stats.items():
        plays = max(d['Plays'], 1)
        drives_in_40 = max(d['Drives Inside 40'], 1)
        drives_total = max(d['Drives Count'], 1)
        punt_plays = max(d['Punt Plays'], 1)
        kick_plays = max(d['Kick Plays'], 1)

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
            'Turnover Margin': turnover_margin.get(t_id, 0),
            'Points per Drive': round(d['Drive Points'] / drives_total, 2),
            'Net Punting': round(d['Punt Net Sum'] / punt_plays, 1) if d['Punt Plays'] > 0 else 0,
            'Net Kickoff': round(d['Kick Net Sum'] / kick_plays, 1) if d['Kick Plays'] > 0 else 0,
            'ST Penalties': d.get('ST Penalties', 0),
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
