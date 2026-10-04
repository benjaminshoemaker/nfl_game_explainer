# NFL Game Explainer

NFL Game Explainer is a live Next.js dashboard and Python analysis toolkit that
uses ESPN play-by-play data to explain why an NFL game unfolded the way it did.
It tracks efficiency, explosives, turnovers, field position, finishing drives,
and win-probability swings.

Production: [https://windelta.app](https://windelta.app)

## Architecture

- `src/`: Next.js App Router dashboard, game directory, detail pages, filters,
  sidebar navigation, and active-game refresh.
- `api/`: Vercel Python functions for the scoreboard and full game analysis.
- `api/lib/nfl_core.py`: shared stat definitions and analytics logic.
- `game_compare.py`: original CLI report generator, retained for local analysis.
- `tests/` and `src/**/*.test.*`: Python and frontend regression suites.

The application has no database or authentication layer. ESPN is the reference
for official box-score statistics, and OpenAI summaries are optional. The
dashboard's "Turnovers" row is intentionally broader than ESPN's official
turnover total: it also counts a kicking-team onside recovery against the
receiving team, as its tooltip explains.
Analysis outputs distinguish ESPN's full-game "Official Yards Per Play" from
the app's "Adjusted Yards Per Play" based on selected offensive snaps.
For completed games, full-game Total Yards and Turnovers use ESPN's box score
(with the onside-recovery addition); competitive-play metrics remain calculated
from the available plays. If ESPN's play feed cannot reproduce a final box-score
total or official offensive-play count, the game page shows a source-gap notice.
A matching yard total alone does not prove every snap is present. The underlying calculation is
retained in debug output and the season reconciliation report.

## Debugging a game

Add `?debug=true` to a game URL, for example
`/game/401772891?debug=true`. The debug view shows every calculated stat,
the source plays and their contributions to calculation counters, and the
underlying ESPN game and win-probability responses. The corresponding JSON is
available at `/api/game/401772891?debug=true`. Debug data is fetched only when
requested; the regular game view and API response remain smaller.

The source-play table uses the full-game calculation pass and marks whether a
play passes the competitive win-probability filter. Score comes from ESPN's
game header, penalty totals from its box score, and non-offensive points from
scoring plays.

## Local setup

Requirements:

- Node.js 20.19 or newer
- Python 3.12 or newer
- Vercel CLI for production-like local routing

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
cp .env.example .env.local
```

For the complete local web stack:

```bash
vercel dev
```

For frontend development without Vercel, run both servers:

```bash
python local_server.py
npm run dev
```

The Next.js development server proxies `/api/*` to the Python server on port
8000.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | No | Enables AI-generated game summaries. |
| `OPENAI_MODEL` | No | Summary model; defaults to `gpt-4o-mini`. |
| `VERCEL_URL` | Automatic | Provided by Vercel and used for server-side API routing. |

AI summaries use Vercel's ephemeral `/tmp` storage. That is a warm-instance
optimization rather than durable storage.

## Verification

Run the same checks used by CI:

```bash
.venv/bin/python -m pytest tests/ -q
npm run test
npm run typecheck
npm run lint
npm run build
npm audit
```

GitHub Actions runs the Python and Node suites for pushes to `main` and pull
requests. Vercel deploys production from `main`.

## CLI analysis

An ESPN game ID can be copied from the game URL:

```bash
source .venv/bin/activate
python game_compare.py <game_id>
python game_compare.py <game_id> --expanded
python dump_plays_wp.py <game_id>
```

Generated CSV, JSON, and HTML reports are written to `game_summaries/`, which
is gitignored. Detailed metric definitions are maintained in
`documentation.txt` and `FAQ.txt`.

## Play EPA

The [2026 Week 3 ESPN EPA validation](EPA_GOAL.md) compares ESPN-derived
play-level EPA with nflverse across 10 development games and 6 held-out games,
including the Seahawks and Rams games. Offense, special teams, penalties,
kneels, spikes, and two-point tries each exceeded 95% play coverage and 95%
agreement within ±0.25 EPA in both samples. The
[initial feasibility check](EPA_WEEK3_FEASIBILITY_2026-09-30.md) records the
earlier restricted prototype. The game API now estimates play EPA from ESPN
play states with the bundled, checksum-pinned nflfastR expected-points model
and a field-goal baseline trained on 2025 reference data. A live play may
have no EPA until the next possession state arrives; unsupported or missing
states stay null. The benchmark covers completed games; in-game latency and
overtime EPA remain unvalidated.

## Data and cache behavior

- Active games refresh every 60 seconds in the browser.
- API and server-rendered scoreboard responses revalidate every 30 seconds.
- AI summaries are keyed by game ID and score and expire after 24 hours.
- ESPN endpoints are public and require no API key.

`api/lib/cache.py` contains an unconnected persistent-cache prototype. It is
deliberately not enabled: its current schema does not preserve competitive and
full-game stat variants separately. Persistent caching should be reconsidered
only after that schema is corrected and repeated ESPN fetch volume justifies an
additional managed service.
