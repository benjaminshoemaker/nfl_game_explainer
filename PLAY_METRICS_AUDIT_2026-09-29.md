# Play-derived metrics audit — 2026-09-29

This is the pre-repair baseline. The deterministic parser defects below were
subsequently fixed and re-audited in [PLAY_METRICS_REPAIR_2026-09-29.md](PLAY_METRICS_REPAIR_2026-09-29.md);
the source-data conflicts remain.

## Outcome

**Targeted data-flow audit: failed (confirmed divergence).** The previous
272-game team-total check identified 13 games with a raw Total Yards or
Turnovers mismatch. This audit joined individual ESPN and nflverse plays for
all 13, plus a seeded random sample of 24 of the 259 games whose team totals
matched. It found 20 offensive-play differences in the flagged games and four
in four of the 24 matched-total games. The matched-total sample is not an
estimate of the entire season's error rate.

For comparison, the [nflverse](https://github.com/nflverse/nflverse-data/releases/tag/pbp)
`play_by_play_2025.parquet` release was fetched on
2026-09-29 and joined by game and numeric play-ID suffix. We applied this app's
40/60/100 success rule, 10-yard run/20-yard pass explosive thresholds, and
pass-dropback treatment for scrambles to nflverse's play data. Two-point tries
and kneels/spikes were excluded. nflverse is a second play stream, **not a
perfect oracle**; disagreements were checked against ESPN text and NFL
gamebooks where the distinction mattered. The full ignored, reproducible
comparison is `audits/play_metric_audit_2026-09-29.py` and its JSON output.
All 74 freshly fetched raw team totals matched their rows in the preceding
season audit, so the play comparison did not cross mismatched ESPN snapshots.
Two subsequent targeted all-season pattern sweeps checked every nflverse rush
mentioning defender M. Kneeland and every interception-plus-touchdown play
against freshly fetched ESPN game data; these sweeps are separate from the
24-game random sample.

## Findings, highest priority first

1. **A normal rush is classified as a kneel when a defender is named
   Kneeland (confirmed parser defect).** In `401772834` NYG–DAL, play `207`
   is Tracy's 2-yard rush on 1st-and-10, tackled by M. Kneeland. The app's
   `is_spike_or_kneel` checks whether `"kneel"` appears anywhere in the full
   play text, so this play contributes +2 to Total Yards but **nothing** to
   adjusted plays/yards/success. nflverse records a 2-yard rush. NYG's
   adjusted values are 504/64 = 7.88 YPP and 33/64 = 51.6% success in the
   app versus 506/65 = 7.78 and 34/65 = 52.3% on the matched play stream.
   Its team Total Yards match ESPN, so `source_gaps` cannot detect this.
   The targeted season sweep found **12 such nflverse rushes in six games; all
   12 were excluded by the app**. This establishes a wider blast radius than
   the one randomly sampled example, but does not count other names or wording
   that might trigger the same substring bug.
   Site: `api/lib/nfl_core.py:is_spike_or_kneel`, then
   `classify_offense_play`.

2. **An intercepted pass returned for a touchdown is dropped from the
   offensive-play denominator (confirmed parser defect).** `_is_nonoffensive_return`
   excludes any `Interception Return Touchdown` before the underlying pass
   can be classified. The affected `401772864` WSH play `3361` and the
   matched-total sample's `401772956` LAC play `636` are real pass attempts
   with zero offensive yards. Both have ESPN win-probability records and
   occurred within the competitive filter. In the LAC example, success is
   22/65 = 33.8% in the app versus 22/66 = 33.3% when the attempt is counted;
   adjusted YPP is 217/65 = 3.34 versus 217/66 = 3.29. The turnover itself
   is counted, and team Total Yards remain unchanged, masking this defect.
   The season sweep found 29 nflverse interception-plus-touchdown candidates.
   ESPN labeled 27 of them `Interception Return Touchdown` (26 games), and
   the app excluded **all 27** underlying pass attempts. The other two use
   different ESPN captions: TEN–ARI's score-only fumble-recovery TD has no
   offensive detail and is excluded; a `Pass Interception Return` caption is
   counted. This is a confirmed pattern, not an extrapolation from two plays.
   Site: `api/lib/nfl_core.py:_is_nonoffensive_return`.

3. **Some own-recovered fumbles retain official yards but disappear from
   adjusted efficiency (confirmed inconsistency; classify policy should be
   explicit).** In matched-total `401772833` SF–NO, play `1254` is a -5
   Mac Jones snap in the [NFL gamebook](https://static.www.nfl.com/image/upload/v1757934527/gamecenter/f64358e9-311e-11f0-b670-ae1250fadad1.pdf).
   The app includes -5 in Total Yards but not in adjusted yards or plays;
   nflverse counts a -5 run. App adjusted YPP is 352/63 = 5.59 versus
   347/64 = 5.42. In matched-total `401772782` BAL–NYJ, play `2187` nets
   +1 yard after a Jackson fumble, recovery, and handoff per the
   [NFL gamebook](https://static.www.nfl.com/image/upload/v1763985645/gamecenter/f815107b-311e-11f0-b670-ae1250fadad1.pdf).
   The app includes +1 in Total Yards but excludes the snap from adjusted
   efficiency; nflverse counts a +1 run. These are not counted as successes,
   but omitting their denominators changes success rate. The documented
   adjusted metric includes offensive snaps, including aborted snaps; a
   special exclusion for these fumble plays is not documented.

4. **The 13 flagged games do have advanced-stat exposure, not just official
   Total Yards exposure.** PHI–TB's score-only -34 fake-punt safety is absent
   from adjusted efficiency: app 234/57 = 4.11 YPP versus 200/58 = 3.45 on
   the second play stream. In SEA–ARI (`401772938`), the ESPN drive list
   omits *five* nflverse offensive plays: two SEA incompletions, two ARI
   incompletions, and Murray's -7 sack. Neither the summary nor ESPN's
   probability feed has those five IDs. ARI's app success rate is 25/61 =
   41.0% versus 25/64 = 39.1%; SEA's is 27/62 = 43.5% versus 27/64 = 42.2%.
   All five were in the competitive range in nflverse's separate WP model.
   Because ESPN lacks their WP records, their individual ESPN WP deltas cannot
   be recovered from this feed; any later visible-play delta may absorb
   intervening state changes. The other 15 offensive-play differences in the
   flagged games had ESPN probability entries, including score-only stubs.
   That gives a game-state observation, not the missing offensive detail.

5. **TEN–ARI's touchdown stub masks a multi-event possession swing.** Play
   `4224` was an Arizona interception of Tennessee, followed by Arizona's
   fumble recovered by Tennessee for a touchdown. The app correctly shows
   the reconciled final turnovers but its raw play-derived details omit one
   turnover for each side and the offensive pass attempt. ESPN has one WP
   entry for the scoring stub, not separate entries for the interception and
   fumble. [The Titans' game summary](https://static.clubs.nfl.com/image/upload/titans/qbuja4jps9qriy7shser)
   describes the sequence. A single-play explanation can describe the whole
   sequence, but it cannot honestly assign separate ESPN WP swings to its
   stages.

## Coverage and magnitude

| Group | Games checked | Games with play-level differences | Offensive-play differences |
|---|---:|---:|---:|
| Previously flagged | 13/13 | 13 | 20 |
| Seeded random matched-total sample | 24/259 | 4 | 4 |

The targeted season sweeps additionally confirmed 12 excluded Kneeland
rushes and 27 excluded pick-six pass attempts; they should not be added to
the sample counts as though they were random observations.

The other 20 matched-total sample games reconciled on offensive-play count,
yards, success, and explosive flags under the stated comparison rule. The
largest observed adjusted-YPP difference was PHI's 0.66 yards/play; the
largest success-rate difference was ARI's 1.9 percentage points in SEA–ARI.
Those are sample maxima, not season-wide bounds. The two clear parser defects
above appeared even when Total Yards were correct. The two own-fumble cases
show a third blind spot in the same situation.

Several previously identified yard differences remain *source/version*
disputes, not necessarily parser mistakes: CHI–WSH and IND–SEA ESPN text plus
static gamebook credit -5 on an aborted rush, while ESPN's box and nflverse
credit zero. CLE–BAL's ESPN box is one yard above the gamebook and its player
stat arithmetic. This audit did not silently force play-derived metrics to
the box score in such cases.

## Metric inventory and boundary

| Metric | Current path | Independent check in this audit | Boundary |
|---|---|---|---|
| Final Total Yards, Turnovers | ESPN box reconciliation in `game_analysis.py` | Earlier full-season ESPN comparison | Source pass-through; does not validate plays |
| Adjusted YPP, success, explosive count/rate | `nfl_core.process_game_stats` from ESPN plays | Matched nflverse play IDs, same thresholds | Reference source can disagree on yard credit |
| Competitive split and play WP | ESPN probability feed + `is_competitive_play` | Presence of ESPN WP IDs; nflverse WP for omitted plays | Different WP models; missing ESPN plays cannot be assigned exact ESPN delta |
| AI/stat narrative | `build_analysis_text` consumes advanced rows | Traced input path | Inherits incorrect adjusted rows; language itself not separately scored |

There is no production database; ESPN is fetched on demand. The untracked
`audits/` files and `pbp_cache/` are snapshots. No
`.claude/data-flow-baseline.md` exists, and no unresolved finding was marked
accepted. No production-code fix or deployment was made as part of this audit.

## Recommended decision

Correct the two deterministic classification bugs and make the own-fumble
policy explicit, then rerun the play-level sample and full-season total audit.
Treat score-only/omitted ESPN plays as flagged, provenance-bearing gaps until
a supported supplemental play source is designed. The dashboard can continue
to use ESPN final totals, but its success rate, adjusted YPP, and AI narrative
should not yet be described as independently validated, even in games whose
Total Yards match.
