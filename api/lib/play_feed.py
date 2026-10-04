"""Canonical, source-backed play context for every game-detail presentation."""

import re
from .nfl_core import (
    _canonical_team_abbr, _charged_penalty_yards,
    boxscore_abbreviations_by_id, normalize_position_text,
)


def _number(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _score(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_play_feed(raw_data, probability_map, pregame_home_wp, epa_by_id=None):
    """Return chronological ESPN plays with pre-play situation and measured WP.

    A missing transition or score is kept unknown. ESPN's scoreboard on a play
    is the result of that play; the preceding row supplies its pre-play score.
    """
    epa_by_id = epa_by_id or {}
    comps = ((raw_data.get('header') or {}).get('competitions') or [{}])[0]
    competitors = comps.get('competitors') or []
    abbr_by_id = boxscore_abbreviations_by_id(raw_data)
    home_id = away_id = None
    for team in competitors:
        team_id = str(team.get('id') or (team.get('team') or {}).get('id') or '')
        if team_id and team_id not in abbr_by_id:
            abbr_by_id[team_id] = (team.get('team') or {}).get('abbreviation')
        if team.get('homeAway') == 'home':
            home_id = team_id
        elif team.get('homeAway') == 'away':
            away_id = team_id
    known_abbrs = {_canonical_team_abbr(abbr): abbr for abbr in abbr_by_id.values() if abbr}
    abbr_from_text = {abbr.lower(): abbr for abbr in abbr_by_id.values() if abbr}
    drives = raw_data.get('drives') or {}
    all_drives = list(drives.get('previous') or [])
    if drives.get('current'):
        all_drives.append(drives['current'])
    result = []
    seen = set()
    ordered_plays = []
    for drive in all_drives:
        drive_team_id = str((drive.get('team') or {}).get('id') or '')
        for play in drive.get('plays') or []:
            play_id = str(play.get('id') or '')
            if play_id and play_id not in seen:
                seen.add(play_id)
                ordered_plays.append((drive_team_id, play))
    before_score = {'home': 0, 'away': 0}
    before_wp = _number(pregame_home_wp)
    restored_score_index = None
    for index, (drive_team_id, play) in enumerate(ordered_plays):
            play_id = str(play.get('id') or '')
            start = play.get('start') or {}
            source_id = str((start.get('team') or {}).get('id') or drive_team_id)
            source_abbr = abbr_by_id.get(source_id)
            ball = normalize_position_text(start.get('possessionText'), known_abbrs)
            if ball is None and start.get('possessionText'):
                ball = None
            if not ball and isinstance(start.get('yardsToEndzone'), (int, float)) and source_abbr:
                yte = start['yardsToEndzone']
                if 0 <= yte <= 100:
                    other = away_id if source_id == home_id else home_id
                    ball = '50' if yte == 50 else f"{source_abbr} {100-yte}" if yte > 50 else f"{abbr_by_id.get(other, '')} {yte}".strip()
            post_home = _score(play.get('homeScore'))
            post_away = _score(play.get('awayScore'))
            after_score = {'home': post_home, 'away': post_away} if post_home is not None and post_away is not None else None
            # ESPN can briefly publish a lower score on a no-play penalty and
            # restore it on the next row. Do not turn the restoration into a
            # scoring kickoff when both rows share the same clock.
            if after_score and before_score and index + 1 < len(ordered_plays):
                next_play = ordered_plays[index + 1][1]
                next_home = _score(next_play.get('homeScore'))
                next_away = _score(next_play.get('awayScore'))
                same_clock = (play.get('clock') or {}).get('displayValue') == (next_play.get('clock') or {}).get('displayValue')
                if same_clock and any(after_score[side] < before_score[side] for side in ('home', 'away')) \
                        and next_home is not None and next_away is not None \
                        and next_home >= before_score['home'] and next_away >= before_score['away']:
                    after_score = dict(before_score)
                    restored_score_index = index + 1
            probability = probability_map.get(play_id) or {}
            after_wp = _number(probability.get('homeWinPercentage'))
            wp_delta = after_wp - before_wp if after_wp is not None and before_wp is not None else None
            text = play.get('text') or ''
            penalty = play.get('penalty') or {}
            penalty_info = None
            penalty_status = ((penalty.get('status') or {}).get('slug') or '').lower()
            if penalty or re.search(r'\bpenalty\b', text, re.I):
                match = re.search(r'\bPENALTY on\s+([A-Z]{2,4})(?:-[^,]+)?,\s*([^,.]+)', text, re.I)
                penalty_team = None
                penalty_type = (penalty.get('type') or {}).get('text')
                if match:
                    penalty_team = abbr_from_text.get(_canonical_team_abbr(match.group(1)), match.group(1).upper())
                    penalty_type = penalty_type or match.group(2).strip()
                yards, yard_note = _charged_penalty_yards(penalty, play)
                penalty_info = {
                    'team': penalty_team,
                    'type': penalty_type or 'Penalty',
                    'status': penalty_status or ('declined' if re.search(r'\bdeclined\b', text, re.I) else 'unknown'),
                    'yards': yards,
                    'note': yard_note,
                }
            down = start.get('down')
            distance = start.get('distance')
            score_change = None
            if after_score and before_score:
                home_points = after_score['home'] - before_score['home']
                away_points = after_score['away'] - before_score['away']
                if home_points > 0 or away_points > 0:
                    scoring_id = home_id if home_points > 0 else away_id
                    score_change = {
                        'team': abbr_by_id.get(scoring_id),
                        'points': max(home_points, away_points),
                        'non_offensive': scoring_id != source_id,
                    }
            result.append({
                'id': play_id,
                'sourceTeamId': source_id,
                'sourceTeam': source_abbr,
                'quarter': (play.get('period') or {}).get('number'),
                'clock': (play.get('clock') or {}).get('displayValue'),
                'type': (play.get('type') or {}).get('text') or 'Play',
                'text': text,
                'down': down,
                'distance': distance,
                'ballBefore': ball,
                'scoreBefore': dict(before_score) if before_score else None,
                'scoreAfter': after_score,
                'homeWpBefore': before_wp,
                'homeWpAfter': after_wp,
                'homeWpDelta': wp_delta,
                'wpAttributionUncertain': index == restored_score_index,
                'epa': epa_by_id.get(play_id),
                'penalty': penalty_info,
                'scoreChange': score_change,
            })
            if after_score:
                before_score = after_score
            else:
                before_score = None
            # A missing WP entry means the next play has no measured adjacent pair.
            before_wp = after_wp
    return result
