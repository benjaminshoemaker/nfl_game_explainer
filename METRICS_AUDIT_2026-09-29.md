# Metrics and reconciliation audit — 2026-09-29

This is a historical initial audit snapshot, not the current result. See
`METRICS_FOLLOWUP_2026-09-29.md` for the subsequent diagnosis and fresh
272-game rerun (16 mismatch games, 15 yard rows, two turnover rows).

## Verdict

**FAILED: not all calculated numbers reconcile.** The analysis is materially better than the pre-audit version, but it should not yet be described as fully verified. Across all 272 games in the 2025 regular season, 49 games still have at least one Total Yards or Turnovers mismatch against the ESPN box score. The remaining Total Yards differences nearly cancel; their net is not a measure of per-game correctness.

This was an implementation and test-oracle audit, not a validation of whether the chosen factors explain NFL outcomes. No deployment or external data was changed.

## Owner decisions and follow-up

- Use ESPN as the reconciliation reference for official box-score numbers. A subsequent 272-game ESPN/NFL-gamebook check found four single-field yardage or penalty differences; scores and official turnovers matched in all 272. Those source differences do not change the reference choice.
- Keep the seven displayed dashboard rows. Keep the label **Turnovers**, with a tooltip reading "includes onside kick recoveries". This is intentionally broader than ESPN's official giveaways: a kicking-team onside recovery is charged to the receiving team. The season report now compares dashboard turnovers to ESPN official giveaways **plus** this explicit onside adjustment.
- Keep explosive-play thresholds at 10+ yards for runs and 20+ for passes. The follow-up separates ESPN's official full-game YPP from the adjusted play-derived value.
- The original 49-game mismatch count below was rerun after the onside attribution/report change; it remains 49, as documented in the follow-up.

## Data flow and validation boundary

ESPN summary play-by-play and box score → `api/lib/nfl_core.py` → CLI analysis (`game_compare.py`) and serverless API (`api/lib/game_analysis.py`) → dashboard. The season report (`compare_season_games_report.py`) compares calculated full-game totals with the box score **from the same fetched summary payload**. It cannot independently validate ESPN's own totals, the competitive-play split, or subjective factor definitions.

| Number or behavior | Source / calculation | Validation in this audit |
|---|---|---|
| Score | ESPN game header | Source pass-through, not independent |
| Total Yards | Parsed play-by-play | Compared with ESPN team box score, all 2025 regular-season games |
| Turnovers and margin | Parsed interceptions, lost fumbles, muffs, onside recoveries | Giveaways compared with ESPN team box score; margin is derived |
| Penalty Yards | ESPN team box score | Source pass-through; zero delta is circular |
| Yards Per Play, Success Rate, explosive count/rate | Offensive-play classification and yardage | Behavioral edge-case tests; no independent season-wide oracle |
| Points per trip inside 40, average start field position, drives, points per drive | Parsed and normalized drives | Behavioral tests; not independently reconciled |
| Net punting/kickoff, non-offensive points | Parsed special teams and scoring plays | Behavioral tests; not independently reconciled |
| Competitive view | ESPN play win probabilities and configurable threshold | Missing WP now produces an explicitly labeled full-game view; coverage and calibration remain unverified |
| AI summary | Model-generated from calculated full-game facts | Length and selected turnover claims guarded; prose cannot be treated as a verified statistical source |

## Confirmed repairs

