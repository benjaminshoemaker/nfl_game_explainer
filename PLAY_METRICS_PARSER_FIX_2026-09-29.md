# Play-metric parser fixes — 2026-09-29

The confirmed pass/run classification defect is fixed in `api/lib/nfl_core.py`.
Passes no longer become runs because a caption contains a defender named
Brunskill, a reference to the runner, or an appended two-point rush. The
explosive-play calculation also explicitly requires a run *without* a pass
dropback before applying the 10-yard run threshold. Pass dropbacks retain
their 20-yard threshold.

Two fake-kick snaps filed by ESPN as `Fumble Recovery (Own)` are now included
as offensive pass/dropback plays when their captions describe an incomplete
pass or a sack, rather than being excluded solely for their field-goal or
punt formation. Both carry zero yards in ESPN's official totals. The CLE
and NE calculated offensive-play counts now agree with the ESPN box scores
for those games.

## Verification

The before/after audit joined all 272 games of the 2025 regular season to
the same 32,813 selected nflverse offensive plays. It removed exactly 22
play-level metric-vector differences: 20 false explosive passes and the two
fake-kick snaps. No new differences appeared. The remaining comparison has
22 differences in 16 games and 17 game/team rows, versus 44 in 36 games and
37 game/team rows before. The 22/32,813 figure is 0.067% of selected
reference plays, **not** a measured parser error rate; residual cases include
source and rules disagreements. The season audit also rechecked each
freshly fetched ESPN game's Total Yards and Turnovers against the earlier
snapshot, so these fixes did not alter those totals.

The previously affected competitive-window example, ATL–TB `401772948`,
now displays ATL with 9/65 explosive plays (13.8%) and TB with 8/61
(13.1%). The erroneous TB lead is gone.

Output: `audits/play_metric_audit_2025_full_after_parser_2026-09-29.json`.
The original baseline and remaining-case categories are in
`PLAY_METRICS_FULL_SEASON_AUDIT_2026-09-29.md`.

## Still unresolved

The 22 residual differences are the earlier source/convention cases minus
the two fake kicks: five plays missing from ESPN's SEA–ARI drive feed; nine
score-only safety/fumble captions lacking underlying play detail; six
yard-credit conflicts; one replay/intentional-grounding count convention;
and one ESPN `Rush` versus nflverse scramble-label disagreement. The
intentional-grounding event agrees with ESPN's official offensive-play count,
so adopting nflverse's `no_play` label would make that ESPN reconciliation
worse. These were not changed by inference. Matching raw team totals still
does not certify all derived metrics in a particular game.

Local checks: Python tests (238 passed), frontend tests (23 passed),
TypeScript typecheck, ESLint, and production build all passed. No deployment
was made.
