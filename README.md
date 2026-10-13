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

To run the Python test suite, install its additional benchmark dependencies with
`pip install -r requirements-test.txt`.

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
| `OPENAI_MODEL` | No | Summary model; defaults to `gpt-5.6-luna`. |
| `VERCEL_URL` | Automatic | Provided by Vercel and used for server-side API routing. |

AI summaries use Vercel's ephemeral `/tmp` storage. That is a warm-instance
optimization rather than durable storage.

The game story briefly explains the score through the few most relevant factor
comparisons. It can mention an unusually decisive play. The model also receives
completed-game gap references and measured WP/EPA play candidates; live or
unresolved measurements are identified in its input.

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

## Team-season data and audit

The team-season foundation produces exact full-game aggregates for all eight
factors, with own/opponent/net views, coverage, and qualified-team ranks. It
does not yet publish a predictive power rating or add public team pages.
Accepted scope and remaining work are in [TEAM_SEASON_PLAN.md](TEAM_SEASON_PLAN.md).

Build a completed season (network access is explicit):

```bash
PYTHONPATH=. .venv/bin/python research/build_team_seasons.py --season 2025 --fetch-missing
```

Use `--through-week 3` for a season-to-date cutoff. Without `--fetch-missing`,
the builder uses saved schedules and game payloads. It checks both calendar
years so January games are assigned to the correct NFL season. Missing games
remain in the coverage denominator. Outputs, source snapshots, weekly
recalculations, and checksum manifests live in `game_summaries/team_seasons/`.

Independently compare efficiency factors with a locally saved nflverse parquet
file (requires `requirements-test.txt` or the research dependencies):

```bash
PYTHONPATH=. .venv/bin/python research/audit_team_seasons.py \
  --games game_summaries/team_seasons/2025-week-18-games.json \
  --reference /path/to/play_by_play_2025.parquet \
  --output game_summaries/team_seasons/2025-independent-audit.json
PYTHONPATH=. .venv/bin/python research/build_team_seasons.py --season 2025 \
  --independent-audit game_summaries/team_seasons/2025-independent-audit.json
```

The second build verifies the audit's input hash and withholds disputed
efficiency factors from ranks without replacing ESPN values. An audit from a
different source snapshot is rejected. No OpenAI calls, odds, market rankings,
or pregame win probabilities are used by these commands.

### nflverse season analysis and review prototype

nflverse is the selected season-analysis source. The ESPN builder remains an
independent comparison path; the new adapter does not blend the two sources.

```bash
PYTHONPATH=. .venv/bin/python research/build_nflverse_seasons.py --seasons 2024 2025 2026 --fetch
.venv/bin/python research/render_team_prototype.py
```

The builder uses existing `/tmp/nfl_game_explainer_pbp_{season}.parquet` files
when available; override with `--pbp-pattern`. `--fetch` downloads missing
inputs only. Checksums, audit summaries, game records, and weekly snapshots
are written under `game_summaries/nflverse/`. Open
`game_summaries/nflverse/team-seasons-review.html` for the portable interactive
prototype. It includes team pages, a metric scatterplot, and multi-team radar
comparisons. No predictive rating has been fitted or published yet.

### Predictive research experiment

Build nflverse snapshots for every season from 2011 through 2026, then run:

```bash
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 .venv/bin/python research/team_power_model.py
.venv/bin/python research/render_team_prototype.py
```

`game_summaries/nflverse/model/REPORT.md` summarizes the experiment. Its siblings
contain the frozen protocol and input hashes, validation candidates, held-out
predictions, calibration bins, season/early-late splits, and experimental team
ratings with additive factor contributions. The review prototype embeds the
results when available. Research dependencies are in `research/requirements.txt`.
The initial evaluation does not demonstrate an advantage over point-differential
baselines. Experimental rankings are saved for analysis, not published on team
pages. FPI/DVOA benchmarking remains outstanding.

### Second-round predictive experiments

```bash
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 .venv/bin/python research/team_power_experiments.py
```

This preserves the first experiment and writes `game_summaries/nflverse/model-v2/`.
`REPORT.md` compares smaller factor sets, point differential plus factors,
separate production/prevention, stabilization, and recency. `protocol.json`
records the search before fitting; phase selections and `locked-selection.json`
precede follow-up evaluation. Full candidate results and game-level predictions
are retained. The 2024–2025 sample is explicitly an already-inspected follow-up,
not a new untouched test. No production ratings or game-highlight weights change.

Extended research (active, experimental):

```bash
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 .venv/bin/python research/team_power_extended_data.py
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/team_power_flexible.py
```

Artifacts are under `game_summaries/nflverse/model-v3/`. The builder requires the
checksum-recorded local 2011–2025 PBP files. Extended measurements and schedule
context exclude odds, WP, actual starting-QB labels, and actual game weather.
This search has not established a publishable predictive advantage.

Nested chronological replay:

```bash
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/team_power_nested.py
```

Requires the round-three feature matrix and candidate protocol. Writes
`game_summaries/nflverse/model-v4-nested/`, including each season's selected
settings, per-game predictions, and paired season-block uncertainty. This uses
only prior seasons for settings selection but remains retrospective development
because candidate families were designed after inspecting recent outcomes.

