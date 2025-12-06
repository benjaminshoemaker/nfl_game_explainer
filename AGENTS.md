# CLAUDE.md

This file provides guidance to AI Agents when working with code in this repository.

## Project Overview

NFL Game Explainer is a Python tool that fetches NFL game data from ESPN APIs and produces advanced analytics reports. It calculates efficiency metrics (success rate, explosive plays, yards per play), tracks turnovers, and computes win probability deltas for key plays. Output includes CSV, JSON, and HTML reports.

## Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Run main analysis on a game (requires ESPN game ID from URL)
python game_compare.py <game_id>
python game_compare.py <game_id> --expanded  # Show detailed play-by-play

# Dump all plays with win probability data
python dump_plays_wp.py <game_id>

# Run tests
pytest tests/
pytest tests/test_game_compare.py -v  # Verbose single test file
```

## Architecture

**game_compare.py** - Main module containing:
- `get_game_data(game_id)` - Fetches play-by-play JSON from ESPN core API
- `get_play_probabilities(game_id)` - Fetches win probability data from ESPN v2 API (paginated)
- `process_game_stats(game_data, expanded, probability_map)` - Core analysis engine that iterates through drives/plays to compute:
  - Success rate (40%/60%/100% thresholds by down)
  - Explosive plays (10+ yard runs, 20+ yard passes)
  - Turnovers, field position, points per trip inside 40
  - Win probability deltas per play
- `classify_offense_play(play)` - Determines if a play counts toward offensive stats (excludes penalties, spikes, kneels, special teams)
- `main()` - CLI entry point, writes output to `game_summaries/` directory

**dump_plays_wp.py** - Utility script that prints every play with win probability and delta values for debugging WP tracking.

**templates/game_summary_template.html** - HTML template that gets `__GAME_DATA_JSON__` replaced with analysis payload.

## Data Flow

1. ESPN game ID → `get_game_data()` fetches play-by-play from `cdn.espn.com/core/nfl/playbyplay`
2. Same ID → `get_play_probabilities()` fetches WP from `sports.core.api.espn.com/v2/.../probabilities`
3. `process_game_stats()` iterates drives/plays, classifies each play, accumulates stats
4. Output written to `game_summaries/` as `{away}_at_{home}_{date}_{id}.[csv|json|html]`

## Key Implementation Details

- Scrambles and sacks are treated as pass dropbacks (not runs) for efficiency calculations
- Turnovers detected via text parsing ("interception", "fumble" + "recovered by" logic)
- Win probability deltas computed by tracking previous play's WP values
- Special teams net yards calculated from field position coordinates when available

## Testing policy (non‑negotiable)
- Tests **MUST** cover the functionality being implemented.
- **NEVER** ignore the output of the system or the tests - logs and messages often contain **CRITICAL** information.
- **TEST OUTPUT MUST BE PRISTINE TO PASS.**
- If logs are **supposed** to contain errors, capture and test it.
- **NO EXCEPTIONS POLICY:** Under no circumstances should you mark any test type as "not applicable". Every project, regardless of size or complexity, **MUST** have unit tests, integration tests, **AND** end‑to‑end tests. If you believe a test type doesn't apply, you need the human to say exactly **"I AUTHORIZE YOU TO SKIP WRITING TESTS THIS TIME"**.

### TDD (how we work)
- Write tests **before** implementation.
- Only write enough code to make the failing test pass.
- Refactor continuously while keeping tests green.

**TDD cycle**
1. Write a failing test that defines a desired function or improvement.  
2. Run the test to confirm it fails as expected.  
3. Write minimal code to make the test pass.  
4. Run the test to confirm success.  
5. Refactor while keeping tests green.  
6. Repeat for each new feature or bugfix.

---

## Important checks
- **NEVER** disable functionality to hide a failure. Fix root cause.  
- **NEVER** create duplicate templates or files. Fix the original.  
- **NEVER** claim something is “working” when any functionality is disabled or broken.  
- If you can’t open a file or access something requested, say so. Do not assume contents.  
- **ALWAYS** identify and fix the root cause of template or compilation errors.  
- If git is initialized, ensure a '.gitignore' exists and contains at least:
  
  .env
  .env.local
  .env.*
  
  Ask the human whether additional patterns should be added, and suggest any that you think are important given the project. 