- Normalized ESPN's legacy team abbreviations in field-position and recovery parsing. A Browns game previously credited 303 offensive yards versus 187 official; it now reconciles at 187 after the subsequent fumble-yardage corrections.
- Corrected several possession, turnover, and special-teams cases: muffed blocked kicks, sequential fumbles/interception returns, nullified return TDs, score-only return stubs, misassigned post-turnover drives, and fake punts recorded as offensive plays.
- Separated penalty yardage from incomplete-pass offense, and zeroed the fumble yardage loss on aborted snaps while retaining legitimately credited rushing advances. The latter is consistent with the [NFL Guide for Statisticians](https://www.nflgsis.com/gsis/documentation/stadiumguides/guide_for_statisticians.pdf).
- Reconciled accepted penalties enforced at midfield, self-recovered fumbles followed by completed or incomplete passes, one-yard gains written in the singular, and offensive yards on fumbles/laterals through the first-touch or recovery spot. Sack-fumble yardage now follows the recovery spot (including a teammate's advance beyond the line) and reconstructs the line from the stated sack when ESPN's start-spot metadata is contradictory. These are general scoring rules with representative-play regression tests, not game-ID exceptions.
- Made the season report fail on missing weeks or missing box-score fields, default to current network data and regular-season games, and extract its comparison values from the same raw payload as the calculation. It no longer silently treats placeholder games or missing values as matches. Recommendation output uses the same raw snapshot.
- Made an unavailable WP feed explicit rather than labeling full-game totals “competitive.” Failed pagination no longer yields a partial WP map.
- Versioned the AI-summary cache by supplied facts rather than score alone, corrected giveaway/takeaway labeling in the prompt, and rejected empty, over-length, or contradicted numeric turnover summaries. This is a guardrail, not a guarantee against hallucination.
- Removed the debug-game picker's incomplete React effect-dependency warning while preserving its selected-week behavior.
- Removed unverified “95%+ of outcomes” and “winning 5+ of 8 almost always wins” claims from `documentation.txt`; factor-count and definition choices remain open.
- Added tests for representative plays and failure behavior instead of relying only on mocked season-level equality.

## Full-season result

Command: `python3 compare_season_games_report.py --season 2025 --season-types 2 --source network`

| Measure | Pre-audit run | Initial post-repair run (superseded) |
|---|---:|---:|
| Regular-season games analyzed | 272 | 272 |
| Fetch/process failures | 0 | 0 |
| Games with any comparison mismatch | 187 | 49 |
| Team rows with Total Yards mismatch | 248 / 544 | 56 / 544 |
| Net Total Yards delta | +1,138 | +2 |
| Team rows with Turnovers mismatch | 12 / 544 | 2 / 544 |
| Net Turnovers delta | -12 | -2 |

The detailed, reproducible per-game output is in `audits/season_2025_reconciliation.md` and its companion CSVs (ignored by Git). Penalty Yards matched on all rows because the app copies that box-score number.

## Remaining confirmed or plausible issues

1. **Two missing giveaways in one game:** `401772747` (TEN at ARI) has TEN and ARI each one below the box score. ESPN's summary provides only a terse Lockett “0 Yd Fumble Recovery” scoring stub, not the interception/fumble chain. The [Titans' game recap](https://www.tennesseetitans.com/news/titans-stage-furious-rally-beat-cardinals-22-21) and [highlight](https://www.tennesseetitans.com/video/can-t-miss-play-cam-ward-s-int-somehow-evolves-into-tyler-lockett-s-first-titans-td-game-highlights) corroborate that chain. Do not hardcode this game into the parser; an additional play source or explicit data-quality status is needed.
2. **Yard residuals and missing source detail:** 56 team rows still disagree, despite the +2 net delta. The largest current game delta is +34 PHI in `401772845`. Its box score credits punter Braden Mann a -34-yard rushing play, but that play is absent from the summary's `drives.previous[].plays` feed; the recap describes a game-ending safety. In `401772730`, the current summary replaces a Panthers sack/fumble play with a terse scoring stub, omitting its -11 sack yards, although an older local snapshot contains the full play. In `401772927`, a safety is only a “Team Safety” stub, omitting the underlying -9-yard sack. A box-score total cannot reconstruct missing play-level details for success rate, drives, or competitive filtering. Other residuals require play-by-play evidence before a parser rule is changed.
3. **Inadequate independent oracles:** Score and penalty totals are source pass-through; success rate, explosiveness, field position, drives, non-offensive points, and WP-filtered splits have tests but no independent season-wide reconciliation. Existing mocked tests can still over-specify implementation behavior. A small set of curated NFL gamebook/play-level goldens would strengthen this substantially.
4. **Definition drift requiring owner choice:** `FAQ.txt` refers to eight factors, `documentation.txt` enumerates ten, and the UI counts seven. The docs describe explosives as 10+ yards for every play, whereas the code uses 10+ runs and 20+ passes. The docs describe YPP as total yards / total plays, whereas the code uses offensive yards / selected offensive plays. They define turnovers as interceptions and lost fumbles, while the app also treats an onside kick recovered by the kicking team as a turnover. These are not safe to resolve by guessing which definition is intended.

## Decisions to make before a broader metric rewrite

Historical questions from the initial audit; the owner decisions and
implementation status are in `METRICS_FOLLOWUP_2026-09-29.md`.

1. What is the authoritative reference: ESPN box score/summary, official NFL gamebooks, or an explicitly defined custom metric when they differ?
2. Should explosives remain 10+ rush / 20+ pass, or become 10+ for all plays as the docs currently say? Which plays should count in YPP (kneels, spikes, aborted snaps)?
3. Should onside recoveries count as turnovers, or be a separate possession-swing event? Which seven/eight/ten factors should the dashboard actually count?

## Verification

- Python: `.venv/bin/python -m pytest -q tests/` → 173 passed.
- Dashboard: `npm run test` → 21 passed; `npm run lint`, `npm run typecheck`, `npm run build` → passed without warnings.
- Season: 272/272 2025 regular-season games analyzed from network with zero fetch/process failures. Reconciliation is **not** green because of the residuals above.
