# Full-season play-metric audit — 2026-09-29

This is the **pre-fix baseline**. The parser repair and verified after-state
are documented in `PLAY_METRICS_PARSER_FIX_2026-09-29.md`.

## Result

**Failed: a confirmed explosive-play parser defect remains.** The audit
compared all 272 games in the 2025 regular season against the nflverse
`play_by_play_2025.parquet` snapshot, joining by game and play ID. The
reference contains 32,813 selected offensive plays (runs/passes, excluding
two-point tries and clock-only play types). Every ESPN game joined to a
nonempty reference game, and the freshly fetched ESPN parser totals matched
the preceding season-audit snapshot for every team row.

There were 44 play-level metric-vector differences in 36 games (13.2%) and
37 of 544 team rows (6.8%). The 44 differences equal 0.134% of the selected
reference plays, **not an estimated error rate**: some are source conflicts
or classification conventions, and the two feeds do not share a perfect
oracle. The earlier 24-game clean sample was not representative of the
remaining 259 totals-matching games: across all 259, 25 differences occurred
in 23 games. The 13 already totals-flagged games retained 19 differences.

## Confirmed application defect

Twenty real pass plays, spread across 18 games, were incorrectly marked
explosive despite gaining only 10–19 yards. All 20 were checked against the
fresh ESPN play objects: `classify_offense_play` returned both `run=True`
and `pass=True`. Broad substring matching for `run` in the play text catches
names such as `Brunskill`, replay descriptions mentioning the `runner`, and
appended two-point rush descriptions. The aggregation then applies the
10-yard run threshold instead of the 20-yard pass threshold. These are
confirmed parser errors, not nflverse yard disagreements.

The maximum observed explosive-rate inflation was 3/65 plays, or 4.62
percentage points, for Miami in `401772760`. In `401772948`, Tampa Bay's
displayed competitive explosive rate is 9/61 (14.8%) versus Atlanta's
9/65 (13.8%); removing the false 19-yard pass explosive makes Tampa Bay
8/61 (13.1%), reversing which team leads that dashboard factor. The play
is inside the app's competitive window. None of these 18 games has a
current `source_gaps` warning, because their team yards and offensive-play
counts can still agree with ESPN.

## Other 24 differences

These occur in 18 different games and need source- or rule-level treatment,
not one generic parser substitution:

- Five offensive plays are absent from ESPN's SEA–ARI drive feed (four
  incompletions and a -7 sack); nflverse supplies them, but ESPN's play/WP
  feeds do not.
- Nine offensive snaps are represented only by safety or fumble-return
  score captions in ESPN, so the underlying rush/pass details are not
  available in the app's primary feed. This includes the TEN–ARI
  multi-turnover sequence and Kansas City's count-only safety case.
- Six plays have different credited yardage between ESPN play data and
  nflverse; some also conflict with ESPN's own box score or a gamebook.
- Two unusual fake-kick plays are offensive attempts in nflverse but are
  excluded by the app's special-teams rules.
- One replay/intentional-grounding event is counted as a zero-yard play by
  the app and `no_play` by nflverse.
- One 11-yard quarterback run is explicitly labeled a scramble in nflverse
  but only a `Rush` in the ESPN play, changing the explosive threshold.

The largest team-level differences in this comparison were 0.66 adjusted
yards/play (PHI, `401772845`) and 1.92 percentage points of success rate
(ARI, `401772938`). These are observed maxima, not bounds on future games.

## Coverage of the current warning

The yards/turnovers/offensive-play-count check warns on 18 games. Sixteen of
those had a play-level difference; two did not under this comparison rule.
Twenty games with play-level differences had **no** warning, including all
18 games with the confirmed false-explosive bug. Matching aggregate yards
and play counts therefore cannot certify success or explosive metrics.

## Audit-tool validation and next step

The comparison tool was corrected for one lateral-pass record where
nflverse's `yards_gained` held only the 11-yard final segment while its
`passing_yards` and the full play text recorded 28 yards. This removed a
false-positive comparison. The final audit also asserts a nonempty game
join and checks every fetched ESPN parser row against the season-audit
snapshot. The raw comparison output is
`audits/play_metric_audit_2025_full_verified_2026-09-29.json`.

First fix pass/run classification and the explosive threshold with a
regression test for these captions, then rerun this all-game comparison.
After that, adjudicate the residual source/convention cases separately and
decide whether to add a secondary play source or mark those metrics
provisional. No production-code fix or deployment was made during this
analysis.

## Metric inventory for this audit

| Metric | App calculation | Independent comparison | Boundary |
|---|---|---|---|
| Final Total Yards and Turnovers | `nfl_core.process_game_stats`; final rows reconciled in `game_analysis.py` | ESPN box score in season CSV | Displayed final totals are source pass-through, not proof of complete plays. |
| Offensive-play count | `nfl_core.classify_total_offense_play` | ESPN `totalOffensivePlays` | Clock and special-teams conventions can differ. |
| Adjusted yards/play | `nfl_core` offensive yards ÷ selected plays | nflverse yards and run/pass plays | Yard-credit conflicts and omitted captions persist. |
| Success rate | `nfl_core.calculate_success` over selected plays | Same 40/60/100 rule applied to nflverse | Missing plays and source down/yard differences matter. |
| Explosive count/rate | `nfl_core` 10-yard run / 20-yard pass rule | Same thresholds with nflverse play/dropback labels | Confirmed dual run/pass classification bug. |
| Competitive split/WP | ESPN probability feed and app WP filter | Presence of ESPN WP IDs; nflverse has separate WP model | Missing ESPN plays cannot receive exact ESPN deltas. |

No `.claude/data-flow-baseline.md` exists; unresolved differences have not
been marked as accepted baseline findings.
