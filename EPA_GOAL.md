# ESPN EPA comparison goal

The active goal is to calculate play-level EPA from ESPN's live play stream and
compare completed-game results with nflverse. The initial sample is ten 2026
Week 3 games, including SEA at Washington and the Rams at Denver. nflverse is
the postgame comparison target, not an infallible play-state oracle.

## Acceptance criteria

- For both offensive run/pass plays and special-teams plays (kickoff, punt,
  field goal, extra point), produce an EPA value on at least **95%** of eligible
  plays with non-null nflverse EPA.
- Among predicted plays in **each** category, at least **95%** differ from
  nflverse by no more than **0.25 EPA points**. Report mean absolute error and
  the 90th-percentile error as diagnostics.
- Report `within tolerance / all eligible` alongside conditional accuracy,
  so missing hard plays cannot disappear from the headline number.
- Attribute defensive EPA to the opponent as the negative of offensive EPA.
  Report defensive scores by team, without double-counting mirrored plays in
  the overall denominator.
- Verify the same criteria on the six 2026 Week 3 games excluded from the
  development sample: ARI–SF, ATL–GB, BAL–DAL, CAR–CLE, KC–MIA, and LAC–BUF.
  Do not tune parser rules or model parameters against these games before the
  first held-out result is recorded.
- Keep a separate count for nullified penalty (`no_play`) and two-point plays;
  their nflverse treatment is not implied by the two categories above.
  Include scoring, possession changes, turnovers, and drive/half ends in the
  offensive denominator, and record any irreducible ESPN/reference conflicts.

## Result, 2026 Week 3

The original six-feature surrogate predicted EPA for 861/1,223 ordinary
offensive plays and no special-teams plays. The current benchmark uses the
[published nflfastR EP model](https://github.com/nflverse/fastrmodels) on
ESPN-derived states, applies the [nflfastR scoring and possession rules](https://github.com/nflverse/nflfastR/blob/master/R/helper_add_ep_wp.R),
and estimates field-goal and extra-point pre-play EP from 2025 reference data.
The nflfastR model artifact and both nflverse seasons are SHA-256 pinned in the
research code. The [ESPN-only transition parser](research/espn_epa.py) receives
no nflverse play states or outcomes.

| Sample | Category | Eligible | Predicted | Within ±0.25 | Mean absolute error |
|---|---|---:|---:|---:|---:|
| Development (10 games) | Offense | 1,223 | 1,223 | 1,216 (99.4%) | 0.006 |
| Development (10 games) | Special teams | 266 | 266 | 264 (99.2%) | 0.013 |
| Held out (6 games) | Offense | 761 | 761 | 755 (99.2%) | 0.015 |
| Held out (6 games) | Special teams | 155 | 155 | 152 (98.1%) | 0.024 |

Scoring run/pass plays: **49/50** development and **31/32** held out within
tolerance. Turnover run/pass plays: **27/27** development and **13/13** held
out. ESPN-derived possession team matched nflverse's team assignment on every
eligible play. Defensive EPA is the negative of the opponent's offensive EPA;
special-teams team totals credit one side and debit the other.

The first held-out run was recorded before inspecting those six games:
751/761 offensive plays and 150/154 predicted special-teams plays were within
tolerance, with 154/155 special-teams coverage. After that run, ESPN timeout
aliases (`ARZ`, `BLT`, `CLV`), a kickoff filed as `Penalty`, and an own-side
quarterback kneel were handled. No threshold or model parameters were changed
to fit the held-out games.

### Seahawks at Washington example

These are **full-game net team EPA sums**, not per-play match rates. Defense
mirrors the opponent's offense, and special teams is zero-sum across both
teams. Minor play errors accumulate in these sums.

| Team | Category | ESPN calculation | nflverse reference |
|---|---|---:|---:|
| SEA | Offense | -2.988 | -2.971 |
| SEA | Defense | +4.936 | +5.031 |
| SEA | Special teams | -0.642 | -0.984 |
| WAS | Offense | -4.936 | -5.031 |
| WAS | Defense | +2.988 | +2.971 |
| WAS | Special teams | +0.642 | +0.984 |

### Source and model disagreements retained in the score

- **SEA–WAS fourth down:** ESPN structured data says fourth-and-2 at SEA 40
  for play `3976`. Its preceding ESPN play ends at SEA 39, and the
  [official gamebook](https://static.www.nfl.com/image/upload/v1790594137/gamecenter/aa29c0fa-4feb-11f1-abca-2c54536568a9.pdf)
  says fourth-and-1 at SEA 39. The paired plays `3951` and `3976` each miss
  by 0.429 EPA in opposite directions. They remain scored as misses because
  the live ESPN structured field itself is inconsistent.
- **BAL–DAL roof:** ESPN and the [official gamebook](https://static.www.nfl.com/image/upload/v1790594140/gamecenter/aa29cd02-4feb-11f1-abca-2c54536568a9.pdf)
  place the game at open-air Maracanã Stadium. The 2026 nflverse row says
  `roof=open`, which its EP model encodes as a retractable roof. All nine
  remaining held-out misses are in that game. The ESPN calculation keeps the
  actual venue classification instead of substituting the reference value.
- **Field goals and scoring clocks:** Field-goal pre-play EP uses a 2025-trained
  approximation of nflfastR's separate field-goal model. ESPN also records
  end-of-play rather than snap time on some scores. These account for some
  other residuals; the JSON evidence lists every play over tolerance.

### Reproduce and limits

Install `research/requirements.txt` into the project virtual environment,
and install `libomp` on macOS if XGBoost reports that runtime missing. Then run:

```bash
PYTHONPATH=. .venv/bin/python research/epa_benchmark.py --sample development
PYTHONPATH=. .venv/bin/python research/epa_benchmark.py --sample holdout
.venv/bin/pytest -q tests/
```

The benchmark writes ignored JSON evidence and ESPN response snapshots under
`audits/`; `--refresh-espn` replaces those snapshots. This validates completed
game streams, including scoring and possession changes. It does **not** yet
measure in-game update latency or put EPA in the live dashboard. Two-point
tries and `no_play` penalties remain separately tracked rather than silently
included in the run/pass and special-teams acceptance denominators: 6 two-point
and 186 `no_play` rows with EPA in development, and 4 two-point and 117
`no_play` rows with EPA held out.
