from http.server import BaseHTTPRequestHandler
import json
import sys
import os

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.game_analysis import analyze_game


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
