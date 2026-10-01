# Live EPA from ESPN: 2026 Week 3 feasibility check

This is the initial September 30 feasibility check. The subsequent
[16-game validation](EPA_GOAL.md) reached the 95% play-level coverage and
accuracy targets for offense and special teams. The recommendations below
record what remained after this initial check; consult the validation report
for the completed exercise and its remaining limits.

## Result

ESPN supplies enough structured state to estimate expected points on ordinary
offensive plays. In ten completed Week 3 games, including **SEA at WSH** and
**LAR at DEN**, every one of the 1,223 nflverse run/pass plays (excluding
two-point tries) had a matching ESPN play ID. On 1,171 plays (95.7%), ESPN and
nflverse agreed on down, yards to go, yards to end zone, half time remaining,
and both teams' timeouts after timeout reconstruction.

This is **not yet a full live EPA implementation**. A deliberately restricted
861-play subset (70.4% of the offensive plays) could be evaluated by
subtracting a predicted pre-play expected-points value from the next
same-possession state. It excludes scoring, turnovers, penalties, drive ends,
and other state transitions. The remaining 362 plays include those situations
and other cases excluded by the conservative matching rule. A full EPA feature
must handle them explicitly. These results came
from completed-game snapshots, not a measurement of in-game latency or of
which fields are available immediately after a snap.

## Games and coverage

Rams and Seahawks games were required. Eight of the other fourteen Week 3
games were selected with a fixed random seed (`20260930`). All games were
final when checked on September 30, 2026.

| Game (ESPN ID) | Reference offensive plays | ESPN ID matches | Exact checked state | Restricted EPA subset |
|---|---:|---:|---:|---:|
| CIN at PIT (`401872950`) | 112 | 112 | 106 | 75 |
| HOU at IND (`401872951`) | 122 | 122 | 119 | 94 |
| NYJ at DET (`401872954`) | 123 | 123 | 116 | 93 |
| **SEA at WSH (`401872955`)** | **127** | **127** | **118** | **78** |
| TEN at NYG (`401872956`) | 114 | 114 | 113 | 85 |
| NE at JAX (`401872957`) | 119 | 119 | 114 | 86 |
| MIN at TB (`401872959`) | 119 | 119 | 117 | 77 |
| LV at NO (`401872961`) | 133 | 133 | 125 | 95 |
| **LAR at DEN (`401872962`)** | **140** | **140** | **133** | **97** |
| PHI at CHI (`401872963`) | 114 | 114 | 110 | 81 |
| **Total** | **1,223** | **1,223** | **1,171** | **861** |

