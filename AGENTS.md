# AGENTS.md

Guidance for AI agents working with this repository. User-facing setup/usage lives in `README.md`; keep stat definitions aligned with `documentation.txt` and `FAQ.txt`.

## Quick Orientation

- **Python analysis**: `game_compare.py` (main analysis), `dump_plays_wp.py` (WP dump)
- **Live dashboard**: Next.js app at project root, Python APIs in `api/` directory
- **Implementation plan**: `IMPLEMENTATION_PLAN.md` contains the phased build plan
- **Outputs**: `game_summaries/` (gitignored) for static HTML reports
- **Sample data**: `sample_games.txt` has known ESPN IDs, `pbp_cache/` has cached API responses

## Project Overview

NFL Game Explainer is a Python tool that fetches NFL game data from ESPN APIs and produces advanced analytics reports. It calculates efficiency metrics (success rate, explosive plays, yards per play), tracks turnovers, and computes win probability deltas for key plays.

**Live Dashboard** (in development): A Next.js frontend with Python serverless API routes, deployed on Vercel. Features:
- Auto-refresh every 60 seconds for active games
- Directory page showing all games for current NFL week
- Game detail pages with sidebar navigation
- AI-generated game summaries (cached by score)

## Architecture

### Python Analysis Layer (existing)

**game_compare.py** - Main module containing:
- `get_game_data(game_id)` - Fetches play-by-play JSON from ESPN core API
- `get_pregame_probabilities(game_id)` - Fetches pre-game win probability
- `get_play_probabilities(game_id)` - Fetches win probability data (paginated)
- `process_game_stats(...)` - Core analysis engine
- `generate_game_summary(...)` - AI summary generation via OpenAI
- `classify_offense_play(play)` - Play classification for stats

**dump_plays_wp.py** - Debug utility for WP tracking

**templates/game_summary_template.html** - Static HTML template

### Live Dashboard Layer (new)

```
Project Root/
├── src/                    # Next.js frontend
│   ├── app/               # App router pages
│   │   ├── page.tsx       # Directory (home)
│   │   └── game/[gameId]/ # Game detail
│   ├── components/        # React components
│   ├── hooks/             # Custom hooks (auto-refresh)
│   ├── lib/               # Utilities (API client, team colors)
│   └── types/             # TypeScript definitions
├── api/                    # Python serverless functions (Vercel)
│   ├── health.py          # Health check
│   ├── scoreboard.py      # All games for current week
│   ├── game/[gameId].py   # Full game analysis
│   └── lib/               # Shared Python modules
│       └── game_analysis.py  # Ported from game_compare.py
├── game_compare.py         # Original CLI tool (preserved)
└── vercel.json            # Vercel configuration
```

## Commands

```bash
# === Python Analysis (original) ===
source .venv/bin/activate
python3 game_compare.py <game_id>
python3 game_compare.py <game_id> --expanded
python3 dump_plays_wp.py <game_id>
pytest tests/

# === Live Dashboard (new) ===
npm install
npm run dev          # Start Next.js dev server
npm run build        # Production build
npm run test         # Run Jest/Vitest tests
npm run typecheck    # TypeScript check
npm run lint         # ESLint

# === Vercel ===
vercel dev           # Local dev with Python functions
vercel deploy        # Deploy to Vercel
```

## Data Flow

### Static Analysis (CLI)
1. ESPN game ID → `get_game_data()` → play-by-play JSON
2. ESPN game ID → `get_play_probabilities()` → WP data
3. `process_game_stats()` → computed stats
4. Output to `game_summaries/{away}_at_{home}_{date}_{id}.[csv|json|html]`

### Live Dashboard (API)
1. Browser loads directory page
2. `/api/scoreboard` → all games for current week
3. Click game → `/api/game/{gameId}` → full analysis JSON
4. Client renders with React components
5. Active games auto-refresh every 60 seconds
6. AI summary generated on score change (cached)

---

## Implementation Plan Execution

The `IMPLEMENTATION_PLAN.md` file contains a phased build plan with 18 steps across 5 phases. When executing this plan:

### Step Execution Protocol

For each step in the implementation plan:

1. **Read the step** - Understand what needs to be built
2. **Implement** - Write the code following the step's instructions
3. **Verify** - Use the code-verification skill (`.claude/skills/code-verification/SKILL.md`) to verify all checklist items
4. **Test** - Run relevant tests and manual verification
5. **Mark complete** - Check off items in the implementation plan
6. **Commit** - Commit with descriptive message before moving to next step

