"""
NFL Game Analysis Core Module

Shared pure analytics functions used by both CLI (game_compare.py) and API (game_analysis.py).
No I/O or HTTP dependencies - just data transformation logic.
"""

import math
import re
from dataclasses import dataclass


# ESPN replay notes are inconsistent about punctuation/spacing:
# e.g. "play was REVERSED.(Shotgun) ..." or "play was REVERSED (Shotgun) ..."
_REPLAY_DECISION_RE = re.compile(r"\b(?:reversed|overturned)\b[.:]?\s*", re.IGNORECASE)
_YARDS_FOR_RE = re.compile(r"\bfor (-?\d+) yards?\b", re.IGNORECASE)
_PUNT_DISTANCE_RE = re.compile(r"\bpunts?\s+(\d+)\s+yards?\b", re.IGNORECASE)
_YARDS_LOSS_RE = re.compile(r"\bfor loss of (\d+) yards?\b", re.IGNORECASE)
_RECOVERED_BY_ABBR_RE = re.compile(r"\brecovered by\s+([a-z]{2,4})\b", re.IGNORECASE)
_FUMBLE_RE = re.compile(r"\bfumbles?\b", re.IGNORECASE)
_MUFF_RE = re.compile(r"\bmuffs?\b|\bmuffed\b", re.IGNORECASE)
_TEAM_ABBR_ALIASES = {
    # ESPN play text can use older abbreviations than the boxscore/team metadata.
    "arz": "ari",
    "blt": "bal",
    "clv": "cle",
    "hst": "hou",
    "la": "lar",
    "was": "wsh",
    "jac": "jax",
}
_PENALTY_ON_TEAM_RE = re.compile(r'\bpenalty on\s+([a-z]{2,4})(?=[\s,.-])', re.IGNORECASE)
_KICKOFF_PLACEMENT_TYPES = {'kickoff-out-of-bounds', 'kickoff-short-of-landing-zone'}
_PLACED_AT_RE = re.compile(r'\bplaced at\s+([a-z]{2,4}\s+\d+|midfield|50)\b', re.IGNORECASE)


def _canonical_team_abbr(abbr):
    normalized = str(abbr or '').lower()
    return _TEAM_ABBR_ALIASES.get(normalized, normalized)


def normalize_position_text(pos_text, known_abbrs):
    """Use a game's box-score abbreviations for a structured yard-line label.

    Unknown team tokens have no safe own/opponent interpretation. Keep the raw
    play description elsewhere, but omit that derived position label.
    """
    if not isinstance(pos_text, str):
        return pos_text
    match = re.fullmatch(r'\s*([a-z]{2,4})\s+(\d{1,2})\s*', pos_text, re.IGNORECASE)
    if not match:
        return pos_text
    abbr = known_abbrs.get(_canonical_team_abbr(match.group(1)))
    return f'{abbr} {match.group(2)}' if abbr else None


def boxscore_abbreviations_by_id(game_data):
    """Use ESPN's stable team IDs to align headers with box-score stat rows."""
    return {
        str(team['team']['id']): team['team']['abbreviation']
        for team in (game_data.get('boxscore') or {}).get('teams', [])
        if (team.get('team') or {}).get('id') and (team.get('team') or {}).get('abbreviation')
    }


def _penalty_team_id(penalty_info, text, abbr_to_id, opponent_id):
    team_id = (penalty_info.get('team') or {}).get('id')
    if team_id:
        return team_id
    match = _PENALTY_ON_TEAM_RE.search(text or '')
    if match:
        return abbr_to_id.get(_canonical_team_abbr(match.group(1)))
    if 'on defense' in (text or '').lower():
        return opponent_id
    return None


def _charged_penalty_yards(penalty_info, play):
    """Return charged yards and a note; placement distance is not penalty yardage."""
    yards = penalty_info.get('yards')
    if isinstance(yards, (int, float)) and math.isfinite(yards):
        return abs(int(yards)), None
    # ESPN can omit structured yardage even when the accepted foul explicitly
    # says "0 yards". Match that foul's type so a later declined foul cannot
    # supply the value for the accepted one.
    penalty_type_text = (penalty_info.get('type') or {}).get('text')
    if (penalty_type_text
            and (penalty_info.get('status') or {}).get('slug') == 'accepted'):
        accepted_zero = re.search(
            r'\bPENALTY on [^,]+,\s*' + re.escape(penalty_type_text) + r',\s*0 yards?\b',
            play.get('text') or '', re.IGNORECASE,
        )
        if accepted_zero:
            return 0, '0 penalty yards stated in ESPN play text'
    penalty_type = (penalty_info.get('type') or {}).get('slug')
    play_type = ((play.get('type') or {}).get('text') or '').lower()
    placement = _PLACED_AT_RE.search(play.get('text') or '')
    if (penalty_type in _KICKOFF_PLACEMENT_TYPES
            and 'kickoff' in play_type and placement):
        return 0, f"0 penalty yards charged; ball placed at {placement.group(1).upper()}"
    return None, 'Penalty yards unavailable'


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

    prefix, aftermath = lower.split('fumble', 1)
    # If the original ball carrier recovers their own lone fumble, all of the
    # final yardage belongs to the initiating run/pass (NFL scoring rule).
    # ESPN's final statYardage is preferable to the pre-fumble fragment here.
    if 'and recovers' in aftermath and not _FUMBLE_RE.search(aftermath):
        return None

    matches = list(_YARDS_FOR_RE.finditer(prefix))
    if matches:
        try:
            if 'lateral' in prefix and len(matches) > 1:
                return sum(int(match.group(1)) for match in matches)
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


def _forward_pass_after_fumble(event_text):
    lower = event_text.lower()
    index = lower.find('fumble')
    if index < 0:
        return False
    aftermath = lower[index:]
    for terminator in ('penalty', 'touchdown', 'two-point conversion attempt'):
        aftermath = aftermath.split(terminator, 1)[0]
    return re.search(r"\b[a-z]{1,3}\.[a-z'-]+\s+pass\b", aftermath) is not None


