"""
NFL Game Analysis Core Module

Shared pure analytics functions used by both CLI (game_compare.py) and API (game_analysis.py).
No I/O or HTTP dependencies - just data transformation logic.
"""

import re


# ESPN replay notes are inconsistent about punctuation/spacing:
# e.g. "play was REVERSED.(Shotgun) ..." or "play was REVERSED (Shotgun) ..."
_REPLAY_DECISION_RE = re.compile(r"\b(?:reversed|overturned)\b[.:]?\s*", re.IGNORECASE)
_YARDS_FOR_RE = re.compile(r"\bfor (-?\d+) yards\b", re.IGNORECASE)
_YARDS_LOSS_RE = re.compile(r"\bfor loss of (\d+) yards\b", re.IGNORECASE)
_RECOVERED_BY_ABBR_RE = re.compile(r"\brecovered by\s+([a-z]{2,4})\b", re.IGNORECASE)
_TEAM_ABBR_ALIASES = {
    # ESPN play text can use older abbreviations than the boxscore/team metadata.
    "was": "wsh",
}


def final_play_text(text):
    """
    ESPN play text sometimes contains an original ruling plus a replay-updated
    re-statement after 'REVERSED.'/'OVERTURNED.'.

    For event detection (turnovers, etc), we should use the final re-stated
    portion when present; otherwise use the original text.
    """
    if not text:
        return ''

    last_match = None
    for match in _REPLAY_DECISION_RE.finditer(text):
        last_match = match

    if not last_match:
        return text

    candidate = text[last_match.end():].lstrip()
    return candidate if candidate else text


def _credited_yards_before_fumble(event_text):
    """
    For fumble plays, ESPN's `statYardage` can reflect net outcome (including recovery),
    while official offense yards are credited to the gain/loss before the fumble.

    Use the last "for X yards" mention BEFORE the first "fumble" in the (final) play text
    when available; otherwise return None and fall back to `statYardage`.
    """
    if not event_text:
        return None
    lower = event_text.lower()
    if 'fumble' not in lower:
        return None

    prefix = lower.split('fumble', 1)[0]

    matches = list(_YARDS_FOR_RE.finditer(prefix))
    if matches:
        try:
            return int(matches[-1].group(1))
        except ValueError:
            return None

    if 'for no gain' in prefix or 'for no loss' in prefix:
        return 0

    m = _YARDS_LOSS_RE.search(prefix)
    if m:
        try:
            return -int(m.group(1))
        except ValueError:
            return None

    return None


def classify_total_offense_play(play):
    """
    Classify plays for ESPN-style total offense (Total Yards) reconciliation.

    Compared to `classify_offense_play`, this includes kneels/spikes as offense plays.
    """
    text_lower = play.get('text', '').lower()
    type_lower = play.get('type', {}).get('text', 'unknown').lower()

    if is_nullified_play(text_lower):
        return False, False, False
    if is_penalty_play(play, text_lower, type_lower):
        return False, False, False
    if is_special_teams_play(text_lower, type_lower):
        return False, False, False

    # Kickoff/punt returns are special teams plays, not offensive plays.
    if ('kickoff' in text_lower or 'kickoff' in type_lower) and 'return' in type_lower:
        return False, False, False
    if ('punt' in text_lower or 'punt' in type_lower) and 'return' in type_lower:
        return False, False, False

    # Spikes/kneels should count toward total offense.
    if is_spike_or_kneel(text_lower, type_lower):
        return True, 'kneel' in text_lower or 'kneel' in type_lower, 'spike' in text_lower or 'spike' in type_lower

    pass_hint = (any_stat_contains(play, ['pass', 'sack']) or
                 'pass' in type_lower or 'sack' in type_lower or
                 'scramble' in type_lower or 'pass' in text_lower or
                 'sack' in text_lower or 'scramble' in text_lower)

    rush_patterns = ['up the middle', 'left end', 'right end', 'left tackle',
                     'right tackle', 'left guard', 'right guard', 'middle for',
                     'around left', 'around right']
    rush_hint = (any_stat_contains(play, ['rush']) or 'rush' in type_lower or
                 'run' in text_lower or any(p in text_lower for p in rush_patterns))

    # Aborted snaps are counted as rush attempts in official stats.
    if 'aborted' in text_lower and 'fumble' in text_lower:
        rush_hint = True

    if pass_hint and rush_hint and ('scramble' in text_lower or 'scramble' in type_lower):
        rush_hint = False

    return True, rush_hint, pass_hint


