# NFL Game Explainer

Python tool that pulls NFL play-by-play data from ESPN and turns it into advanced analytics reports. It calculates success rate, explosive plays, turnovers, finishing drives, and win probability deltas so you can quickly see why a team won.

## Quick Start
- Prereqs: Python 3, `pip`; dependencies are `pandas` and `requests`.
- Setup:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install pandas requests
  ```
- Run the main report (ESPN game ID comes from the game URL):
  ```bash
  python game_compare.py <game_id>
  python game_compare.py <game_id> --expanded  # includes detailed play-by-play output
  ```
- Win probability dump for debugging:
  ```bash
  python dump_plays_wp.py <game_id>
  ```
- Outputs: CSV, JSON, and HTML files land in `game_summaries/` (gitignored) as `{away}_at_{home}_{date}_{id}.*`.

## What It Measures
- Efficiency: yards per play and success rate (scrambles/sacks count as passes).
- Explosiveness: explosive play counts and rates (10+ yards).
- Finishing drives: points per trip inside the opponent 40.
- Turnovers and non-offensive points.
- Average starting field position, penalty yards, possessions, and per-play win probability deltas (ESPN v2 probabilities feed).

## Data Flow
1. `get_game_data(game_id)` pulls play-by-play from `cdn.espn.com/core/nfl/playbyplay`.
2. `get_play_probabilities(game_id)` pulls win probabilities from `sports.core.api.espn.com/v2/.../probabilities`.
3. `process_game_stats(...)` iterates drives/plays to compute metrics and render CSV/JSON/HTML reports.

## Development Notes
- Activate the virtualenv before running scripts: `source .venv/bin/activate`.
- Sample IDs for quick runs live in `sample_games.txt`; expanded stat definitions are in `documentation.txt` and `FAQ.txt`.
- Tests: `pytest tests/` or `pytest tests/test_game_compare.py -v`.