def _credit_fumble_loose_ball_spot(credited, event_text, play, offense_abbrev):
    """Credit fumble-play yards using the first touch or recovery spot."""
    if not isinstance(credited, (int, float)) or not event_text:
        return credited
    fumble_index = event_text.lower().find('fumble')
    if fumble_index < 0:
        return credited
    # On a sack-fumble, a teammate's advance back through the line of
    # scrimmage cancels the passer's sack loss; the later advance is fumble
    # yardage, not passing yardage.
    passer = re.search(r"\b([A-Za-z]{1,3}\.[A-Za-z'-]+)\s+sacked\b",
                       event_text[:fumble_index], re.IGNORECASE)
    recovery = re.search(r"\brecovered by\s+([A-Za-z]{2,4})-([A-Za-z]{1,3}\.[A-Za-z'-]+)\b",
                         event_text[fumble_index:], re.IGNORECASE)
    start = play.get('start') or {}
    end = play.get('end') or {}
    start_yte = start.get('yardsToEndzone')
    start_coord = (100 - start_yte) if isinstance(start_yte, (int, float)) else None
    if passer:
        sack = re.search(r'\bsacked at\s+([A-Z]{2,4})\s+(-?\d{1,2})\s+for\s+(-?\d+)\s+yards?\b',
                         event_text[:fumble_index], re.IGNORECASE)
        if sack:
            sack_coord = yardline_to_coord(f'{sack.group(1)} {sack.group(2)}', offense_abbrev)
            if sack_coord is not None:
                inferred_start = sack_coord - int(sack.group(3))
                if 0 <= inferred_start <= 100:
                    # ESPN occasionally reports an impossible start spot on a
                    # sack-fumble; the stated sack spot and loss reconstruct it.
                    start_coord = inferred_start
    aftermath = event_text[fumble_index:]
    # Later recoveries/fumbles are separate advances. The initiating pass or
    # rush is credited only through the first fumble's touch/recovery spot.
    next_fumble = _FUMBLE_RE.search(aftermath, 1)
    first_aftermath = aftermath[:next_fumble.start()] if next_fumble else aftermath

    def fumble_spot_coord(spot):
        position = spot.group(1).upper()
        return 50 if position in ('50', 'MIDFIELD') else yardline_to_coord(
            position, offense_abbrev
        )
    later_sack = re.search(
        r'\bsacked at\s+[A-Z]{2,4}\s+-?\d{1,2}\s+for\s+(-?\d+)\s+yards?\b',
        aftermath, re.IGNORECASE
    )
    if later_sack:
        later_fumble = _FUMBLE_RE.search(aftermath, later_sack.end())
        if later_fumble and start_coord is not None:
            later_touch = re.search(
                r'\btouched at\s+([A-Z]{2,4})\s+(-?\d{1,2})\b',
                aftermath[later_fumble.start():], re.IGNORECASE
            )
            if later_touch:
                touch_coord = yardline_to_coord(
                    f'{later_touch.group(1)} {later_touch.group(2)}', offense_abbrev
                )
                if touch_coord is not None and 0 <= touch_coord <= 100:
                    return min(touch_coord - start_coord, 0)
        return int(later_sack.group(1))
    first_touch = re.search(
        r'\btouched at\s+((?:[A-Z]{2,4}\s+)?-?\d{1,2}|midfield)\b',
        first_aftermath, re.IGNORECASE
    )
    if passer and first_touch and start_coord is not None:
        touch_coord = fumble_spot_coord(first_touch)
        if touch_coord is not None and 0 <= touch_coord <= 100:
            return min(touch_coord - start_coord, 0)
    if (passer and recovery
            and passer.group(1).lower() != recovery.group(2).lower()
            and _canonical_team_abbr(recovery.group(1)) == _canonical_team_abbr(offense_abbrev)
            and (start.get('team') or {}).get('id') == (end.get('team') or {}).get('id')
            and start_coord is not None
            and isinstance(end.get('yardsToEndzone'), (int, float))):
        # A teammate's advance after the recovery determines the final sack
        # loss, even if the ball never gets all the way back to scrimmage.
        return min((100 - end['yardsToEndzone']) - start_coord, 0)
    spot = first_touch
    if not spot:
        spot = re.search(
            r'\brecovered by\b.*?\bat\s+((?:[A-Z]{2,4}\s+)?-?\d{1,2}|midfield)\b',
            first_aftermath, re.IGNORECASE
        )
    if not spot:
        spot = re.search(
            r'\bball out of bounds at\s+((?:[A-Z]{2,4}\s+)?-?\d{1,2}|midfield)\b',
            first_aftermath, re.IGNORECASE
        )
    if not spot:
        return credited
    if start_coord is None:
        return credited
    spot_coord = fumble_spot_coord(spot)
    if passer and spot_coord is not None and spot_coord < 0 and start_coord >= 0:
        # Statistical sack loss ends at the offense's goal line, not beyond it.
        return -start_coord
    if spot_coord is None or not 0 <= spot_coord <= 100:
        return credited
    spot_gain = spot_coord - start_coord
    # Sack yardage follows a teammate/opponent recovery back toward the line
    # of scrimmage as well as away from it. A recovery beyond the line is a
    # zero-yard sack, not positive passing yardage.
    if passer:
        return min(spot_gain, 0)
    if credited < 0 and spot_gain > credited and 'recovered by' in aftermath.lower():
        # A rushing fumble behind scrimmage that comes back toward the line
        # reduces the runner's loss, stopping at zero rushing yards.
        return min(spot_gain, 0)
    return min(credited, spot_gain)


def _is_credited_nullified_touchdown(play):
    """A nullified score can still retain yards gained before a downfield foul."""
    text = (play.get('text') or '').lower()
    penalty = play.get('penalty') or {}
    start_yte = (play.get('start') or {}).get('yardsToEndzone')
    end_yte = (play.get('end') or {}).get('yardsToEndzone')
    penalty_yards = penalty.get('yards')
    return (
        'touchdown nullified' in text
        and 'no play' not in text
        and (penalty.get('status') or {}).get('slug') == 'accepted'
        and 'enforced at ' in text
        and isinstance(start_yte, (int, float))
        and isinstance(end_yte, (int, float))
        and isinstance(penalty_yards, (int, float))
        and start_yte > end_yte - penalty_yards
    )


def _credited_yards_on_accepted_penalty(play, event_text, offense_abbrev, default):
    """Separate a completed play's yards from its accepted penalty yards."""
    penalty = play.get('penalty') or {}
    if (penalty.get('status') or {}).get('slug') != 'accepted':
        return default
    lower = event_text.lower()
    if 'no play' in lower:
        return default
    start = play.get('start') or {}
    end = play.get('end') or {}
    start_yte = start.get('yardsToEndzone')
    end_yte = end.get('yardsToEndzone')
    if not isinstance(start_yte, (int, float)):
        return default
    if ('enforced between downs' in lower and 'touchdown' in lower
            and isinstance(end_yte, (int, float))):
        return int(start_yte - end_yte)
    enforced_yte = _enforced_at_yards_to_endzone(event_text, offense_abbrev)
    if enforced_yte is None:
        return default
    return int(start_yte - enforced_yte)


def _aborted_snap_rushing_yards(event_text, yards, play, offense_abbrev):
    """Exclude an opponent's return, but retain ESPN's own-team advances."""
    handler = re.search(
        r"\b([A-Za-z]{1,3}\.[A-Za-z'-]+)\s+aborted\.", event_text, re.IGNORECASE
    )
    fumbler = re.search(
        r"\b([A-Za-z]{1,3}\.[A-Za-z'-]+)\s+fumbles\b", event_text, re.IGNORECASE
    )
    recovering_player = re.search(
        r"\brecovered by\s+[A-Z]{2,4}-([A-Za-z]{1,3}\.[A-Za-z'-]+)\b",
        event_text, re.IGNORECASE
    )
    if (handler and fumbler and recovering_player
            and handler.group(1).lower() != fumbler.group(1).lower()
            and handler.group(1).lower() != recovering_player.group(1).lower()):
        # A botched center-to-handler exchange recovered by a third teammate
        # is a zero-yard rush; his advance is separate fumble yardage.
        return 0
    recovery = _RECOVERED_BY_ABBR_RE.search(event_text)
    if recovery and _canonical_team_abbr(recovery.group(1)) != _canonical_team_abbr(offense_abbrev):
        return 0
    start_team = ((play.get('start') or {}).get('team') or {}).get('id')
    end_team = ((play.get('end') or {}).get('team') or {}).get('id')
    if start_team and end_team and start_team != end_team:
        return 0
    return max(yards, 0)