_ENFORCED_AT_SPOT_RE = re.compile(r'\benforced at(?: the)?\s+([A-Z]{2,3})\s+(\d{1,2})\b', re.IGNORECASE)


def _enforced_at_yards_to_endzone(event_text, offense_abbrev):
    """
    Parse 'enforced at XXX NN' and convert to yardsToEndzone (relative to the offense).

    This lets us derive the offensive yards credited on accepted-penalty plays without
    incorporating the penalty yardage into Total Yards.
    """
    if not event_text or not offense_abbrev:
        return None
    m = _ENFORCED_AT_SPOT_RE.search(event_text)
    if not m:
        return None
    side = m.group(1).upper()
    try:
        yard = int(m.group(2))
    except ValueError:
        return None

    if yard < 0 or yard > 50:
        return None
    if yard == 50:
        return 50

    off = offense_abbrev.upper()
    return (100 - yard) if side == off else yard


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
    if 'declined' in text_lower:
        return False
    if 'offsetting' in text_lower:
        return False
    if play.get('penalty') and 'no play' in text_lower:
        return True
    if play.get('hasPenalty') and 'no play' in text_lower:
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


def is_declined_only_penalty(text_lower, penalty_info):
    """
    Return True when a play contains a declined penalty that should not be shown
    in penalty play lists.

    ESPN often embeds "declined" in play text even when an accepted penalty is
    also present (e.g. one enforced + a second declined). When structured
    penalty info exists and is not declined, treat the play as an enforced
    penalty.
    """
    if not text_lower or 'declined' not in text_lower:
        status_slug = ((penalty_info or {}).get('status') or {}).get('slug')
        return status_slug == 'declined'

    status_slug = ((penalty_info or {}).get('status') or {}).get('slug')
    if status_slug and status_slug != 'declined':
        return False

    # Keep plays that clearly indicate an enforced/accepted penalty.
    if 'enforced' in text_lower or 'accepted' in text_lower or 'no play' in text_lower:
        return False

    return True


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
    - The game is competitive at either the start OR end of the play:
      max(home_wp, away_wp) < wp_threshold

    Uses start_home_wp/start_away_wp (start-of-play) when provided and
    probability_map (end-of-play) when available.
    """
    period = play.get('period', {}).get('number', 0)
    if period >= 5:
        return True

    def _is_competitive_from_probs(home_wp, away_wp):
        if home_wp is None or away_wp is None:
            return None
        try:
            return max(float(home_wp), float(away_wp)) < wp_threshold
        except (TypeError, ValueError):
            return None

    start_competitive = None
    if start_home_wp is not None and start_away_wp is not None:
        start_competitive = _is_competitive_from_probs(start_home_wp, start_away_wp)

    # probability_map entries are end-of-play; we use them to include plays that
    # make a game competitive even if the start-of-play WP was non-competitive.
    play_id = play.get('id')
    prob = (probability_map or {}).get(str(play_id)) if play_id is not None else None
    end_competitive = None
    if prob:
        end_competitive = _is_competitive_from_probs(
            prob.get('homeWinPercentage', 0.5),
            prob.get('awayWinPercentage', 0.5),
        )

    if start_competitive is None and end_competitive is None:
        return True
    if start_competitive is None:
        return bool(end_competitive)
    if end_competitive is None:
        return bool(start_competitive)
    return bool(start_competitive or end_competitive)


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

    # Build a start-of-play WP lookup keyed by play id so every WP threshold check
    # can consistently use start-of-play probabilities (not end-of-play).
    #
    # ESPN probability_map entries are end-of-play; start-of-play is the previous
    # play's end-of-play (or pregame for the first play).
    start_wp_by_play_id = {}
    walk_home_wp = prev_home_wp
    walk_away_wp = prev_away_wp
    for drive in drives:
        for play in drive.get('plays', []):
            pid = play.get('id')
            if pid is None:
                continue
            pid_str = str(pid)
            start_wp_by_play_id[pid_str] = (walk_home_wp, walk_away_wp)
            prob = probability_map.get(pid_str)
            if prob:
                home_end = prob.get('homeWinPercentage')
                away_end = prob.get('awayWinPercentage')
                if isinstance(home_end, (int, float)):
                    walk_home_wp = sanitize_prob(home_end, fallback=walk_home_wp)
                if isinstance(away_end, (int, float)):
                    walk_away_wp = sanitize_prob(away_end, fallback=walk_away_wp)

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
            'Offensive Yards': 0,
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
                'All Plays': [],
                'Turnovers': [],
                'Explosive Plays': [],
                'Non-Offensive Scores': [],
                'Points Per Trip (Inside 40)': [],
                'Drive Starts': [],
                'Penalty Yards': [],
                'Total Yards Corrections': [],
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
        play_id = sp.get('id')
        start_wps = start_wp_by_play_id.get(str(play_id)) if play_id is not None else None
        if start_wps is not None:
            competitive_scoring = is_competitive_play(
                sp,
                probability_map,
                wp_threshold,
                start_home_wp=start_wps[0],
                start_away_wp=start_wps[1],
            )
        else:
            competitive_scoring = is_competitive_play(sp, probability_map, wp_threshold)
        if not competitive_scoring:
            continue
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
    def _end_pos_text(play_obj):
        end = (play_obj.get('end') or {}) if isinstance(play_obj, dict) else {}
        if not isinstance(end, dict):
            return None
        pos_text = end.get('possessionText')
        if isinstance(pos_text, str) and pos_text.strip():
            return pos_text.strip()
        down_dist = end.get('downDistanceText')
        if isinstance(down_dist, str):
            m = re.search(r"\bat\s+([A-Z]{2,3}\s+\d+)\b", down_dist)
            if m:
                return m.group(1)
        return None

    def _is_drive_boundary_noise(play_obj):
        ptype = (play_obj.get('type', {}) or {}).get('text', '') or ''
        ptype_lower = ptype.lower()
        txt = (play_obj.get('text', '') or '').lower()
        return ('timeout' in ptype_lower) or ('end of' in ptype_lower) or ('end of' in txt)

    def _is_kick_or_punt_start(play_obj):
        ptype = (play_obj.get('type', {}) or {}).get('text', '') or ''
        ptype_lower = ptype.lower()
        txt = (play_obj.get('text', '') or '').lower()
        return ('kickoff' in ptype_lower) or ('kickoff' in txt) or ('punt' in ptype_lower) or ('onside' in txt)

    for drive_index, drive in enumerate(drives):
        team_id = drive.get('team', {}).get('id')
        if team_id not in stats:
            continue

        drive_plays = drive.get('plays', [])
        drive_first_play = drive_plays[0] if drive_plays else None
        drive_start_yte = drive.get('start', {}).get('yardsToEndzone', -1)
        drive_start_pos_text = (drive.get('start', {}) or {}).get('text')
        if not isinstance(drive_start_pos_text, str) or not drive_start_pos_text.strip():
            drive_start_pos_text = (drive.get('start', {}) or {}).get('yardLine')
        if not isinstance(drive_start_pos_text, str) or not drive_start_pos_text.strip():
            drive_start_pos_text = None
        drive_points_competitive = 0
        drive_crossed_40_competitive = False
        drive_started_competitive = False
        drive_first_play_checked = False
        drive_has_offensive_play = False
        last_competitive_play = None
        last_competitive_prob = None
        current_yte_est = drive_start_yte if isinstance(drive_start_yte, (int, float)) else None
        drive_start_quarter = drive_first_play.get('period', {}).get('number') if drive_first_play else None
        drive_start_clock = drive_first_play.get('clock', {}).get('displayValue') if drive_first_play else None

        for play in drive_plays:
            text = play.get('text', '')
            text_lower = text.lower()
            event_text = final_play_text(text)
            event_text_lower = event_text.lower()
            has_replay_reversal = event_text != text
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
            if expanded and has_penalty_flag and not is_declined_only_penalty(text_lower, penalty_info):
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
                    'end_pos': _end_pos_text(play),
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
            # NOTE: NFL official stats do not count interceptions on 2-point conversion attempts
            # as turnovers because they do not create a possession change (the scoring team
            # would kick off either way).
            is_two_point_conversion_attempt = (
                'two-point' in event_text_lower
                or '2-point' in event_text_lower
                or 'conversion attempt' in event_text_lower
            )
            # Defaults used by offensive/totals yard accounting below.
            interception = False
            fumble_phrase = False
            fumble_turnover = False
            if is_two_point_conversion_attempt:
                turnover_on_play = False
            else:
                muffed_punt = 'muffed punt' in event_text_lower or 'muff' in play_type_lower
                muffed_kick = muffed_punt or ('muffed kick' in event_text_lower) or ('muffed kickoff' in event_text_lower)
                interception = 'interception' in play_type_lower or 'intercept' in event_text_lower
                if has_replay_reversal and ('intercept' not in event_text_lower and 'interception' not in event_text_lower):
                    interception = False
                fumble_phrase = 'fumble' in event_text_lower
                is_fumble_recovery_own = 'fumble recovery (own)' in play_type_lower
                is_fumble_recovery_opp = 'fumble recovery (opponent)' in play_type_lower or 'sack opp fumble recovery' in play_type_lower
                is_touchback = 'touchback' in event_text_lower

                turnover_events = []
                current_possessor = start_team_id
                current_off_abbr = offense_abbrev

                # Punt plays: once the punt is kicked ("punts ..."), the receiving team has the
                # possession context for any subsequent fumble/recovery in the same play text.
                punt_in_air = 'punts' in event_text_lower
                if punt_in_air and opponent_id and (fumble_phrase or muffed_kick):
                    current_possessor = opponent_id
                    current_off_abbr = id_to_abbr.get(opponent_id, '').lower()

                # Onside kick - if the kicking team recovers, charge the receiving team (drive team)
                # with a turnover. On kickoffs, ESPN drives typically attribute the drive to the
                # receiving team, so `team_id` represents the receiving team here.
                onside_kick = 'onside' in event_text_lower and 'kick' in event_text_lower
                kicking_team_recovered_onside = False
                if onside_kick:
                    explicit_start_team_id = play.get('start', {}).get('team', {}).get('id')
                    kicking_team_recovered_onside = (
                        end_team_id is not None
                        and end_team_id != team_id
                        and 'recovered' in event_text_lower
                        and (explicit_start_team_id is None or end_team_id == explicit_start_team_id)
                    )
                    if kicking_team_recovered_onside:
                        turnover_events.append((team_id, 'onside_kick_lost'))

                if muffed_kick and opponent_id:
                    current_possessor = opponent_id
                    current_off_abbr = id_to_abbr.get(opponent_id, '').lower()

                # Kickoff return fumbles are charged to the receiving team (opponent), even though
                # `start_team_id` is the kicking team. Without this adjustment, a successful
                # kick-coverage recovery can be misattributed as a turnover by the kicking team.
                kickoff_play = 'kickoff' in play_type_lower or 'kickoff' in event_text_lower
                if kickoff_play and fumble_phrase and opponent_id and not onside_kick and not muffed_kick:
                    current_possessor = opponent_id
                    current_off_abbr = id_to_abbr.get(opponent_id, '').lower()

                if interception:
                    turnover_events.append((current_possessor, 'interception'))
                    if opponent_id:
                        current_possessor = opponent_id
                        current_off_abbr = id_to_abbr.get(opponent_id, '').lower()

                if fumble_phrase:
                    recovered_team_id = None

                    if is_fumble_recovery_own:
                        recovered_team_id = current_possessor
                    elif is_fumble_recovery_opp and opponent_id:
                        recovered_team_id = opponent_id
                    else:
                        m = _RECOVERED_BY_ABBR_RE.search(event_text_lower)
                        if m:
                            recovered_abbr = m.group(1).lower()
                            recovered_abbr = _TEAM_ABBR_ALIASES.get(recovered_abbr, recovered_abbr)
                            recovered_team_id = abbr_to_id.get(recovered_abbr)
                            if recovered_team_id is None:
                                recovered_team_id = end_team_id
                        elif 'and recovers' in event_text_lower or 'recovers at' in event_text_lower:
                            recovered_team_id = current_possessor
                        else:
                            recovered_team_id = end_team_id

                    if recovered_team_id is not None and current_possessor is not None:
                        fumble_turnover = recovered_team_id != current_possessor
                    elif 'recovered by' in event_text_lower:
                        # Fallback when end team is missing: treat as a turnover unless it
                        # explicitly looks like an own-team recovery.
                        fumble_turnover = not (current_off_abbr and f"recovered by {current_off_abbr}" in event_text_lower)
                    elif 'and recovers' in event_text_lower or 'recovers at' in event_text_lower:
                        fumble_turnover = False

                    if is_touchback:
                        fumble_turnover = True
                if fumble_turnover and not muffed_kick:
                    turnover_events.append((current_possessor, 'fumble'))

                if muffed_kick and not kicking_team_recovered_onside:
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
                                'end_pos': _end_pos_text(play),
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
                        'end_pos': _end_pos_text(play),
                        'probability': probability_snapshot
                    })

            # Offensive stats
            is_offense, is_run, is_pass = classify_offense_play(play)
            if is_offense and (is_run or is_pass):
                stats[team_id]['Plays'] += 1
                yards = play.get('statYardage', 0)

                penalty_type_slug = (penalty_info.get('type') or {}).get('slug')
                penalty_status_slug = (penalty_info.get('status') or {}).get('slug')
                is_intentional_grounding = (
                    penalty_status_slug == 'accepted'
                    and penalty_type_slug == 'intentional-grounding'
                ) or ('intentional grounding' in text_lower)
                if is_intentional_grounding:
                    yards = 0

                if turnover_on_play:
                    yards = 0
                    if fumble_phrase and not interception:
                        credited = _credited_yards_before_fumble(event_text)
                        if credited is not None:
                            yards = credited
                elif fumble_phrase:
                    credited = _credited_yards_before_fumble(event_text)
                    if credited is not None:
                        yards = credited

                down = play.get('start', {}).get('down', 1)
                dist = play.get('start', {}).get('distance', 10)

                stats[team_id]['Offensive Yards'] += yards

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
                            'end_pos': _end_pos_text(play),
                            'probability': lookup_probability_with_delta(play)
                        })

            # Total offense (ESPN-style): include kneels/spikes, and use credited yards for fumbles.
            is_total_offense, _, _ = classify_total_offense_play(play)
            if is_total_offense:
                total_yards = play.get('statYardage', 0)

                penalty_type_slug = (penalty_info.get('type') or {}).get('slug')
                penalty_status_slug = (penalty_info.get('status') or {}).get('slug')
                is_intentional_grounding = (
                    penalty_status_slug == 'accepted'
                    and penalty_type_slug == 'intentional-grounding'
                ) or ('intentional grounding' in text_lower)
                if is_intentional_grounding:
                    total_yards = 0

                # Interceptions are 0 offensive yards by definition; fumble plays use credited gain/loss.
                if not is_two_point_conversion_attempt:
                    if interception:
                        total_yards = 0
                    elif fumble_phrase:
                        credited = _credited_yards_before_fumble(event_text)
                        if credited is not None:
                            total_yards = credited

                # Accepted penalties: derive credited offensive yards from the enforcement spot when possible.
                # This avoids counting the penalty yardage in total offense, while also protecting against
                # ESPN payloads where statYardage is inconsistent with the described enforcement.
                penalty_status_slug = (penalty_info.get('status') or {}).get('slug')
                start_yte = (play.get('start') or {}).get('yardsToEndzone')
                if (
                    penalty_status_slug == 'accepted'
                    and isinstance(start_yte, (int, float))
                    and 'no play' not in event_text_lower
                    and not interception
                    and not fumble_phrase
                ):
                    start_team_id = ((play.get('start') or {}).get('team') or {}).get('id')
                    end_team_id = ((play.get('end') or {}).get('team') or {}).get('id')
                    if start_team_id is None or end_team_id is None or start_team_id == end_team_id:
                        enforced_yte = _enforced_at_yards_to_endzone(event_text, offense_abbrev)
                        if enforced_yte is not None:
                            credited = int(start_yte - enforced_yte)
                            if isinstance(total_yards, (int, float)):
                                total_yards_int = int(total_yards)
                            else:
                                total_yards_int = total_yards
                            if credited is not None and credited != total_yards_int:
                                if expanded and team_id in details:
                                    details[team_id]['Total Yards Corrections'].append({
                                        'type': play_type,
                                        'text': text,
                                        'quarter': play.get('period', {}).get('number'),
                                        'clock': play.get('clock', {}).get('displayValue'),
                                        'statYardage': total_yards_int,
                                        'startYardsToEndzone': start_yte,
                                        'penaltyYards': (penalty_info or {}).get('yards'),
                                        'enforcedAtYardsToEndzone': enforced_yte,
                                        'correctedYards': credited,
                                        'reason': 'accepted_penalty_enforcement_spot',
                                    })
                                total_yards = credited

                stats[team_id]['Total Yards'] += total_yards

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

            # Collect all meaningful plays for "All Plays" category
            if expanded:
                is_meaningful = (
                    (is_offense and (is_run or is_pass)) or  # Offensive play
                    play.get('scoringPlay') or               # Scoring play
                    turnover_on_play or                      # Turnover
                    has_penalty_flag                         # Penalty
                )
                if is_meaningful:
                    play_entry = {
                        'type': play_type,
                        'text': text,
                        'yards': play.get('statYardage', 0),
                        'quarter': play.get('period', {}).get('number'),
                        'clock': play.get('clock', {}).get('displayValue'),
                        'end_pos': _end_pos_text(play),
                        'probability': probability_snapshot,
                    }
                    # Add points if scoring play
                    if play.get('scoringPlay') and play_id in scoring_map:
                        play_entry['points'] = scoring_map[play_id].get('points', 0)
                    details[team_id]['All Plays'].append(play_entry)

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
            if expanded and drive_start_yte != -1:
                start_pos = drive_start_pos_text
                if not start_pos and isinstance(drive_start_yte, (int, float)):
                    start_pos = f"Own {int(100 - drive_start_yte)}"

                cause_play = None
                if drive_first_play and _is_kick_or_punt_start(drive_first_play):
                    cause_play = drive_first_play
                elif drive_index > 0:
                    prev_drive = drives[drive_index - 1] or {}
                    prev_plays = prev_drive.get('plays', []) or []
                    for cand in reversed(prev_plays):
                        if not _is_drive_boundary_noise(cand):
                            cause_play = cand
                            break

                details[team_id]['Drive Starts'].append({
                    'text': (cause_play.get('text', '') if cause_play else 'Start of game'),
                    'type': (cause_play.get('type', {}) or {}).get('text', 'Drive Start') if cause_play else 'Drive Start',
                    'yards': (cause_play.get('statYardage') if cause_play else None),
                    'quarter': drive_start_quarter,
                    'clock': drive_start_clock,
                    'start_pos': start_pos,
                    'end_pos': start_pos,
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
            'Yards Per Play': round(d['Offensive Yards'] / plays, 2),
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
