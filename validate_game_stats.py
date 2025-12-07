#!/usr/bin/env python3
"""
Validation script to compare game_compare.py statistics against ESPN's official team stats.

Usage:
    python validate_game_stats.py <game_id>

Example:
    python validate_game_stats.py 401772896
"""

import sys
import requests

from game_compare import get_game_data, process_game_stats


def get_espn_team_stats(game_id):
    """
    Fetch official team stats from ESPN's summary API.
    Returns dict with team abbreviations as keys, containing stats.
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"Error fetching ESPN data: {e}")
        return None, None, None

    # Extract game header info
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

    # Extract boxscore stats
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
            'Penalty Yards': 0,
            'Total Drives': 0
        }

        # Parse statistics array
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

            elif stat_name == 'totalPenaltiesYards':
                # Format is "COUNT-YARDS" (e.g., "5-45")
                if isinstance(display_value, str) and '-' in display_value:
                    parts = display_value.split('-')
                    if len(parts) == 2:
                        try:
                            stats['Penalty Yards'] = int(parts[1])
                        except (ValueError, TypeError):
                            pass

            elif stat_name == 'totalDrives':
                try:
                    stats['Total Drives'] = int(display_value)
                except (ValueError, TypeError):
                    pass

        espn_stats[abbr] = stats

    # Determine team order (away first)
    team_order = [away_team, home_team] if away_team and home_team else list(espn_stats.keys())

    return espn_stats, game_header, team_order


def get_game_compare_stats(game_id):
    """
    Get stats from game_compare.py using full/unfiltered data.
    Returns dict with team abbreviations as keys.
    """
    try:
        game_data = get_game_data(game_id)
        if not game_data:
            print(f"Error: Could not fetch game data for {game_id}")
            return None

        # Process with no WP filtering (threshold=1.0 means all plays are "competitive")
        df = process_game_stats(
            game_data,
            expanded=False,
            probability_map=None,
            pregame_probabilities=None,
            wp_threshold=1.0  # No filtering - include all plays
        )

        gc_stats = {}
        for _, row in df.iterrows():
            abbr = row['Team']
            gc_stats[abbr] = {
                'Score': row['Score'],
                'Total Yards': row['Total Yards'],
                'Turnovers': row['Turnovers'],
                'Penalty Yards': row['Penalty Yards'],
                'Total Drives': row['Drives']
            }

        return gc_stats

    except Exception as e:
        print(f"Error processing game_compare stats: {e}")
        import traceback
        traceback.print_exc()
        return None


def compare_and_display(espn_stats, gc_stats, game_header, team_order):
    """
    Compare stats and display formatted comparison table.
    """
    stats_to_compare = ['Score', 'Total Yards', 'Turnovers', 'Penalty Yards', 'Total Drives']

    print(f"\nGame: {game_header}")
    print("=" * 80)
    print(f"{'Stat':<24}| {'Team':<5}| {'ESPN':<8}| {'game_compare':<13}| Delta")
    print("-" * 80)

    mismatch_count = 0

    for stat in stats_to_compare:
        for team in team_order:
            espn_val = espn_stats.get(team, {}).get(stat, 'N/A')
            gc_val = gc_stats.get(team, {}).get(stat, 'N/A')

            # Calculate delta
            if isinstance(espn_val, (int, float)) and isinstance(gc_val, (int, float)):
                delta = gc_val - espn_val
                delta_str = f"{delta:+d}" if delta != 0 else "0"
                indicator = " \u2713" if delta == 0 else " \u26a0\ufe0f"
                if delta != 0:
                    mismatch_count += 1
            else:
                delta_str = "N/A"
                indicator = " ?"

            print(f"{stat:<24}| {team:<5}| {str(espn_val):<8}| {str(gc_val):<13}| {delta_str}{indicator}")

    print("=" * 80)

    if mismatch_count == 0:
        print("Summary: All stats match!")
    else:
        print(f"Summary: {mismatch_count} mismatch(es) found")

    return mismatch_count


def main():
    if len(sys.argv) != 2:
        print("Usage: python validate_game_stats.py <game_id>")
        print("Example: python validate_game_stats.py 401772896")
        sys.exit(1)

    game_id = sys.argv[1]

    print(f"Fetching ESPN stats for game {game_id}...")
    espn_stats, game_header, team_order = get_espn_team_stats(game_id)

    if not espn_stats:
        print("Failed to fetch ESPN stats")
        sys.exit(1)

    print(f"Running game_compare.py analysis...")
    gc_stats = get_game_compare_stats(game_id)

    if not gc_stats:
        print("Failed to get game_compare stats")
        sys.exit(1)

    mismatches = compare_and_display(espn_stats, gc_stats, game_header, team_order)

    sys.exit(0 if mismatches == 0 else 1)


if __name__ == "__main__":
    main()