def _is_score_only_fumble_return(play):
    """Recognize ESPN's terse scoring stub, not the underlying offensive play."""
    play_type = ((play.get('type') or {}).get('text') or '').lower()
    text = (play.get('text') or '').lower()
    return (
        'fumble' in play_type
        and re.search(r'\b\d+\s+yd\s+fumble\s+(?:return|recovery)\b', text) is not None
        and re.search(r'\b(?:pass|sacked|rush|punts|kicks|scrambles)\b', text) is None
    )


def _is_nonoffensive_return(play):
    play_type = ((play.get('type') or {}).get('text') or '').lower()
    return _is_score_only_fumble_return(play) or (
        'touchdown' in play_type
        and any(kind in play_type for kind in (
            'blocked field goal', 'blocked punt', 'kickoff return',
            'punt return',
        ))
    )


def classify_total_offense_play(play):
    """
    Classify plays for ESPN-style total offense (Total Yards) reconciliation.

    Compared to `classify_offense_play`, this includes kneels/spikes as offense plays.
    """
    text_lower = play.get('text', '').lower()
    type_lower = play.get('type', {}).get('text', 'unknown').lower()
    aborted_snap = 'aborted' in text_lower and 'fumble' in text_lower

    if _is_nonoffensive_return(play):
        return False, False, False
    if is_nullified_play(text_lower) and not _is_credited_nullified_touchdown(play):
        return False, False, False
    if is_penalty_play(play, text_lower, type_lower):
        return False, False, False
    if not aborted_snap and is_special_teams_play(text_lower, type_lower):
        return False, False, False

    # Kickoff/punt returns are special teams plays, not offensive plays.
    if ('kickoff' in text_lower or 'kickoff' in type_lower) and 'return' in type_lower:
        return False, False, False
    if ('punt' in text_lower or 'punt' in type_lower) and 'return' in type_lower:
        return False, False, False

    # Spikes/kneels should count toward total offense.
    if is_spike_or_kneel(text_lower, type_lower):
        return True, 'kneel' in text_lower or 'kneel' in type_lower, 'spike' in text_lower or 'spike' in type_lower

    # All other offensive snaps follow the adjusted classifier. In particular,
    # feed markers such as End Period and Two-Minute Warning are not snaps.
    _, is_run, is_pass = classify_offense_play(play)
    return is_run or is_pass, is_run, is_pass


_ENFORCED_AT_SPOT_RE = re.compile(r'\benforced at(?: the)?\s+([A-Z]{2,3})\s+(\d{1,2})\b', re.IGNORECASE)


def _enforced_at_yards_to_endzone(event_text, offense_abbrev):
    """
    Parse 'enforced at XXX NN' and convert to yardsToEndzone (relative to the offense).

    This lets us derive the offensive yards credited on accepted-penalty plays without
    incorporating the penalty yardage into Total Yards.
    """
    if not event_text or not offense_abbrev:
        return None
    if re.search(r'\benforced at(?: the)?\s+(?:50|midfield)\b', event_text, re.IGNORECASE):
        return 50
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

    return (100 - yard) if _canonical_team_abbr(side) == _canonical_team_abbr(offense_abbrev) else yard


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
    if _canonical_team_abbr(side) == _canonical_team_abbr(team_abbr):
        return yard
    return 100 - yard


def format_field_position(own_goal_distance):
    """Display a 0-100 field coordinate using the nearest team's goal line."""
    yard = int(own_goal_distance)
    return f"Opp {100 - yard}" if yard > 50 else f"Own {yard}"


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
    return bool(re.search(r'\b(?:spikes?|spiked|kneels?|kneeled)\b',
                          f'{type_lower} {text_lower}'))


def is_special_teams_play(text_lower, type_lower):
    """
    Identify special teams plays (punts, kickoffs, FGs, XPs).
    A special-teams return remains special teams even when it scores.
    """
    text_lower = (text_lower or '').lower()
    type_lower = (type_lower or '').lower()
    # A fake-kick snap can be filed as a fumble recovery even though its
    # actual offensive action was an incomplete pass or a sack. Formation
    # alone does not make that snap a punt or field-goal attempt.
    if ('fumble recovery' in type_lower
            and ('punt formation' in text_lower or 'field goal formation' in text_lower)
            and re.search(r'\b(?:pass|sacked)\b', text_lower)
            and not re.search(r'\b(?:punts|kicks|kickoff)\b', text_lower)):
        return False
    st_keywords = ['punt', 'kickoff', 'field goal', 'extra point', 'xp', 'fg', 'onside']
    if any(k in type_lower for k in st_keywords):
        return True
    # ESPN describes fake punts in the play text as "Punt formation", while
    # classifying the actual snap as a pass or rush. The play type wins.
    if re.search(r'\b(pass|passing|rush|rushing|run|sack)\b', type_lower):
        return False
    if 'touchdown' in text_lower or 'touchdown' in type_lower:
        return False
    return any(k in text_lower for k in st_keywords)


def is_nullified_play(text_lower):
    """Detect plays that didn't happen (nullified, no play)."""
    # A return touchdown can be nullified by a post-turnover penalty while the
    # underlying interception/fumble still counts. An offensive touchdown
    # nullified by a penalty does not earn offensive yards.
    without_nullified_score = re.sub(r'\btouchdown\s+nullified\b', '', text_lower)
    if 'nullified' in without_nullified_score or 'no play' in text_lower:
        return True
    match = re.search(r'\btouchdown\s+nullified\b', text_lower)
    if match:
        preceding_play = text_lower[:match.start()]
        return 'intercept' not in preceding_play and 'fumble' not in preceding_play
    return False


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
    aborted_snap = 'aborted' in text_lower and 'fumble' in text_lower

    if _is_nonoffensive_return(play):
        return False, False, False
    if is_nullified_play(text_lower) and not _is_credited_nullified_touchdown(play):
        return False, False, False
    if is_penalty_play(play, text_lower, type_lower):
        return False, False, False
    if is_spike_or_kneel(text_lower, type_lower):
        return False, False, False
    if not aborted_snap and is_special_teams_play(text_lower, type_lower):
        return False, False, False

    # Kickoff/punt return TDs are special teams plays, not offensive plays
    if ('kickoff' in text_lower or 'kickoff' in type_lower) and 'return' in type_lower:
        return False, False, False
    if ('punt' in text_lower or 'punt' in type_lower) and 'return' in type_lower:
        return False, False, False

    pass_hint = (any_stat_contains(play, ['pass', 'sack']) or
                 'pass' in type_lower or 'sack' in type_lower or
                 'interception' in type_lower or
                 'scramble' in type_lower or 'pass' in text_lower or
                 'sack' in text_lower or 'scramble' in text_lower)

    # Detect rushing plays - include common rush direction phrases
    rush_patterns = ['up the middle', 'left end', 'right end', 'left tackle',
                     'right tackle', 'left guard', 'right guard', 'middle for',
                     'around left', 'around right']
    fumble_origin = text_lower.split('fumble', 1)[0]
    fumble_rush = (
        'fumble recovery' in type_lower
        and not pass_hint
        and re.search(
            r"\b[a-z]{1,3}\.[a-z'-]+\s+to\s+(?:[a-z]{2,4}\s+-?\d{1,2}|midfield)\s+for\s+-?\d+\s+yards?\b",
            fumble_origin,
        ) is not None
    )
    rush_hint = (aborted_snap or fumble_rush or any_stat_contains(play, ['rush']) or 'rush' in type_lower or
                 re.search(r'\b(?:run|runs|ran)\b', text_lower) is not None or
                 any(p in text_lower for p in rush_patterns))

    # Captions may mention a runner, a defender whose name contains "run", or
    # a two-point rush appended after a passing touchdown. Classify the
    # underlying snap from its play type before using those text hints.
    if pass_hint and rush_hint:
        if ('scramble' in text_lower or 'scramble' in type_lower
                or any(word in type_lower for word in ('pass', 'sack', 'interception'))):
            rush_hint = False
        elif 'rush' in type_lower:
            pass_hint = False
        elif re.search(r'\b(?:pass|sacked|scrambles?)\b', fumble_origin):
            rush_hint = False

    return True, rush_hint, pass_hint


