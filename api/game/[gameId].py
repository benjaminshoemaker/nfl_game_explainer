from http.server import BaseHTTPRequestHandler
import json
import sys
import os

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.game_analysis import analyze_game
from lib.ai_summary import generate_ai_summary, get_cached_summary


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Extract gameId from the path
        # Path will be like /api/game/401772896
        path_parts = self.path.split('/')
        game_id = None

        for i, part in enumerate(path_parts):
            if part == 'game' and i + 1 < len(path_parts):
                # Get the next part, removing query params if present
                game_id = path_parts[i + 1].split('?')[0]
                break

        if not game_id or not game_id.isdigit():
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Invalid game ID",
                "message": "Game ID must be a numeric value"
            }).encode())
            return

        try:
            # Analyze the game
            payload = analyze_game(game_id)

            # Get scores for cache lookup
            summary_table = payload.get('summary_table', [])
            team_meta = payload.get('team_meta', [])

            home_team = next((t for t in team_meta if t['homeAway'] == 'home'), None)
            away_team = next((t for t in team_meta if t['homeAway'] == 'away'), None)

            home_score = 0
            away_score = 0

            if home_team and away_team:
                home_summary = next((s for s in summary_table if s['Team'] == home_team['abbr']), {})
                away_summary = next((s for s in summary_table if s['Team'] == away_team['abbr']), {})
                home_score = home_summary.get('Score', 0)
                away_score = away_summary.get('Score', 0)

            # Check for cached AI summary first
            cached_summary = get_cached_summary(game_id, home_score, away_score)

            if cached_summary:
                payload['ai_summary'] = cached_summary
            else:
                # Try to generate AI summary (will fail gracefully if no API key)
                try:
                    ai_summary = generate_ai_summary(
                        payload=payload,
                        game_data={},  # Raw data not needed for basic summary
                        probability_map={},  # Probability data not needed for basic summary
                        wp_threshold=0.975
                    )
                    payload['ai_summary'] = ai_summary
                except Exception as e:
                    # AI summary generation failed, continue without it
                    print(f"AI summary generation failed: {e}")
                    payload['ai_summary'] = None

            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'public, max-age=30')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Failed to analyze game",
                "message": str(e),
                "gameId": game_id
            }).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
