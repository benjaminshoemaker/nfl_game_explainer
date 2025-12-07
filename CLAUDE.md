# NFL Game Explainer - Project Context

## Overview
Python tool that pulls NFL play-by-play data from ESPN and generates advanced analytics reports including success rate, explosive plays, turnovers, finishing drives, and win probability analysis.

## Project Structure
- `game_compare.py` - Main script for generating game reports
- `dump_plays_wp.py` - Win probability dump utility for debugging
- `debug_pregame_wp.py` - Debug pre-game win probability
- `audit_turnovers.py` - Turnover auditing utility
- `validate_game_stats.py` - Validation script for game statistics
- `tests/` - pytest test suite

## Key Commands
```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install pandas requests

# Run main report
python game_compare.py <game_id>
python game_compare.py <game_id> --expanded  # detailed play-by-play

# Debug utilities
python dump_plays_wp.py <game_id>

# Tests
pytest tests/
```

## Data Sources
- ESPN play-by-play: `cdn.espn.com/core/nfl/playbyplay`
- Win probabilities: `sports.core.api.espn.com/v2/.../probabilities`
- Pre-game WP: ESPN `winprobability` array on summary endpoint

## Output Files
Generated files go to `game_summaries/` folder:
- `{away}_at_{home}_{date}_{id}_advanced.csv` - Advanced stats
- `{away}_at_{home}_{date}_{id}_expanded.json` - Detailed play data
- `{away}_at_{home}_{date}_{id}.html` - HTML report

Root-level generated files:
- `game_stats.csv` - General stats output
- `plays_wp_*.csv` - Win probability dumps

## Reference Files
- `sample_games.txt` - Sample ESPN game IDs for testing
- `documentation.txt` - Stat definitions
- `FAQ.txt` - Frequently asked questions
- `TODOS.txt` - Project todo list
- `LLM_research.txt` - Research notes

## Key Metrics
- Success rate (scrambles/sacks count as passes)
- Explosive plays (10+ yards)
- Points per trip inside opponent 40
- Average starting field position
- Per-play win probability deltas