@dataclass(frozen=True)
class OffensivePlayContribution:
    """One snap's offensive contribution, before team/window aggregation.

    The play may also contain a defensive return, score, or turnover. Those
    events do not erase its offensive pass/rush attempt. Total offense and the
    selected adjusted metric have distinct inclusion rules but share yard
    crediting below.
    """

    adjusted_play: bool
    total_offense_play: bool
    total_yards_only: bool
    run: bool
    pass_dropback: bool
    adjusted_yards: int | float
    total_yards: int | float
    total_yards_before_penalty: int | float


def _build_offensive_play_contribution(
    play, *, event_text, offense_abbrev, penalty_info, turnover_on_play,
    interception, fumble_phrase, is_incomplete_pass, aborted_snap,
    is_two_point_conversion_attempt,
):
    """Normalize classification and credited yards once for both metrics."""
    is_offense, is_run, is_pass = classify_offense_play(play)
    is_total_offense, _, _ = classify_total_offense_play(play)
    adjusted_play = is_offense and (is_run or is_pass)
    play_type = ((play.get('type') or {}).get('text') or '').lower()
    # ESPN occasionally replaces a sack/run with a score-only Safety caption
    # while retaining its credited statYardage. Credit the known yards, but do
    # not pretend the missing pass/rush detail is available for play metrics.
    total_yards_only = (
        not is_total_offense and 'safety' in play_type
        and isinstance(play.get('statYardage'), (int, float))
        and play['statYardage'] != 0
    )

    source_yards = play.get('statYardage', 0)
    adjusted_yards = 0 if turnover_on_play else source_yards
    total_yards = source_yards
    event_lower = event_text.lower()
    penalty_type = (penalty_info.get('type') or {}).get('slug')
    penalty_status = (penalty_info.get('status') or {}).get('slug')
    intentional_grounding = (
        penalty_status == 'accepted' and penalty_type == 'intentional-grounding'
    ) or 'intentional grounding' in event_lower
    if intentional_grounding or is_incomplete_pass:
        adjusted_yards = 0
        total_yards = 0
    if interception and not is_two_point_conversion_attempt:
        total_yards = 0

    if fumble_phrase and not _forward_pass_after_fumble(event_text):
        credited = _credited_yards_before_fumble(event_text)
        if credited is not None:
            credited = _credit_fumble_loose_ball_spot(
                credited, event_text, play, offense_abbrev
            )
            if not interception:
                adjusted_yards = credited
                if not is_two_point_conversion_attempt:
                    total_yards = credited
    if is_incomplete_pass:
        adjusted_yards = 0
        total_yards = 0
    if aborted_snap:
        adjusted_yards = _aborted_snap_rushing_yards(
            event_text, adjusted_yards, play, offense_abbrev
        )
        total_yards = _aborted_snap_rushing_yards(
            event_text, total_yards, play, offense_abbrev
        )

    total_before_penalty = total_yards
    if (not interception and not is_incomplete_pass
            and (not fumble_phrase or _is_credited_nullified_touchdown(play))):
        adjusted_yards = _credited_yards_on_accepted_penalty(
            play, event_text, offense_abbrev, adjusted_yards
        )
        start_team = ((play.get('start') or {}).get('team') or {}).get('id')
        end_team = ((play.get('end') or {}).get('team') or {}).get('id')
        if start_team is None or end_team is None or start_team == end_team:
            total_yards = _credited_yards_on_accepted_penalty(
                play, event_text, offense_abbrev, total_yards
            )

    return OffensivePlayContribution(
        adjusted_play=adjusted_play,
        total_offense_play=is_total_offense,
        total_yards_only=total_yards_only,
        run=is_run,
        pass_dropback=is_pass,
        adjusted_yards=adjusted_yards,
        total_yards=total_yards,
        total_yards_before_penalty=total_before_penalty,
    )


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
    if wp_threshold >= 1.0:
        return True

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


def _split_drives_on_possession_change(drives):
    """ESPN sometimes keeps plays after a turnover in the former team's drive."""
    normalized = []

    def is_boundary_noise(play):
        play_type = ((play.get('type') or {}).get('text') or '').lower()
        text = (play.get('text') or '').lower()
        return ('timeout' in play_type or 'end of' in play_type
                or 'end of' in text)

    for drive in drives:
        original_team = (drive.get('team') or {}).get('id')
        plays = drive.get('plays') or []
        if not original_team or not plays:
            normalized.append(drive)
            continue

        segment_team = original_team
        segment_start = drive.get('start') or {}
        segment_plays = []

        def append_segment():
            # ESPN often appends the next team's Official Timeout to the end
            # of the previous drive. Splitting that marker creates a fake
            # one-play drive before the actual next drive record.
            if segment_plays and any(not is_boundary_noise(play) for play in segment_plays):
                normalized.append({
                    **drive,
                    'team': {'id': segment_team},
                    'start': segment_start,
                    'plays': segment_plays,
                })

        for play in plays:
            start = play.get('start') or {}
            play_team = (start.get('team') or {}).get('id')
            play_type = ((play.get('type') or {}).get('text') or '').lower()
            special_teams = any(keyword in play_type for keyword in
                                ('kickoff', 'punt', 'field goal', 'extra point', 'onside'))
            if (play_team and play_team != segment_team
                    and start.get('down') in (1, 2, 3, 4) and not special_teams):
                if segment_plays:
                    append_segment()
                segment_team = play_team
                segment_start = {**start, 'text': start.get('possessionText')}
                segment_plays = []
            segment_plays.append(play)
        append_segment()

    return normalized