### Checklist Management

- After completing any step, **immediately update the corresponding TODO checklist** in `IMPLEMENTATION_PLAN.md`
- Use Markdown checkbox format (`- [x]`) to mark completion
- Do not consider a step "done" until ALL checklist items are verified
- Commit the updated plan file alongside the code

### Verification Protocol

Use the code-verification skill for each step:

1. Parse the step's checklist into verification instructions
2. For each instruction:
   - Sub-agent verifies if instruction is met
   - If failed: attempt fix (up to 5 times)
   - Log all attempts
3. Generate verification report
4. Only proceed to next step when all pass or are explicitly deferred

### Context Management

**Starting a new step**: Begin with fresh context. Load:
1. `AGENTS.md` (this file)
2. Current step's section from `IMPLEMENTATION_PLAN.md`
3. Relevant source files as needed

**Within a step**: Keep context while debugging/iterating. Only clear when moving to next step.

**Resuming after a break**:
1. Start fresh conversation
2. Load AGENTS.md
3. Check IMPLEMENTATION_PLAN.md to find current step
4. Run tests to verify state
5. Continue from first unchecked step

---

## Testing Policy (non-negotiable)

### Core Rules
- Tests **MUST** cover the functionality being implemented
- **NEVER** ignore test output—logs contain critical information
- **NEVER** disable functionality to hide a failure—fix root cause
- **TEST OUTPUT MUST BE PRISTINE TO PASS**

### What "Green Tests" Means

For Python:
- `pytest tests/` passes

For Next.js:
- `npm run test` passes
- `npm run typecheck` passes (no TypeScript errors)
- `npm run lint` passes (no ESLint errors)
- `npm run build` succeeds

A step is not complete until all relevant checks pass.

### TDD Workflow
1. Write a failing test
2. Run test to confirm failure
3. Write minimal code to pass
4. Run test to confirm success
5. Refactor while keeping tests green
6. Repeat

### Mocking Requirements
- **NEVER** make real OpenAI API calls in tests—always mock
- **NEVER** make real ESPN API calls in unit tests—use cached fixtures
- Integration tests may use real ESPN API (free, no key needed)
- Use temp directories for file system tests

---

## Key Implementation Details

### Python
- Scrambles and sacks are treated as pass dropbacks (not runs)
- Turnovers detected via text parsing ("interception", "fumble" + "recovered by")
- Win probability deltas computed by tracking previous play's WP
- Competitive time filter: WP < 97.5% (configurable via `--wp-threshold`)

### Next.js / TypeScript
- Use App Router (not Pages Router)
- Server components for initial data fetch
- Client components ("use client") for interactivity
- Team colors in `src/lib/teamColors.ts`
- Auto-refresh via custom hook, only for active games

### Vercel
- Python functions in `api/` directory
- Use Vercel's Python runtime (python3.12)
- Environment variables: `OPENAI_API_KEY`
- AI summaries cached by `{gameId}_{homeScore}_{awayScore}`

---

## Important Checks

- **NEVER** disable functionality to hide a failure—fix root cause
- **NEVER** create duplicate templates or files—fix the original
- **NEVER** claim something is "working" when any functionality is broken
- If you can't open a file or access something, say so—do not assume contents
- **ALWAYS** identify and fix root cause of errors
- Ensure `.gitignore` contains:
  ```
  .env
  .env.local
  .env.*
  node_modules/
  .next/
  .vercel/
  __pycache__/
  *.pyc
  game_summaries/
  ```

---

## When to Ask for Human Input

Ask the human if any of the following is true:
- You need new environment variables or secrets (especially `OPENAI_API_KEY`)
- ESPN API structure has changed and you can't parse responses
- A test is failing and you cannot determine why after reading full error output
- You need to deploy to Vercel (requires human to configure dashboard)
- Manual browser testing is needed to verify UI behavior
- You're unsure whether a design choice matches the existing template aesthetic

---

## Commit Messages

Format: `<scope>: <description>`

| Scope | Use |
|-------|-----|
| `feat` | New functionality |
| `fix` | Bug fix |
| `test` | Test additions/changes |
| `refactor` | Code restructuring |
| `docs` | Documentation |
| `chore` | Build/tooling changes |
| `style` | UI/styling changes |

Examples:
- `feat(api): add scoreboard endpoint`
- `feat(ui): build Scoreboard component`
- `fix(api): handle missing WP data gracefully`
- `test(components): add StatRow unit tests`
