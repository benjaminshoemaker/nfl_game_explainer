"""Dump all plays from a game with their win probabilities and delta."""
import sys
from game_compare import get_game_data, get_play_probabilities

def main():
    if len(sys.argv) < 2:
        print("Usage: python dump_plays_wp.py <game_id>")
        sys.exit(1)

    game_id = sys.argv[1]
    print(f"Fetching game {game_id}...")

    game_data = get_game_data(game_id)
    prob_map = get_play_probabilities(game_id)

    # Get team info
    comps = game_data.get('header', {}).get('competitions', [])
    home_abbr = away_abbr = "?"
    if comps:
        for comp in comps[0].get('competitors', []):
            abbr = comp.get('team', {}).get('abbreviation', '?')
            if comp.get('homeAway') == 'home':
                home_abbr = abbr
            else:
                away_abbr = abbr

    print(f"\n{away_abbr} @ {home_abbr}")
    print(f"Probabilities: {len(prob_map)} plays have WP data\n")
    print("=" * 120)

    drives = game_data.get('drives', {}).get('previous', [])

    # Track previous WP for delta calculation
    prev_home_wp = 0.5
    prev_away_wp = 0.5

    for drive in drives:
        team_abbr = drive.get('team', {}).get('abbreviation', '?')
        drive_desc = drive.get('description', '')
        print(f"\n--- DRIVE: {team_abbr} - {drive_desc} ---")

        for play in drive.get('plays', []):
            play_id = str(play.get('id', ''))
            quarter = play.get('period', {}).get('number', '?')
            clock = play.get('clock', {}).get('displayValue', '?')
            play_type = play.get('type', {}).get('text', 'Unknown')
            text = play.get('text', '')[:70]  # Truncate for readability

            # Get score at this point
            home_score = play.get('homeScore', '?')
            away_score = play.get('awayScore', '?')

            # Get WP and compute delta
            prob = prob_map.get(play_id)
            if prob:
                home_wp = prob.get('homeWinPercentage', 0.5)
                away_wp = prob.get('awayWinPercentage', 0.5)

                # Compute delta
                home_delta = (home_wp - prev_home_wp) * 100
                away_delta = (away_wp - prev_away_wp) * 100

                # Format delta with sign
                def fmt_delta(d):
                    if abs(d) < 0.05:  # Effectively zero
                        return "  0.0"
                    return f"+{d:5.1f}" if d > 0 else f"{d:6.1f}"

                wp_str = f"{away_abbr} {away_wp*100:5.1f}% ({fmt_delta(away_delta)}) | {home_abbr} {home_wp*100:5.1f}% ({fmt_delta(home_delta)})"

                # Update previous
                prev_home_wp = home_wp
                prev_away_wp = away_wp
            else:
                wp_str = "(no WP data)"

            print(f"Q{quarter} {clock:>5} | {away_abbr} {away_score}-{home_score} {home_abbr} | {wp_str} | {play_type}: {text}")

if __name__ == "__main__":
    main()