The reference is the nflverse [2026 play-by-play release](https://github.com/nflverse/nflverse-data/releases/tag/pbp), joined to the app's [ESPN summary feed](api/lib/game_analysis.py) by game and numeric play-ID suffix. The exact 2026 Parquet downloaded for this check had SHA-256 `e04965158a00a23cf89193f9959c05f9e532f4313f2fde62fce074b226832273`.
Matching IDs establish coverage in this sample, not that every source field is
correct or that the two feeds are independent oracles.

## State differences that matter for EPA

- **Clock on scoring plays:** 51 of the 52 state disagreements are game-clock
  differences. In these records, ESPN's `start` field is the pre-play down and
  field position, but `clock.displayValue` is the clock when the scoring play
  ended. nflverse records the snap clock. For example, Rams touchdown play
  `401872962632` is 5:00 in the reference and 4:55 in ESPN. The gap across
  these 51 plays is 1–12 seconds. A live model needs a defined pre-play clock
  source or must mark those estimates provisional.
- **One field-position conflict:** In SEA–WSH play `4018729553976`, ESPN says
  fourth-and-2 at the SEA 40; nflverse says fourth-and-1 at the SEA 39. ESPN's
  preceding play text itself says the ball reached the SEA 39. This changes
  the prototype's EPA estimate for that play from +2.15 using reference states
  to +2.77 using ESPN states, versus nflverse EPA of +2.17. It should be
  adjudicated against the gamebook before changing an ESPN parser rule.
- **Timeouts are reconstructable, but not a clean field:** Neither team's
  remaining timeout count appeared as a structured per-play field in the
  ESPN summary. The audit rebuilt it from timeout event text and embedded
  replay-challenge text. HOU uses `HST` in timeout text, and failed challenges
  in the Rams and Buccaneers games consume a timeout inside the challenged
  play's description. The resulting counts match nflverse in this sample;
  that text parsing needs broader validation and live-revision handling.
- **Roof is not present in the checked ESPN summary.** The published
  [nflfastR expected-points function](https://nflfastr.com/reference/calculate_expected_points.html)
  lists roof among its inputs. A full implementation would need a venue/roof
  source or a model trained without it.

## Expected-points model experiment

To separate ESPN state quality from model quality, I trained a small Python
`HistGradientBoostingRegressor` on **38,841 2025 regular-season nflverse rows**
to approximate nflverse's pre-play expected-points (`ep`) value. Inputs were
only down, yards to go, yards to end zone, half time remaining, and each team's
remaining timeouts. The 2025 reference release used here had SHA-256
`c6ecedd6d678cc37ed316b23ef84ee1ec6abb69c514bb11868a7ebd5a367df29`.
The 2026 Week 3 games were held out. This is a **surrogate**, not nflfastR's
published model and not a production model trained on actual scoring outcomes.

| Held-out comparison | Plays | Mean absolute error | 90th percentile absolute error |
|---|---:|---:|---:|
| Pre-play EP from nflverse states vs nflverse EP | 1,223 | 0.166 points | 0.324 points |
| Pre-play EP from reconstructed ESPN states vs nflverse EP | 1,223 | 0.166 points | 0.325 points |
| Restricted EPA from nflverse states vs nflverse EPA | 861 | 0.067 points | 0.137 points |
| Restricted EPA from ESPN states vs nflverse EPA | 861 | 0.068 points | 0.138 points |

For restricted EPA, both predictions use *the same surrogate model*. They
subtract predicted EP at the current state from predicted EP at the next
same-possession offensive state; only the source of the input state changes.
Across those 861 plays, switching from nflverse to ESPN states changes the
estimate by a mean absolute **0.0007 points**. That small average hides the
SEA–WSH field-position outlier above. It also does not validate the excluded
362 plays, or show that the surrogate can replace nflfastR's model.

The next largest restricted-subset errors were mainly **model differences with
identical input states**: Rams play `401872962418` was -1.13 EPA in nflverse
versus -1.57 in either surrogate calculation; HOU–IND play `401872951359`
was +0.19 versus -0.22. These should not be attributed to ESPN.

## What to do next

1. Build a canonical pre-play and post-play state adapter from ESPN, with
   explicit handling for scoring plays, turnovers, penalties, possession
   changes, end-of-half plays, extra points, and two-point conversions.
   Preserve a reason when a play cannot be valued; do not silently assign
   zero EPA.
2. Resolve the scoring-play clock and the SEA–WSH yardline conflict against
   the NFL gamebooks. Recheck timeout reconstruction across more games and
   during one live game, because completed ESPN records can be revised.
3. Choose a reproducible, deployable EP model. The surrogate proves that
   ESPN-state inference is possible for straightforward plays; it is not
   enough to publish full-game EPA. Compare a proper model's play and team
   totals with the postgame nflverse release on held-out games, with errors
   broken out by scoring, turnover, penalty, and ordinary plays.
4. Only after those cases pass, add an opt-in/debug display with model version,
   eligible-play count, unvalued-play count, and provisional status. A
   completed-game reconciliation can replace or flag provisional values.

The reproducible one-off script and detailed per-play JSON are in
`audits/epa_week3_2026.py` and `audits/epa_week3_2026.json` (the repository's
`audits/` directory is gitignored). The script downloads and verifies the two
pinned Parquet files in `/tmp` if needed, fetches current ESPN summaries through the app's existing
`get_game_data`, and does not change application output.