The completed predictive research summary is
`game_summaries/nflverse/model-v7-audit/FINDINGS.md`. Reproduce its final audit with:

```bash
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/team_power_final_audit.py
```

The frozen margin model is `model-v7-audit/frozen-margin-model.json`; use the
recorded adjusted features, not raw game-stat differences. Historical gains are
modest, retrospective, and not a claim of prospective or FPI/DVOA superiority.

### Experimental power-rating review

The season review now includes 32-team ratings in points relative to league
average, team contribution breakdowns, a neutral matchup comparison, and a
power-rating axis alongside the observed-factor charts. Its prediction target
is upcoming-game scoring margin; it does not forecast final season records.
The frozen model is preserved in `research/models/frozen-margin-model.json`.

With the audited season snapshots and local nflverse PBP files available:

```bash
PYTHONPATH=. .venv/bin/python research/team_power_ratings.py --season 2026 --through-week 3
PYTHONPATH=. .venv/bin/python research/render_team_prototype.py
python3 -m http.server 8767 --bind 127.0.0.1
```

Open `/game_summaries/nflverse/team-seasons-review.html#power`. The generated
review is a dated retrospective snapshot, not a live ranking or pregame archive.
The final coefficients are intentionally unavailable on pre-2026 team pages.

The team review's schedule measure ranks `1 = hardest` using venue-adjusted
scoring strength with the focal team's current-season games excluded. Its
current/prior evidence breakdown sums exactly to the factor/scoring rating,
with multi-season QB history shown separately. These displays do not change
the frozen model. Reproduce the bounded schedule-model audit with:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python research/team_schedule_audit.py
```

Read `game_summaries/nflverse/model-v8-schedule/REPORT.md` or Prediction results
in the review. The alternatives did not pass the promotion gate; the model
remains unchanged. All historical audit years were already inspected.

### Weekly ratings and pregame archive

Refresh the completed regular-season cutoff, archive the inputs, save next-week
predictions from both frozen models, score earlier pregame forecasts, and rebuild
the review with one command:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python research/weekly_team_ratings.py
```

The 2026 protocol uses `research/models/frozen-margin-model.json` and
`research/models/frozen-point-baseline.json`; updates never refit either model.
The baseline was exported once with `research/freeze_point_baseline.py` using the
previously established Ridge-10 adjusted-point comparator and 2012–2025 data.
The command requires the audited 2011–2025 season JSON and the original training
reference matrix already present under `game_summaries/nflverse/`. It downloads
fresh nflverse schedule, team, and three-season QB/PBP source snapshots.

Each run has a unique `game_summaries/nflverse/weekly-archive/<timestamp>/`
directory with source files, season ratings, game feature values, predictions,
both model formulas, code copies, checksums, coverage, and evaluation. Successful
weekly publications also include `review.html`. Existing archives are never
rewritten by the updater; integrity checks reject changed files. These are local
records, not an externally certified publication or off-machine backup.
`weekly-latest.json` points to the last successful run. Missing scheduled games,
scoring mismatches, source failures, or a missed target-week kickoff prevent a new
publication. `weekly-status.json` exposes the failure; the review retains the last
successful cutoff. Factor-specific ambiguities remain excluded under the existing
metric policy and are displayed explicitly. Previous review HTML is retained in
`review-history/`; all earlier season JSON remains intact.

Run the weekly command after the final game and before the following week's first
kickoff. Kickoffs use US Eastern with daylight-saving time. It only publishes full
completed weeks, and refuses to silently reuse the 2026 protocol in another season.
The first sealed pregame forecast per game is used for prospective scoring;
subsequent corrected-source publications do not replace that original forecast.
Closing spreads are read only during evaluation, with positive `spread_line`
meaning a home-favored scoring margin. Both models and closing spreads are compared
on identical completed games with available lines. Tied outcomes are excluded from
winner accuracy. No betting-return or market-superiority claim follows from these
margin-error metrics.

For an explicit historical replay (which is excluded from prospective scoring):

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python research/weekly_team_ratings.py --replay-week 5
```

A replay may use corrected sources downloaded after kickoff, but model inputs
stop at the preceding week's games. It does not update the current publication.
Use `PYTHONPATH=. .venv/bin/python research/render_team_prototype.py` to regenerate
the main review from the latest successful snapshot and display newly added replays.

### Publish the team pages

The production routes `/teams`, `/teams/BUF`, `/power-rankings`,
`/prediction-results`, and `/team-methodology` serve the reviewed season interface.
The game directory links to Teams and Power rankings. These are dated publications;
model caveats and source quality exclusions remain visible.

After a successful weekly refresh, export the public bundle before deployment:

```bash
PYTHONPATH=. .venv/bin/python research/publish_team_site.py
npm run build
```

The exporter verifies the source archive checksums and writes
`public/team-seasons.html` and a whitelist of public forecasts, frozen formulas,
results, reports, sanitized provenance, and checksums in `public/team-data/`.
It never includes raw PBP/CSV inputs or code snapshots. Keep previous public
archive files in subsequent deployments. `public/team-data/publication.json`
identifies the published cutoff and model. Publishing requires deploying the
updated bundle; the local weekly refresh alone does not update the website.
