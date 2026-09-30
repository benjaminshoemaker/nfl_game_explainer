# Metrics follow-up — 2026-09-29

## Outcome

The prior follow-up stopped at a correct final-game display but left 49 games
with unexplained differences between the play parser and ESPN's box score.
That was premature. I compared individual plays, ESPN player/team totals, and
44 older local ESPN snapshots, repaired general parser errors, then fetched
all 272 games in the 2025 regular season again. A second investigation joined
the ESPN plays to nflverse's 2025 play-by-play and checked the disputed plays
against NFL gamebooks. That found three more general fumble-spot errors, now
fixed with real-play regression tests. The fresh, failure-free season run has
**13 mismatch games** and **12 of 544 Total Yards rows** (down from 49 games
and 56 yard rows at the start of this follow-up). The two turnover rows are
unchanged and both belong to one game with missing possession detail. The 12
yard differences sum to +65; netting them obscures the individual gaps.

The raw parser remains **not fully reconciled**. Final-game API/CLI output uses
ESPN's box-score Total Yards and giveaways, plus kicking-team onside
recoveries charged to the receiving team under this dashboard's Turnovers
definition. It retains `Calculated Total Yards`, `Calculated Turnovers`, and
`source_gaps` rather than inventing absent plays. Live games still use
play-by-play totals to avoid box-score/feed lag. Competitive metrics remain
play-derived, so the final-total reconciliation does not validate them.

The independent season comparison deliberately uses the raw parser, before
display reconciliation. Its command and ignored output paths are:

```bash
.venv/bin/python compare_season_games_report.py --season 2025 --season-types 2 \
  --ids-input audits/season_2025_game_ids.txt --source network \
  --out-team-csv audits/season_2025_team_comparison_2026-09-29.csv \
  --out-game-csv audits/season_2025_game_priority_2026-09-29.csv \
  --out-md audits/season_2025_reconciliation_2026-09-29.md \
  --espn-stats-cache audits/season_2025_espn_official_stats_2026-09-29.json
```

## What the play-level diagnosis fixed

- Accepted penalties after completed plays: retain touchdown yards when a
  foul is enforced between downs; credit yards up to the enforcement spot on
  post-catch and downfield-foul plays even if ESPN labels the score nullified.
- Sack/fumble and recovery spots: exclude return yards, apply first-touch
  position where ESPN supplies it, handle end-zone sacks and repeat fumbles,
  and avoid treating an illegal-forward-pass penalty or a later two-point try
  as a completed forward pass within the fumble play.
- Scoring captions and possession: include the underlying offensive play on
  fumble-return touchdowns when full play text exists, while excluding terse
  score-only captions. Keep true rushing plays even when a later illegal pass
  appears in the text. Narrow the aborted-snap rule to the center/handler/
  third-recoverer case the ESPN player totals actually support; a broader
  zero-yard rule introduced four new mismatches and was withdrawn.
- Fumble first-contact spots: recognize a bare `50` as midfield and stop the
  search at the next fumble. This corrected LAC `401772750630` (+1), DAL
  `4017729471625` (+1), and CAR `4017728581848` (-1) without game-ID rules.

