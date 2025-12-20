from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error
import gzip
from urllib.parse import urlparse, parse_qs


ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

ESPN_REQUEST_HEADERS = {
    # ESPN frequently blocks/behaves differently for non-browser UAs.
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.espn.com/",
    "Origin": "https://www.espn.com",
}

# Playoff week labels
PLAYOFF_LABELS = {
    1: "Wild Card",
    2: "Divisional Round",
    3: "Conference Championship",
    5: "Super Bowl"  # Week 4 is Pro Bowl, skip it
}


def _decompress_response(data):
    """Decompress gzip data if needed, return raw data otherwise."""
    if data[:2] == b'\x1f\x8b':  # gzip magic bytes
        return gzip.decompress(data)
    return data


def fetch_scoreboard(week=None, seasontype=None):
    """Fetch NFL scoreboard from ESPN API with optional week/seasontype filters."""
    url = ESPN_SCOREBOARD_URL
    params = []

    # Note: Don't pass 'season' param - ESPN API errors with explicit season but defaults to current season
    if seasontype is not None:
        params.append(f"seasontype={seasontype}")
    if week is not None:
        params.append(f"week={week}")

    if params:
        url += "?" + "&".join(params)

    try:
        req = urllib.request.Request(url, headers=ESPN_REQUEST_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as response:
            raw_data = _decompress_response(response.read())
            return json.loads(raw_data.decode())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        return {"error": str(e)}


def transform_game(event):
    """Transform ESPN event data to our response format."""
    competition = event.get("competitions", [{}])[0]
    status = event.get("status", {})
    status_type = status.get("type", {})

    # Get competitors (home and away teams)
    competitors = competition.get("competitors", [])
    home_team = None
    away_team = None

    for comp in competitors:
        team_data = {
            "abbr": comp.get("team", {}).get("abbreviation", ""),
            "name": comp.get("team", {}).get("displayName", ""),
            "score": int(comp.get("score", 0) or 0),
            "logo": comp.get("team", {}).get("logo", ""),
            "id": comp.get("team", {}).get("id", "")
        }
        if comp.get("homeAway") == "home":
            home_team = team_data
        else:
            away_team = team_data

    # Determine game status
    state = status_type.get("state", "pre")
    if state == "in":
        game_status = "in-progress"
    elif state == "post":
        game_status = "final"
    else:
        game_status = "pregame"

    # Get status detail (quarter/time or "Final")
    status_detail = status_type.get("shortDetail", "")

    # Get start time for pregame
    start_time = event.get("date") if game_status == "pregame" else None

    return {
        "gameId": event.get("id", ""),
        "status": game_status,
        "statusDetail": status_detail,
        "homeTeam": home_team,
        "awayTeam": away_team,
        "startTime": start_time,
        "isActive": state == "in"
    }


def get_week_label(week_number, season_type):
    """Return appropriate label for the week."""
    if season_type == 3:  # Postseason
        return PLAYOFF_LABELS.get(week_number, f"Playoff Week {week_number}")
    return f"Week {week_number}"


def build_response(data):
    """Build the full scoreboard response."""
    if "error" in data:
        return {
            "week": {"number": 0, "label": "Unknown", "seasonType": 2},
            "games": [],
            "error": data["error"]
        }

    week_data = data.get("week", {})
    season_data = data.get("season", {})
    events = data.get("events", [])

    # Get season type (1=preseason, 2=regular, 3=postseason)
    season_type = season_data.get("type", 2)
    week_number = week_data.get("number", 0)

    games = [transform_game(event) for event in events]

    # Sort: in-progress first, then pregame by time, then final
    def sort_key(game):
        if game["status"] == "in-progress":
            return (0, "")
        elif game["status"] == "pregame":
            return (1, game.get("startTime", ""))
        else:
            return (2, "")

    games.sort(key=sort_key)

    return {
        "week": {
            "number": week_number,
            "label": get_week_label(week_number, season_type),
            "seasonType": season_type
        },
        "games": games
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse query parameters
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        week = query.get('week', [None])[0]
        seasontype = query.get('seasontype', [None])[0]

        # Convert to int if present
        if week is not None:
            try:
                week = int(week)
            except ValueError:
                week = None
            if week is not None and week <= 0:
                week = None
        if seasontype is not None:
            try:
                seasontype = int(seasontype)
            except ValueError:
                seasontype = None

        # Fetch and transform scoreboard data
        raw_data = fetch_scoreboard(week=week, seasontype=seasontype)
        response_data = build_response(raw_data)

        # Send response
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'public, max-age=30')
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
