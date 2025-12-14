#!/usr/bin/env python3
"""
Diagnostic script to identify stat discrepancies between ESPN and game_compare.py.

Usage:
    python diagnose_game_discrepancies.py <game_id>

Example:
    python diagnose_game_discrepancies.py 401772896
"""

import sys
import requests
from collections import defaultdict

from game_compare import (
    get_game_data,
    process_game_stats,
    classify_offense_play,
    is_special_teams_play,
    is_penalty_play,
    is_nullified_play,
    is_spike_or_kneel,
)


def get_espn_official_stats(game_id):
    """
    Fetch official team stats from ESPN's summary API.
    Returns (stats_dict, game_header, team_order, away_team, home_team)
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"Error fetching ESPN data: {e}")
        return None, None, None, None, None

    header = data.get('header', {})
    competitions = header.get('competitions', [])

    away_team = None
    home_team = None
    away_score = 0
    home_score = 0

    if competitions:
        comp = competitions[0]
        for competitor in comp.get('competitors', []):
            abbr = competitor.get('team', {}).get('abbreviation', '')
            score = int(competitor.get('score', 0))
            if competitor.get('homeAway') == 'away':
                away_team = abbr
                away_score = score
            else:
                home_team = abbr
                home_score = score

    game_header = f"{away_team} {away_score} @ {home_team} {home_score} ({game_id})"

    boxscore = data.get('boxscore', {})
    teams_data = boxscore.get('teams', [])

    espn_stats = {}

    for team_data in teams_data:
        team_info = team_data.get('team', {})
        abbr = team_info.get('abbreviation', '')

        stats = {
            'Score': away_score if abbr == away_team else home_score,
            'Total Yards': 0,
            'Turnovers': 0,
            'Rushing Yards': 0,
            'Passing Yards': 0,
            'Penalty Yards': 0,
        }

        for stat in team_data.get('statistics', []):
            stat_name = stat.get('name', '')
            display_value = stat.get('displayValue', '')

            if stat_name == 'totalYards':
                try:
                    stats['Total Yards'] = int(display_value)
                except (ValueError, TypeError):
                    pass
            elif stat_name == 'turnovers':
                try:
                    stats['Turnovers'] = int(display_value)
                except (ValueError, TypeError):
                    pass
            elif stat_name == 'rushingYards':
                try:
                    stats['Rushing Yards'] = int(display_value)
                except (ValueError, TypeError):
                    pass
            elif stat_name == 'netPassingYards':
                try:
                    stats['Passing Yards'] = int(display_value)
                except (ValueError, TypeError):
                    pass
            elif stat_name == 'totalPenaltiesYards':
                if isinstance(display_value, str) and '-' in display_value:
                    parts = display_value.split('-')
                    if len(parts) == 2:
                        try:
                            stats['Penalty Yards'] = int(parts[1])
                        except (ValueError, TypeError):
                            pass

        espn_stats[abbr] = stats

    team_order = [away_team, home_team] if away_team and home_team else list(espn_stats.keys())

    return espn_stats, game_header, team_order, away_team, home_team


def classify_play_type(play, text_lower, type_lower):
    """
    Classify a play into categories for diagnostic purposes.
    Returns (category, subcategory)
    """
    is_offense, is_run, is_pass = classify_offense_play(play)

    if is_offense:
        if is_run:
            return 'Offensive', 'Rushing'
        elif is_pass:
            return 'Offensive', 'Passing'
        else:
            return 'Offensive', 'Other'

    # Check special teams
    if 'kickoff' in text_lower or 'kickoff' in type_lower:
        if 'return' in text_lower or 'return' in type_lower:
            return 'Special Teams', 'Kickoff Return'
        return 'Special Teams', 'Kickoff'

    if 'punt' in text_lower or 'punt' in type_lower:
        if 'return' in text_lower or 'return' in type_lower:
            return 'Special Teams', 'Punt Return'
        return 'Special Teams', 'Punt'

    if 'field goal' in text_lower or 'fg' in type_lower:
        return 'Special Teams', 'Field Goal'

    if 'extra point' in text_lower or 'xp' in type_lower:
        return 'Special Teams', 'Extra Point'

    # Check for penalties
    if is_penalty_play(play, text_lower, type_lower):
        return 'Penalty', 'Penalty (No Play)'

    # Check for spikes/kneels
    if is_spike_or_kneel(text_lower, type_lower):
        return 'Clock Management', 'Spike/Kneel'

    # Check for timeouts
    if 'timeout' in type_lower:
        return 'Other', 'Timeout'

    if 'end of' in type_lower or 'end period' in type_lower:
        return 'Other', 'End of Period'

    return 'Unknown', 'Unknown'


def analyze_turnovers(play, text_lower, type_lower, offense_team_id, opponent_id, id_to_abbr):
    """
    Analyze a play for turnover indicators.
    Returns list of (team_charged, reason, is_counted) tuples
    """
    turnovers = []
    offense_abbrev = id_to_abbr.get(offense_team_id, '').lower()

    overturned = 'reversed' in text_lower or 'overturned' in text_lower

    # Check for interception
    interception = 'interception' in type_lower or 'intercept' in text_lower
    if interception:
        if overturned:
            turnovers.append((offense_team_id, 'interception (overturned)', False))
        else:
            turnovers.append((offense_team_id, 'interception', True))

    # Check for fumble
    fumble_phrase = 'fumble' in text_lower
    if fumble_phrase:
        recovered_by_def = False

        if 'recovered by' in text_lower:
            if offense_abbrev:
                recovered_by_def = f"recovered by {offense_abbrev}" not in text_lower
            else:
                recovered_by_def = True
        elif 'fumble recovery (own)' in type_lower:
            recovered_by_def = False

        # Check for possession change via team IDs
        start_team_id = play.get('start', {}).get('team', {}).get('id') or offense_team_id
        end_team_id = play.get('end', {}).get('team', {}).get('id')
        if start_team_id and end_team_id and start_team_id != end_team_id:
            recovered_by_def = True

        if overturned:
            turnovers.append((offense_team_id, 'fumble (overturned)', False))
        elif recovered_by_def:
            turnovers.append((offense_team_id, 'fumble lost', True))
        else:
            turnovers.append((offense_team_id, 'fumble (own recovery)', False))

    # Check for muffed punt/kick
    muffed_punt = 'muffed punt' in text_lower or 'muff' in type_lower
    muffed_kick = muffed_punt or 'muffed kick' in text_lower or 'muffed kickoff' in text_lower
    if muffed_kick and opponent_id:
        # Muffed kicks are charged to the receiving team (opponent)
        if overturned:
            turnovers.append((opponent_id, 'muffed kick (overturned)', False))
        else:
            turnovers.append((opponent_id, 'muffed kick', True))

    # Check for blocked kick/punt
    if 'blocked' in text_lower and ('punt' in type_lower or 'field goal' in type_lower or 'fg' in type_lower):
        start_team_id = play.get('start', {}).get('team', {}).get('id') or offense_team_id
        end_team_id = play.get('end', {}).get('team', {}).get('id')
        if start_team_id and end_team_id and start_team_id != end_team_id:
            if overturned:
                turnovers.append((start_team_id, 'blocked kick (overturned)', False))
            else:
                turnovers.append((start_team_id, 'blocked kick', True))

    # Check for onside kick recovery
    if 'onside' in text_lower and 'kick' in text_lower and opponent_id:
        end_team_id = play.get('end', {}).get('team', {}).get('id')
        start_team_id = play.get('start', {}).get('team', {}).get('id') or offense_team_id
        if end_team_id == start_team_id:  # Kicking team recovered
            turnovers.append((opponent_id, 'onside kick lost', True))

    return turnovers


def diagnose_game(game_id):
    """Main diagnostic function."""

    print(f"Fetching ESPN official stats for game {game_id}...")
    espn_stats, game_header, team_order, away_team, home_team = get_espn_official_stats(game_id)

    if not espn_stats:
        print("Failed to fetch ESPN stats")
        return

    print(f"Fetching play-by-play data...")
    game_data = get_game_data(game_id)

    if not game_data:
        print("Failed to fetch game data")
        return

    # Get game_compare stats (unfiltered)
    df = process_game_stats(
        game_data,
        expanded=False,
        probability_map=None,
        pregame_probabilities=None,
        wp_threshold=1.0
    )

    gc_stats = {}
    for _, row in df.iterrows():
        abbr = row['Team']
        gc_stats[abbr] = {
            'Total Yards': row['Total Yards'],
            'Turnovers': row['Turnovers'],
        }

    # Build team ID mapping
    boxscore = game_data.get('boxscore', {})
    teams_info = boxscore.get('teams', [])
    id_to_abbr = {}
    abbr_to_id = {}
    for t in teams_info:
        tid = t.get('team', {}).get('id')
        abbr = t.get('team', {}).get('abbreviation')
        if tid and abbr:
            id_to_abbr[tid] = abbr
            abbr_to_id[abbr] = tid

    # Process all plays
    drives = game_data.get('drives', {}).get('previous', [])

    # Storage for analysis
    plays_by_team = {team: {
        'counted': defaultdict(list),
        'excluded': defaultdict(list),
        'turnovers_counted': [],
        'turnovers_potential': [],
    } for team in team_order}

    for drive in drives:
        drive_team_id = drive.get('team', {}).get('id')
        drive_team_abbr = id_to_abbr.get(drive_team_id, 'UNK')
        opponent_id = None
        if len(id_to_abbr) == 2:
            opponent_id = next((tid for tid in id_to_abbr if tid != drive_team_id), None)

        for play in drive.get('plays', []):
            text = play.get('text', '') or ''
            text_lower = text.lower()
            play_type = play.get('type', {}).get('text', 'Unknown')
            type_lower = play_type.lower()
            yards = play.get('statYardage', 0) or 0
            quarter = play.get('period', {}).get('number', '?')
            clock = play.get('clock', {}).get('displayValue', '?')

            # Skip timeouts and end of period markers
            if 'timeout' in type_lower or 'end of' in type_lower:
                continue

            play_info = {
                'quarter': quarter,
                'clock': clock,
                'type': play_type,
                'yards': yards,
                'text': text[:100],
                'full_text': text,
            }

            # Classify the play
            category, subcategory = classify_play_type(play, text_lower, type_lower)
            is_offense, is_run, is_pass = classify_offense_play(play)

            # Check for turnover
            turnover_events = analyze_turnovers(
                play, text_lower, type_lower,
                drive_team_id, opponent_id, id_to_abbr
            )

            # Determine which team this affects
            play_team = drive_team_abbr

            # For kickoff returns, the returning team is the opponent
            if subcategory in ['Kickoff Return', 'Punt Return']:
                if opponent_id:
                    play_team = id_to_abbr.get(opponent_id, drive_team_abbr)

            if play_team not in plays_by_team:
                continue

            play_info['category'] = category
            play_info['subcategory'] = subcategory

            # Determine if this play was counted toward Total Yards
            if is_offense and (is_run or is_pass):
                # Check if turnover zeroed out yards
                has_turnover = any(counted for _, _, counted in turnover_events)
                if has_turnover:
                    play_info['note'] = 'Turnover - yards zeroed'
                    play_info['counted_yards'] = 0
                else:
                    play_info['counted_yards'] = yards
                plays_by_team[play_team]['counted'][subcategory].append(play_info)
            else:
                plays_by_team[play_team]['excluded'][subcategory].append(play_info)

            # Track turnovers
            for team_charged_id, reason, is_counted in turnover_events:
                team_charged_abbr = id_to_abbr.get(team_charged_id, 'UNK')
                if team_charged_abbr not in plays_by_team:
                    continue

                turnover_info = {
                    'quarter': quarter,
                    'clock': clock,
                    'text': text[:100],
                    'full_text': text,
                    'reason': reason,
                    'is_counted': is_counted,
                }

                if is_counted:
                    plays_by_team[team_charged_abbr]['turnovers_counted'].append(turnover_info)
                else:
                    plays_by_team[team_charged_abbr]['turnovers_potential'].append(turnover_info)

    # Scan for potential missed turnovers (keyword search)
    turnover_keywords = ['interception', 'intercept', 'fumble', 'muffed', 'blocked', 'turnover']
    potential_missed = {team: [] for team in team_order}

    for drive in drives:
        drive_team_id = drive.get('team', {}).get('id')
        drive_team_abbr = id_to_abbr.get(drive_team_id, 'UNK')

        for play in drive.get('plays', []):
            text = play.get('text', '') or ''
            text_lower = text.lower()

            has_keyword = any(kw in text_lower for kw in turnover_keywords)
            if not has_keyword:
                continue

            # Check if this play was already counted
            quarter = play.get('period', {}).get('number', '?')
            clock = play.get('clock', {}).get('displayValue', '?')

            already_tracked = False
            for team in team_order:
                for to in plays_by_team[team]['turnovers_counted']:
                    if to['quarter'] == quarter and to['clock'] == clock:
                        already_tracked = True
                        break
                for to in plays_by_team[team]['turnovers_potential']:
                    if to['quarter'] == quarter and to['clock'] == clock:
                        already_tracked = True
                        break

            if not already_tracked:
                play_type = play.get('type', {}).get('text', 'Unknown')
                potential_missed[drive_team_abbr].append({
                    'quarter': quarter,
                    'clock': clock,
                    'type': play_type,
                    'text': text[:100],
                    'keywords': [kw for kw in turnover_keywords if kw in text_lower],
                })

    # ============================================
    # OUTPUT REPORT
    # ============================================

    print("\n" + "=" * 80)
    print(f"=== DIAGNOSTIC REPORT: {game_header} ===")
    print("=" * 80)

    # Summary comparison
    print("\nESPN Totals:")
    for team in team_order:
        e = espn_stats.get(team, {})
        print(f"  {team}: {e.get('Total Yards', 'N/A')} yards, {e.get('Turnovers', 'N/A')} turnovers")

    print("\ngame_compare Totals:")
    for team in team_order:
        g = gc_stats.get(team, {})
        e = espn_stats.get(team, {})

        espn_yards = e.get('Total Yards', 0)
        gc_yards = g.get('Total Yards', 0)
        yards_delta = gc_yards - espn_yards

        espn_to = e.get('Turnovers', 0)
        gc_to = g.get('Turnovers', 0)
        to_delta = gc_to - espn_to

        yards_str = f"(DELTA: {yards_delta:+d} yards)" if yards_delta != 0 else "(MATCH)"
        to_str = f"(DELTA: {to_delta:+d} turnovers)" if to_delta != 0 else ""

        print(f"  {team}: {gc_yards} yards {yards_str}, {gc_to} turnovers {to_str}")

    # Section A: Yardage by Play Type
    print("\n" + "=" * 80)
    print("SECTION A: YARDAGE BY PLAY TYPE")
    print("=" * 80)

    for team in team_order:
        team_data = plays_by_team.get(team, {})
        counted = team_data.get('counted', {})

        print(f"\n{team} Offensive Plays (Counted toward Total Yards):")
        total_counted = 0

        for subcategory in ['Rushing', 'Passing', 'Other']:
            plays = counted.get(subcategory, [])
            if not plays:
                continue

            play_count = len(plays)
            yard_sum = sum(p.get('counted_yards', p.get('yards', 0)) for p in plays)
            total_counted += yard_sum
            print(f"  {subcategory}: {play_count} plays, {yard_sum} yards")

        print(f"  Subtotal: {total_counted} yards")

        # Special teams (not counted)
        excluded = team_data.get('excluded', {})
        st_categories = ['Kickoff Return', 'Punt Return', 'Kickoff', 'Punt', 'Field Goal', 'Extra Point']

        print(f"\n{team} Special Teams (NOT Counted toward Total Yards):")
        has_st = False
        for subcat in st_categories:
            plays = excluded.get(subcat, [])
            if not plays:
                continue
            has_st = True
            play_count = len(plays)
            yard_sum = sum(p.get('yards', 0) for p in plays)
            flag = "  <-- POSSIBLE MISSING YARDS" if yard_sum > 0 and subcat in ['Kickoff Return', 'Punt Return'] else ""
            print(f"  {subcat}: {play_count} plays, {yard_sum} yards{flag}")

        if not has_st:
            print("  (none)")

    # Section B: Excluded Plays with Yardage
    print("\n" + "=" * 80)
    print("SECTION B: EXCLUDED PLAYS WITH YARDAGE")
    print("=" * 80)

    for team in team_order:
        team_data = plays_by_team.get(team, {})
        excluded = team_data.get('excluded', {})

        print(f"\n{team} Excluded Plays:")
        has_excluded = False

        for subcat, plays in sorted(excluded.items()):
            for p in plays:
                if p.get('yards', 0) != 0:
                    has_excluded = True
                    q = p.get('quarter', '?')
                    c = p.get('clock', '?')
                    y = p.get('yards', 0)
                    t = p.get('type', 'Unknown')
                    txt = p.get('text', '')
                    print(f"  Q{q} {c} | {subcat} | {y:+d} yards | {t}")
                    print(f"    \"{txt}\"")

        if not has_excluded:
            print("  (no excluded plays with non-zero yardage)")

    # Section C: Turnovers Detected
    print("\n" + "=" * 80)
    print("SECTION C: TURNOVERS DETECTED BY game_compare")
    print("=" * 80)

    for team in team_order:
        team_data = plays_by_team.get(team, {})
        turnovers = team_data.get('turnovers_counted', [])

        gc_to_count = gc_stats.get(team, {}).get('Turnovers', 0)
        print(f"\n{team} Turnovers ({gc_to_count} detected):")

        if not turnovers:
            print("  (none)")
        else:
            for to in turnovers:
                q = to.get('quarter', '?')
                c = to.get('clock', '?')
                reason = to.get('reason', 'unknown')
                txt = to.get('text', '')
                print(f"  Q{q} {c} | \"{txt}\" | Reason: {reason}")

    # Section D: Potential Missing Turnovers
    print("\n" + "=" * 80)
    print("SECTION D: POTENTIAL MISSING TURNOVERS")
    print("=" * 80)

    print("\nPlays with turnover keywords NOT counted:")

    has_potential = False
    for team in team_order:
        team_data = plays_by_team.get(team, {})
        potential = team_data.get('turnovers_potential', [])
        missed = potential_missed.get(team, [])

        all_potential = potential + missed

        if all_potential:
            has_potential = True
            print(f"\n{team}:")
            for p in all_potential:
                q = p.get('quarter', '?')
                c = p.get('clock', '?')
                txt = p.get('text', '')
                reason = p.get('reason', '')
                keywords = p.get('keywords', [])

                if reason:
                    print(f"  Q{q} {c} | \"{txt}\" | NOT COUNTED: {reason}")
                else:
                    print(f"  Q{q} {c} | \"{txt}\" | Keywords: {keywords} <-- INVESTIGATE")

    if not has_potential:
        print("  (none found)")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print("\nYardage Gap Explanation:")
    for team in team_order:
        e = espn_stats.get(team, {})
        g = gc_stats.get(team, {})

        espn_yards = e.get('Total Yards', 0)
        gc_yards = g.get('Total Yards', 0)
        delta = gc_yards - espn_yards

        if delta == 0:
            print(f"  {team}: MATCH - no yardage discrepancy")
        else:
            team_data = plays_by_team.get(team, {})
            excluded = team_data.get('excluded', {})

            # Calculate excluded special teams yards
            kr_yards = sum(p.get('yards', 0) for p in excluded.get('Kickoff Return', []))
            pr_yards = sum(p.get('yards', 0) for p in excluded.get('Punt Return', []))

            explanation_parts = []
            if kr_yards != 0:
                explanation_parts.append(f"Kickoff returns ({kr_yards})")
            if pr_yards != 0:
                explanation_parts.append(f"Punt returns ({pr_yards})")

            explanation = " + ".join(explanation_parts) if explanation_parts else "Unknown source"
            check = "?" if abs(kr_yards + pr_yards - abs(delta)) > 5 else ""
            print(f"  {team}: {delta:+d} yards, likely from: {explanation} {check}")

    print("\nTurnover Gap Explanation:")
    for team in team_order:
        e = espn_stats.get(team, {})
        g = gc_stats.get(team, {})

        espn_to = e.get('Turnovers', 0)
        gc_to = g.get('Turnovers', 0)
        delta = gc_to - espn_to

        if delta == 0:
            print(f"  {team}: MATCH - no turnover discrepancy")
        else:
            team_data = plays_by_team.get(team, {})
            potential = team_data.get('turnovers_potential', [])

            if delta < 0:
                # game_compare has fewer - might have missed some
                print(f"  {team}: {delta:+d} turnovers - game_compare may have missed {abs(delta)} turnover(s)")
                if potential:
                    print(f"    Candidates to investigate: {len(potential)} play(s) with turnover keywords")
            else:
                # game_compare has more - might have overcounted
                print(f"  {team}: {delta:+d} turnovers - game_compare may have overcounted")

    print("\n" + "=" * 80)


def main():
    if len(sys.argv) != 2:
        print("Usage: python diagnose_game_discrepancies.py <game_id>")
        print("Example: python diagnose_game_discrepancies.py 401772896")
        sys.exit(1)

    game_id = sys.argv[1]
    diagnose_game(game_id)


if __name__ == "__main__":
    main()