These are play-shape rules with regression tests using actual ESPN play IDs,
not game-ID corrections. The [NFL Guide for Statisticians](https://www.nflgsis.com/gsis/documentation/stadiumguides/guide_for_statisticians.pdf)
was used to check sack/fumble and aborted-play attribution. ESPN's own
examples are not fully uniform, so we did not generalize beyond tested cases.

## Additional source checks and remaining residuals

The [nflverse 2025 play-by-play release](https://github.com/nflverse/nflverse-data/releases/tag/pbp)
provides a machine-readable second play stream. We matched game, team, and
ESPN play-ID suffix, then compared each offensive play's credited yards. Its
team totals matched ESPN's box in 14 of the 15 yard rows remaining before the
last fumble fix. The exception was CLE: nflverse and the NFL gamebook both say
322, while ESPN's box says 323. This is a useful diagnostic cross-check, not
an independent gold standard or a same-day live-game source. nflverse's
[published refresh schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html)
is nightly.

The [NFL PHI-TB gamebook](https://www.nflgsis.com/2025/REG/04/59899/Gamebook.pdf),
[PIT-LAC gamebook](https://static.www.nfl.com/image/upload/v1762776347/gamecenter/f7d5339e-311e-11f0-b670-ae1250fadad1.pdf),
[CIN-DET gamebook](https://static.www.nfl.com/image/upload/v1759751442/gamecenter/f6efb1e1-311e-11f0-b670-ae1250fadad1.pdf), and
[ARI-SEA gamebook](https://static.www.nfl.com/image/upload/v1758885913/gamecenter/f688dbab-311e-11f0-b670-ae1250fadad1.pdf)
pinpoint the hidden plays. ESPN's alternate site summary and individual core
play endpoint return the same score-only captions; switching ESPN endpoints
does not restore their missing text.

| Category | Game/team | Raw yard delta vs ESPN | Evidence and disposition |
|---|---|---:|---|
| Hidden safety play | `401772845` PHI | +34 | Gamebook/nflverse: Mann fake-punt run at Q4 0:06, -34; ESPN drive list has only “Kaevon Merriweather Safety.” |
| Replaced with score caption | `401772730` CAR | +11 | An older local ESPN snapshot and nflverse include the -11 sack; current ESPN summary and core play replace it with a fumble-return TD caption. |
| Hidden safety play | `401772927` PIT | +9 | Gamebook/nflverse: Q1 5:17 Rodgers sack/fumble, -9 credited; ESPN lists only “Team Safety.” |
| Hidden safety play | `401772854` CIN | +7 | Gamebook/nflverse: Q4 1:54 Browning sack, -7; ESPN lists only “Derrick Barnes Safety.” |
| Play omitted from ESPN drives | `401772938` ARI | +7 | Gamebook/nflverse: Q2 0:38 Murray sack, -7, play suffix `2128`; no corresponding ESPN drive play. |
| Different credited aborted-play yardage | `401772717` CHI | -5 | ESPN text and [gamebook](https://static.www.nfl.com/image/upload/v1760432465/gamecenter/f73265eb-311e-11f0-b670-ae1250fadad1.pdf) have a -5 Williams rush at play `3094`, yielding 381. ESPN box and nflverse credit 0, yielding 386. The available sources conflict; the reason for the different credit is unconfirmed. Final display follows ESPN. |
| Different credited aborted-play yardage | `401772799` IND | -5 | ESPN text and [gamebook](https://static.www.nfl.com/image/upload/v1765759222/gamecenter/f8d8d236-311e-11f0-b670-ae1250fadad1.pdf) have a -5 Rivers rush at play `3285`, yielding 215. ESPN box and nflverse credit 0, yielding 220. Same unresolved source conflict. |
| Aborted recovery not credited in box | `401772835` CHI, `401772903` HOU | +1 each | ESPN play `statYardage` records +1 on each recovered aborted snap, but box/player totals and nflverse credit 0. Similar recoveries *are* credited in other games, so a blanket exclusion is unsafe. |
| Hidden fumble-return play plus box inconsistency | `401772726` CLE | +3 | [Gamebook](https://www.nflgsis.com/2025/reg/02/59860/Gamebook.pdf)/nflverse credit -4 at play `3773`, bringing parser 326 to 322. ESPN box says 323: its net passing 208 plus rushing 115, but player passes 218 less 11 sack yards implies net passing 207 and total 322. Two other ESPN-vs-nflverse one-yard play differences offset. |
| Hidden safety play | `401772819` LV, `401772864` DAL | +1 each | nflverse has a -1 rush on play `3483`/`396`; ESPN supplies only a score-only safety caption. |

The remaining turnover difference is `401772747` TEN at ARI: raw TEN 1/ARI 2
versus ESPN TEN 2/ARI 3. ESPN's summary and individual core play contain only
a Lockett fumble-recovery TD stub, not the full interception/fumble chain.
nflverse play `4224` records an Arizona interception followed by a fumble
recovered by Tennessee, independently accounting for both missing turnovers.
[The Titans' game summary](https://static.clubs.nfl.com/image/upload/titans/qbuja4jps9qriy7shser)
also describes the sequence. Final display uses ESPN 2/3 and warns; it cannot
reconstruct the missing play's WP or competitive attribution from ESPN alone.

We tested a tempting fallback: derive a score-only safety's yardage from its
starting distance to the offense's goal line. It happens to fit all five
2025 score-only safety stubs above, but **not all safeties are offensive-yard
plays**. The same season includes holding-in-end-zone no-plays and an
intentional-grounding safety with zero credited offensive yards. The stubs
also omit whether the underlying snap was a rush or sack, which affects
adjusted metrics. We therefore did not add an unverified yardage/classification
guess. A curated, versioned gamebook/nflverse supplement for *completed*
games is a possible future design; it would need provenance, refresh, and
disagreement handling rather than silently replacing ESPN live plays.

## Validation boundary

There is no database. ESPN responses are fetched on demand; `pbp_cache/` and
ignored `audits/` files are snapshots, not production storage. `nfl_core`
computes API and CLI metrics. Score, Penalty Yards, and official full-game YPP
come from ESPN; agreement for those fields is source pass-through, not
independent validation. Adjusted YPP, success rate, explosive rate, drives,
field position, non-offensive points, and competitive/WP splits have behavioral
and hand-checked representative-play tests, but **no independent season-wide
oracle**. The existing hand-calculated Chicago drive checks 8 net yards on
three snaps, 1/3 success, zero explosives, and its own-18 drive start. Separate
real-play goldens check onside attribution and a kickoff-return TD.

No `.claude/data-flow-baseline.md` existed; none was created to mark unresolved
differences as accepted. A complete parser reconciliation would require richer
play sources or manual gamebook-level attribution, not a rule that merely
forces team totals to agree.

## Verification

- `.venv/bin/python -m pytest tests/ -q`: 211 passed, including the three
  new fumble-spot goldens.
- `npm run test`: 23 passed; `npm run lint`, `npm run build`, and
  `npm run typecheck`: passed on the final worktree state.
- Fresh 272-game network audit: 272 analyzed, zero failures, 13 mismatch
  games, 12/544 yard rows, 2/544 turnover rows. Penalty yards match by
  construction, not independent validation.
- The earlier separate 272-game serving check showed every final-game Total
  Yards and adjusted Turnovers row agreeing with the chosen ESPN baseline.
  After the prior parser fixes, all then-mismatched games were fetched again
  and their served rows had zero baseline failures. The entire 272-game
  serving check was not rerun after this final fumble-spot correction.
- No deployment was made.
