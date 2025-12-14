#!/usr/bin/env python3
"""
Local development server for testing Python APIs.
Run with: python local_server.py
APIs will be available at http://localhost:8000
"""

from dotenv import load_dotenv
load_dotenv('.env.local')

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.lib.game_analysis import analyze_game
from api.lib.ai_summary import generate_ai_summary, get_cached_summary
from api.scoreboard import fetch_scoreboard, build_response

class LocalAPIHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        path = self.path.split('?')[0]

        # Health check
        if path == '/api/health':
            self._send_json({"status": "ok", "server": "local"})
            return

        # Scoreboard
        if path == '/api/scoreboard':
            try:
                raw_data = fetch_scoreboard()
                data = build_response(raw_data)
                self._send_json(data)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        # Game detail
        if path.startswith('/api/game/'):
            game_id = path.split('/')[-1]
            if game_id.isdigit():
                try:
                    payload = analyze_game(game_id)

                    # Generate AI summary
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

                    # Check cache first
                    cached_summary = get_cached_summary(game_id, home_score, away_score)

                    if cached_summary:
                        payload['ai_summary'] = cached_summary
                    else:
                        try:
                            ai_summary = generate_ai_summary(
                                payload=payload,
                                game_data={},
                                probability_map={},
                                wp_threshold=0.975
                            )
                            payload['ai_summary'] = ai_summary
                        except Exception as e:
                            print(f"AI summary generation failed: {e}")
                            payload['ai_summary'] = None

                    self._send_json(payload)
                except Exception as e:
                    self._send_json({"error": str(e), "gameId": game_id}, 500)
                return
            else:
                self._send_json({"error": "Invalid game ID"}, 400)
                return

        # 404
        self._send_json({"error": "Not found"}, 404)

def run(port=8000):
    server = HTTPServer(('localhost', port), LocalAPIHandler)
    print(f"Local API server running at http://localhost:{port}")
    print("Available endpoints:")
    print("  GET /api/health")
    print("  GET /api/scoreboard")
    print("  GET /api/game/<gameId>")
    print("\nPress Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()

if __name__ == '__main__':
    run()