def process_game_stats(game_data, expanded=False, probability_map=None,
                       pregame_probabilities=None, wp_threshold=0.975,
                       debug_rows=None, debug_threshold=0.975,
                       penalty_yards_from_plays=False):
    """
    Process game data and return stats as dict rows (not DataFrame).
    Returns (stats_rows, details) where stats_rows is a list of dicts.
    """
    boxscore = game_data.get('boxscore', {})
    teams_info = boxscore.get('teams', [])
    id_to_abbr = {}
    probability_map = probability_map or {}
    drives = _split_drives_on_possession_change(game_data.get('drives', {}).get('previous', []))

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
    abbr_to_id = {_canonical_team_abbr(abbr): tid for tid, abbr in id_to_abbr.items()}
    display_abbrs = {_canonical_team_abbr(abbr): abbr for abbr in id_to_abbr.values()}

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
            'Total Offensive Plays': 0,
            'Offensive Yards': 0,
            'Official Yards Per Play (Full Game)': None,
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
            'Kickoff Opponent Start Sum': 0,
            'Kickoff Count': 0,
            'ST Penalties': 0,
            'Penalty Yards': 0,
            'Penalty Count': 0,
            'Non-Offensive Points': 0
        }
        if expanded:
            details[t_id] = {
                'All Plays': [],
                'Offensive Plays': [],
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

    # Official full-game yards per play and penalty totals from ESPN's boxscore.
    for t in teams_info:
        t_id = t.get('team', {}).get('id')
        if not t_id or t_id not in stats:
            continue
        team_stats = t.get('statistics', [])
        for stat in team_stats:
            stat_name = stat.get('name', '')
            if stat_name == 'yardsPerPlay':
                for raw_value in (stat.get('displayValue'), stat.get('value')):
                    try:
                        parsed = float(raw_value)
                        if math.isfinite(parsed):
                            stats[t_id]['Official Yards Per Play (Full Game)'] = parsed
                            break
                    except (TypeError, ValueError):
                        continue
            if stat_name == 'totalPenaltiesYards' and not penalty_yards_from_plays:
                display_val = stat.get('displayValue', '')
                if isinstance(display_val, str) and '-' in display_val:
                    parts = display_val.split('-')
                    if len(parts) == 2:
                        try:
                            stats[t_id]['Penalty Count'] = int(parts[0])
                            stats[t_id]['Penalty Yards'] = int(parts[1])
                        except ValueError:
                            pass

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
                    'source_play_id': str(play_id),
                    'type': sp.get('type', {}).get('text', ''),
                    'text': sp.get('text', ''),
                    'points': points,
                    'quarter': sp.get('period', {}).get('number'),
                    'clock': sp.get('clock', {}).get('displayValue'),
                })

    # Debug rows are collected inside the same calculation loop, so their
    # contributions reflect the actual rules rather than a second approximation.
    def stat_snapshot():
        if debug_rows is None:
            return None
        return {
            tid: {key: value for key, value in values.items()
                  if isinstance(value, (int, float))}
            for tid, values in stats.items()
        }

    def stat_delta(before):
        if before is None:
            return {}
        return {
            id_to_abbr.get(tid, tid): changes
            for tid, values in stats.items()
            if (changes := {
                key: value - before[tid].get(key, 0)
                for key, value in values.items()
                if isinstance(value, (int, float)) and value != before[tid].get(key)
            })
        }

    def record_debug_play(play, drive_index, team_id, before, excluded_reason,
                          start_home_wp, start_away_wp):
        if debug_rows is None:
            return
        _, is_run, is_pass = classify_offense_play(play)
        pid = play.get('id')
        end_wp = probability_map.get(str(pid)) if pid is not None else None
        debug_rows.append({
            'kind': 'play',
            'drive': drive_index + 1,
            'playId': pid,
            'team': id_to_abbr.get(team_id, team_id),
            'quarter': (play.get('period') or {}).get('number'),
            'clock': (play.get('clock') or {}).get('displayValue'),
            'type': (play.get('type') or {}).get('text'),
            'text': play.get('text'),
            'down': (play.get('start') or {}).get('down'),
            'distance': (play.get('start') or {}).get('distance'),
            'sourceYards': play.get('statYardage'),
            'classification': 'run' if is_run else 'pass' if is_pass else 'other',
            'competitive': is_competitive_play(
                play, probability_map, debug_threshold, start_home_wp, start_away_wp
            ),
            'excludedReason': excluded_reason,
            'startHomeWP': start_home_wp,
            'endHomeWP': end_wp.get('homeWinPercentage') if end_wp else None,
            'statDeltas': stat_delta(before),
            'raw': play,
        })

    # Process drives and plays
    def _end_pos_text(play_obj):
        end = (play_obj.get('end') or {}) if isinstance(play_obj, dict) else {}
        if not isinstance(end, dict):
            return None
        pos_text = end.get('possessionText')
        if isinstance(pos_text, str) and pos_text.strip():
            return normalize_position_text(pos_text.strip(), display_abbrs)
        down_dist = end.get('downDistanceText')
        if isinstance(down_dist, str):
            m = re.search(r"\bat\s+([A-Z]{2,3}\s+\d+)\b", down_dist)
            if m:
                return normalize_position_text(m.group(1), display_abbrs)
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
        # ESPN's kickoff/punt play coordinates describe the kicking team. The
        # drive start is the receiving offense's field position, so prefer its
        # drive-level yard line when available.
        drive_start = drive.get('start', {}) or {}
        drive_start_yard_line = drive_start.get('text') or drive_start.get('yardLine')
        if isinstance(drive_start_yard_line, str):
            drive_start_coord = yardline_to_coord(drive_start_yard_line, id_to_abbr.get(team_id))
            if drive_start_coord is not None:
                drive_start_yte = 100 - drive_start_coord
        drive_start_pos_text = (drive.get('start', {}) or {}).get('text')
        if not isinstance(drive_start_pos_text, str) or not drive_start_pos_text.strip():
            drive_start_pos_text = (drive.get('start', {}) or {}).get('yardLine')
        if not isinstance(drive_start_pos_text, str) or not drive_start_pos_text.strip():
            drive_start_pos_text = None
        if drive_start_pos_text:
            drive_start_pos_text = normalize_position_text(drive_start_pos_text, display_abbrs)
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
            debug_before = stat_snapshot()
            debug_start_home_wp = prev_home_wp
            debug_start_away_wp = prev_away_wp
            text = play.get('text', '')
            text_lower = text.lower()
            event_text = final_play_text(text)
            event_text_lower = event_text.lower()
            aborted_snap = 'aborted' in event_text_lower and 'fumble' in event_text_lower
            has_replay_reversal = event_text != text
            play_type = play.get('type', {}).get('text', 'Unknown')
            play_type_lower = play_type.lower()
            is_incomplete_pass = (
                'pass incompletion' in play_type_lower
                or ('pass incomplete' in event_text_lower
                    and 'sacked' not in event_text_lower
                    and 'rush' not in play_type_lower)
            )
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
                start_yte = drive_start_yte
                if start_yte == -1:
                    start_yte = play.get('start', {}).get('yardsToEndzone', -1)
                if start_yte != -1:
                    drive_start_yte = start_yte
                if drive_started_competitive and start_yte != -1:
                    start_loc = 100 - start_yte
                    stats[team_id]['Start Field Pos Sum'] += start_loc
                    stats[team_id]['Drives Count'] += 1

            # Handle penalty plays for expanded details
            penalty_info = play.get('penalty') or {}
            has_penalty_flag = bool(penalty_info) or play.get('hasPenalty') or 'penalty' in text_lower
            penalty_team_id = _penalty_team_id(penalty_info, text, abbr_to_id, opponent_id)
            charged_yards, yardage_note = _charged_penalty_yards(penalty_info, play)
            if (expanded and has_penalty_flag
                    and (not penalty_yards_from_plays or competitive)
                    and not is_declined_only_penalty(text_lower, penalty_info)):
                commit_team_id = penalty_team_id
                attribution_note = None
                if (penalty_yards_from_plays
                        and (penalty_info.get('status') or {}).get('slug') == 'accepted'
                        and commit_team_id not in details):
                    # Both totals are unavailable when the committing team is
                    # unknown; show the unresolved play in both drilldowns.
                    detail_team_ids = list(details)
                    attribution_note = 'Committing team unavailable'
                else:
                    if not commit_team_id:
                        commit_team_id = opponent_id if 'on defense' in text_lower else team_id
                    if commit_team_id not in details:
                        commit_team_id = team_id
                    detail_team_ids = [commit_team_id]
                yards_pen = -charged_yards if charged_yards is not None else None
                for detail_team_id in detail_team_ids:
                    details[detail_team_id]['Penalty Yards'].append({
                        'source_play_id': str(play.get('id')),
                        'penalty_type': (penalty_info.get('type') or {}).get('text'),
                        'penalty_status': (penalty_info.get('status') or {}).get('slug'),
                        'yards': yards_pen,
                        'yardage_note': yardage_note,
                        'team_attribution_note': attribution_note,
                        'text': play.get('text', ''),
                        'type': play_type,
                        'quarter': play.get('period', {}).get('number'),
                        'clock': play.get('clock', {}).get('displayValue'),
                        'end_pos': _end_pos_text(play),
                        'probability': probability_snapshot
                    })

            # Accepted penalties count even when they nullify the underlying
            # play. Apply the WP scope before the no-play filter below.
            if penalty_yards_from_plays and competitive:
                penalty_status = (penalty_info.get('status') or {}).get('slug')
                if penalty_status == 'accepted' and penalty_team_id in stats and charged_yards is not None:
                    stats[penalty_team_id]['Penalty Yards'] += charged_yards

            if 'timeout' in play_type_lower or 'end of' in play_type_lower:
                record_debug_play(play, drive_index, team_id, debug_before,
                                  'timeout_or_period_end', debug_start_home_wp, debug_start_away_wp)
                update_prev_wp(play)
                continue
            if is_nullified_play(text_lower) and not _is_credited_nullified_touchdown(play):
                record_debug_play(play, drive_index, team_id, debug_before,
                                  'nullified', debug_start_home_wp, debug_start_away_wp)
                update_prev_wp(play)
                continue

            if not competitive:
                record_debug_play(play, drive_index, team_id, debug_before,
                                  'wp_filter', debug_start_home_wp, debug_start_away_wp)
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
            conversion_markers = ('two-point', '2-point', 'conversion attempt')
            conversion_positions = [event_text_lower.find(marker) for marker in conversion_markers
                                    if marker in event_text_lower]
            conversion_start = min(conversion_positions) if conversion_positions else -1
            # ESPN appends conversion text to a touchdown play. That must not
            # erase a turnover that happened before the touchdown.
            is_two_point_conversion_attempt = (
                conversion_start >= 0
                and 'touchdown' not in event_text_lower[:conversion_start]
            )
            turnover_text_lower = (
                event_text_lower[:conversion_start]
                if conversion_start >= 0 and not is_two_point_conversion_attempt
                else event_text_lower
            )
            # Defaults used by offensive/totals yard accounting below.
            interception = False
            fumble_phrase = False
            if is_two_point_conversion_attempt:
                turnover_on_play = False
            else:
                kick_context = any(keyword in turnover_text_lower or keyword in play_type_lower
                                   for keyword in ('punt', 'kick', 'field goal'))
                muffed_kick = kick_context and (bool(_MUFF_RE.search(turnover_text_lower)) or 'muff' in play_type_lower)
                interception = 'interception' in play_type_lower or 'intercept' in turnover_text_lower
                if has_replay_reversal and ('intercept' not in turnover_text_lower and 'interception' not in turnover_text_lower):
                    interception = False
                fumble_phrase = 'fumble' in turnover_text_lower
                is_fumble_recovery_own = 'fumble recovery (own)' in play_type_lower
                is_fumble_recovery_opp = 'fumble recovery (opponent)' in play_type_lower or 'sack opp fumble recovery' in play_type_lower

                turnover_events = []
                current_possessor = start_team_id

                # Punt plays: once the punt is kicked ("punts ..."), the receiving team has the
                # possession context for any subsequent fumble/recovery in the same play text.
                punt_in_air = 'punts' in turnover_text_lower
                if punt_in_air and opponent_id and (fumble_phrase or muffed_kick):
                    current_possessor = opponent_id

                # ESPN can attribute an onside play's drive to either team. The play's
                # start team is the kicker; a recovery by that team costs the receiver
                # a possession in this dashboard's custom Turnovers definition.
                onside_kick = 'onside' in turnover_text_lower and 'kick' in turnover_text_lower
                kicking_team_recovered_onside = False
                if onside_kick:
                    explicit_start_team_id = play.get('start', {}).get('team', {}).get('id')
                    recovered_match = _RECOVERED_BY_ABBR_RE.search(turnover_text_lower)
                    recovered_team_id = (
                        abbr_to_id.get(_canonical_team_abbr(recovered_match.group(1)))
                        if recovered_match else end_team_id
                    )
                    kicking_team_recovered_onside = (
                        explicit_start_team_id in id_to_abbr
                        and opponent_id in id_to_abbr
                        and 'recovered' in turnover_text_lower
                        and recovered_team_id == explicit_start_team_id
                    )
                    if kicking_team_recovered_onside:
                        turnover_events.append((opponent_id, 'onside_kick_lost'))

                if muffed_kick and opponent_id:
                    current_possessor = opponent_id

                # Kickoff return fumbles are charged to the receiving team (opponent), even though
                # `start_team_id` is the kicking team. Without this adjustment, a successful
                # kick-coverage recovery can be misattributed as a turnover by the kicking team.
                kickoff_play = 'kickoff' in play_type_lower or 'kickoff' in turnover_text_lower
                if kickoff_play and fumble_phrase and opponent_id and not onside_kick and not muffed_kick:
                    current_possessor = opponent_id

                if interception:
                    turnover_events.append((current_possessor, 'interception'))
                    if opponent_id:
                        current_possessor = opponent_id

                muff_possessor = current_possessor
                if fumble_phrase:
                    fumble_matches = list(_FUMBLE_RE.finditer(turnover_text_lower))
                    for index, match in enumerate(fumble_matches):
                        segment_end = (fumble_matches[index + 1].start()
                                       if index + 1 < len(fumble_matches) else len(turnover_text_lower))
                        segment = turnover_text_lower[match.start():segment_end]
                        recovered_team_id = None
                        recovered_match = _RECOVERED_BY_ABBR_RE.search(segment)
                        if recovered_match:
                            recovered_team_id = abbr_to_id.get(_canonical_team_abbr(recovered_match.group(1)))
                        if recovered_team_id is None:
                            if 'touchback' in segment and current_possessor in id_to_abbr:
                                recovered_team_id = next((tid for tid in id_to_abbr if tid != current_possessor), None)
                            elif 'and recovers' in segment or 'recovers at' in segment:
                                recovered_team_id = current_possessor
                            elif len(fumble_matches) == 1 and is_fumble_recovery_own:
                                recovered_team_id = current_possessor
                            elif len(fumble_matches) == 1 and is_fumble_recovery_opp and opponent_id:
                                recovered_team_id = opponent_id
                            elif index == len(fumble_matches) - 1:
                                recovered_team_id = end_team_id

                        if recovered_team_id is not None and current_possessor is not None:
                            if recovered_team_id != current_possessor and not muffed_kick:
                                turnover_events.append((current_possessor, 'fumble'))
                            current_possessor = recovered_team_id

                if muffed_kick and not kicking_team_recovered_onside:
                    recovered_match = _RECOVERED_BY_ABBR_RE.search(turnover_text_lower)
                    recovered_team_id = (
                        abbr_to_id.get(_canonical_team_abbr(recovered_match.group(1)))
                        if recovered_match else end_team_id
                    )
                    if recovered_team_id is not None and recovered_team_id != muff_possessor:
                        turnover_events.append((muff_possessor, 'muffed_kick'))

                turnover_on_play = bool(turnover_events)
                if turnover_on_play:
                    for t_event, reason in turnover_events:
                        if t_event not in stats:
                            continue
                        stats[t_event]['Turnovers'] += 1
                        if expanded:
                            details[t_event]['Turnovers'].append({
                                'source_play_id': str(play.get('id')),
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
                        'source_play_id': str(play_id),
                        'type': non_off_entry.get('type') or play_type,
                        'text': non_off_entry.get('text') or text,
                        'points': non_off_entry.get('points'),
                        'quarter': play.get('period', {}).get('number'),
                        'clock': play.get('clock', {}).get('displayValue'),
                        'end_pos': _end_pos_text(play),
                        'probability': probability_snapshot
                    })

            contribution = _build_offensive_play_contribution(
                play,
                event_text=event_text,
                offense_abbrev=offense_abbrev,
                penalty_info=penalty_info,
                turnover_on_play=turnover_on_play,
                interception=interception,
                fumble_phrase=fumble_phrase,
                is_incomplete_pass=is_incomplete_pass,
                aborted_snap=aborted_snap,
                is_two_point_conversion_attempt=is_two_point_conversion_attempt,
            )
            if contribution.adjusted_play:
                stats[team_id]['Plays'] += 1
                stats[team_id]['Offensive Yards'] += contribution.adjusted_yards
                down = play.get('start', {}).get('down', 1)
                dist = play.get('start', {}).get('distance', 10)
                successful = calculate_success(down, dist, contribution.adjusted_yards)
                if successful:
                    stats[team_id]['Successful Plays'] += 1
                if expanded:
                    details[team_id]['Offensive Plays'].append({
                        'source_play_id': str(play.get('id')),
                        'type': 'Pass' if contribution.pass_dropback else 'Run',
                        'text': text,
                        'yards': contribution.adjusted_yards,
                        'success': successful,
                        'quarter': play.get('period', {}).get('number'),
                        'clock': play.get('clock', {}).get('displayValue'),
                    })
                if ((contribution.run and not contribution.pass_dropback
                     and contribution.adjusted_yards >= 10)
                        or (contribution.pass_dropback and contribution.adjusted_yards >= 20)):
                    stats[team_id]['Explosive Plays'] += 1
                    if expanded:
                        details[team_id]['Explosive Plays'].append({
                            'source_play_id': str(play.get('id')),
                            'yards': contribution.adjusted_yards,
                            'text': text,
                            'type': 'Run' if contribution.run else 'Pass',
                            'quarter': play.get('period', {}).get('number'),
                            'clock': play.get('clock', {}).get('displayValue'),
                            'end_pos': _end_pos_text(play),
                            'probability': lookup_probability_with_delta(play)
                        })

            if contribution.total_offense_play:
                stats[team_id]['Total Offensive Plays'] += 1
            if contribution.total_offense_play or contribution.total_yards_only:
                if contribution.total_yards != contribution.total_yards_before_penalty:
                    if expanded and team_id in details:
                        details[team_id]['Total Yards Corrections'].append({
                            'type': play_type,
                            'text': text,
                            'quarter': play.get('period', {}).get('number'),
                            'clock': play.get('clock', {}).get('displayValue'),
                            'statYardage': contribution.total_yards_before_penalty,
                            'startYardsToEndzone': (play.get('start') or {}).get('yardsToEndzone'),
                            'penaltyYards': penalty_info.get('yards'),
                            'enforcedAtYardsToEndzone': _enforced_at_yards_to_endzone(
                                event_text, offense_abbrev
                            ),
                            'correctedYards': contribution.total_yards,
                            'reason': 'accepted_penalty_credited_play_yards',
                        })
                stats[team_id]['Total Yards'] += contribution.total_yards

            # Net punting average follows the official box-score convention:
            # gross punt distance less return yards and 20 yards per touchback.
            # ESPN's statYardage on punt plays is return yardage, not punt distance.
            if play_type_lower == 'punt':
                punt_text = final_play_text(text)
                distance_match = _PUNT_DISTANCE_RE.search(punt_text)
                blocked = 'blocked' in punt_text.lower()
                if distance_match or blocked:
                    gross_yards = int(distance_match.group(1)) if distance_match else 0
                    return_yards = play.get('statYardage', 0)
                    if not isinstance(return_yards, (int, float)):
                        return_yards = 0
                    touchback = 'touchback' in punt_text.lower()
                    stats[team_id]['Punt Net Sum'] += gross_yards - return_yards - (20 if touchback else 0)
                    stats[team_id]['Punt Plays'] += 1

            # Kickoff quality is reported as the opponent's starting yard line,
            # not a fabricated "net kickoff" distance. Attribute the result to
            # the kicking team and use the post-penalty receiving spot.
            if 'kickoff' in play_type_lower and 'return' not in play_type_lower:
                start = play.get('start') or {}
                end = play.get('end') or {}
                kicker_id = (start.get('team') or {}).get('id') or team_id
                receiver_id = (end.get('team') or {}).get('id')
                yte = end.get('yardsToEndzone')
                if (kicker_id in stats and receiver_id and receiver_id != kicker_id
                        and isinstance(yte, (int, float)) and 0 <= yte <= 100):
                    stats[kicker_id]['Kickoff Opponent Start Sum'] += 100 - yte
                    stats[kicker_id]['Kickoff Count'] += 1

            # Collect all meaningful plays for "All Plays" category
            if expanded:
                is_meaningful = (
                    contribution.adjusted_play or  # Offensive play
                    play.get('scoringPlay') or               # Scoring play
                    turnover_on_play or                      # Turnover
                    has_penalty_flag                         # Penalty
                )
                if is_meaningful:
                    play_entry = {
                        'source_play_id': str(play.get('id')),
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

            record_debug_play(play, drive_index, team_id, debug_before,
                              None, debug_start_home_wp, debug_start_away_wp)
            update_prev_wp(play)

        debug_drive_end_before = stat_snapshot()
        if drive_started_competitive:
            if drive_has_offensive_play and drive_start_yte != -1 and drive_start_yte <= 40:
                drive_crossed_40_competitive = True
            if drive_crossed_40_competitive and drive_has_offensive_play:
                stats[team_id]['Drives Inside 40'] += 1
                stats[team_id]['Points Inside 40'] += drive_points_competitive
            stats[team_id]['Drive Points'] += drive_points_competitive
            if expanded and drive_crossed_40_competitive and drive_has_offensive_play and last_competitive_play:
                details[team_id]['Points Per Trip (Inside 40)'].append({
                    'source_play_id': str(last_competitive_play.get('id')),
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
                    'source_play_id': str(cause_play.get('id')) if cause_play else None,
                    'text': (cause_play.get('text', '') if cause_play else 'Start of game'),
                    'type': (cause_play.get('type', {}) or {}).get('text', 'Drive Start') if cause_play else 'Drive Start',
                    'yards': (cause_play.get('statYardage') if cause_play else None),
                    'quarter': drive_start_quarter,
                    'clock': drive_start_clock,
                    'start_pos': start_pos,
                    'end_pos': start_pos,
                })

        if debug_rows is not None:
            drive_deltas = stat_delta(debug_drive_end_before)
            if drive_deltas:
                debug_rows.append({
                    'kind': 'drive_end',
                    'drive': drive_index + 1,
                    'team': id_to_abbr.get(team_id, team_id),
                    'text': 'Drive totals finalized',
                    'statDeltas': drive_deltas,
                    'raw': drive,
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
        kickoff_count = d['Kickoff Count']

        row = {
            'Team': d['Team'],
            'Score': d['Score'],
            'Turnovers': d['Turnovers'],
            'Total Yards': d['Total Yards'],
            'Calculated Offensive Plays': d['Total Offensive Plays'],
            'Official Yards Per Play (Full Game)': d['Official Yards Per Play (Full Game)'],
            'Adjusted Yards Per Play': round(d['Offensive Yards'] / plays, 2),
            'Success Rate': round((d['Successful Plays'] / plays), 3),
            'Explosive Plays': d['Explosive Plays'],
            'Explosive Play Rate': round(d['Explosive Plays'] / plays, 3),
            'Points Per Trip (Inside 40)': round(d['Points Inside 40'] / drives_in_40, 2),
            'Ave Start Field Pos': format_field_position(d['Start Field Pos Sum'] / drives_total),
            'Drives': d['Drives Count'],
            'Turnover Margin': turnover_margin.get(t_id, 0),
            'Points per Drive': round(d['Drive Points'] / drives_total, 2),
            'Net Punting': round(d['Punt Net Sum'] / punt_plays, 1) if d['Punt Plays'] > 0 else 0,
            'Avg Opponent Kickoff Start': f"Own {round(d['Kickoff Opponent Start Sum'] / kickoff_count)}" if kickoff_count > 0 else '—',
            'ST Penalties': d.get('ST Penalties', 0),
            'Penalty Yards': d.get('Penalty Yards', 0),
            'Non-Offensive Points': d.get('Non-Offensive Points', 0)
        }
        final_rows.append(row)

    if expanded:
        return final_rows, details
    return final_rows, {}


def reconcile_final_boxscore(game_data, rows, details):
    """Use ESPN box-score totals for final games, retaining parser gaps for audit.

    Play-derived metrics remain untouched: missing summary plays cannot be
    assigned to a competitive WP window or used to invent success/explosive
    plays. Live games retain their play-by-play totals to avoid feed lag.
    """
    competitions = (game_data.get('header') or {}).get('competitions') or []
    status_type = ((competitions[0].get('status') or {}).get('type') or {}) if competitions else {}
    if status_type.get('state') != 'post' and not status_type.get('completed'):
        return rows, []

    def boxscore_int(stat):
        try:
            return int(str(stat.get('displayValue')).replace(',', ''))
        except (TypeError, ValueError):
            return None

    official = {}
    onside_against = {}
    for entry in (game_data.get('boxscore') or {}).get('teams') or []:
        team = entry.get('team') or {}
        abbr = team.get('abbreviation')
        if not abbr:
            continue
        official[abbr] = {
            stat.get('name'): boxscore_int(stat)
            for stat in entry.get('statistics') or []
            if stat.get('name') in ('totalYards', 'turnovers', 'totalOffensivePlays')
        }
        onside_against[abbr] = sum(
            play.get('reason') == 'onside_kick_lost'
            for play in ((details.get(str(team.get('id'))) or {}).get('Turnovers') or [])
        )

    reconciled = []
    gaps = []
    for row in rows:
        updated = dict(row)
        abbr = row.get('Team')
        box = official.get(abbr, {})
        yards = box.get('totalYards')
        turnovers = box.get('turnovers')
        offensive_plays = box.get('totalOffensivePlays')
        if yards is not None:
            updated['Calculated Total Yards'] = row['Total Yards']
            updated['Total Yards'] = yards
        if turnovers is not None:
            updated['Calculated Turnovers'] = row['Turnovers']
            updated['Turnovers'] = turnovers + onside_against.get(abbr, 0)
        yards_gap = updated['Total Yards'] - row['Total Yards']
        turnovers_gap = updated['Turnovers'] - row['Turnovers']
        calculated_plays = row.get('Calculated Offensive Plays')
        plays_gap = (offensive_plays - calculated_plays
                     if offensive_plays is not None and calculated_plays is not None
                     else 0)
        if offensive_plays is not None:
            updated['Official Offensive Plays'] = offensive_plays
        if yards_gap or turnovers_gap or plays_gap:
            gaps.append({
                'team': abbr,
                'yards_gap': yards_gap,
                'turnovers_gap': turnovers_gap,
                'plays_gap': plays_gap,
            })
        reconciled.append(updated)

    if len(reconciled) == 2:
        first, second = reconciled
        first['Turnover Margin'] = second['Turnovers'] - first['Turnovers']
        second['Turnover Margin'] = first['Turnovers'] - second['Turnovers']

    return reconciled, gaps


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
    add_stat_line("Adjusted yards per play", "Adjusted Yards Per Play")

    return " ".join(parts)
