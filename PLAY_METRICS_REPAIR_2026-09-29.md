# Play-metric repair and verification — 2026-09-29

## Outcome

The parser did not need a wholesale rewrite. Three confirmed classification
defects were corrected: a defender named Kneeland was mistaken for a kneel;
interception-return touchdowns erased the underlying pass attempt; and some
rushing fumbles were present in Total Yards but absent from adjusted efficiency.
Offensive classification and credited yards now flow through one per-play
contribution before aggregation, with separate inclusion flags for adjusted
metrics, official-style offense, and score-only yards.

The completed-game API still uses ESPN box-score Total Yards and Turnovers
(with the dashboard's onside-recovery addition). It now also compares its
calculated offensive-play count with ESPN's official count. A count-only
difference can reveal missing zero-yard plays that yard totals cannot, but
it can also reflect unusual scoring or special-teams classification. The
warning therefore signals a disagreement, not a claim that ESPN is always
missing exactly that many source plays. The app does not synthesize absent
plays or assign them to a win-probability window.

## Independent checks

- Fresh 2025 regular-season reconciliation: 272 games, zero fetch/process
  failures; 13 games with raw yard/turnover mismatches, 12 of 544 Total Yards
  rows, two of 544 Turnovers rows. These are unchanged from the prior audit.
  The new count check finds 16 of 544 offensive-play rows differing from ESPN
  by a net -15 plays. Penalty yards are a source pass-through, not an
  independently checked parser result.
- ESPN-to-nflverse per-play rerun: all 13 totals-flagged games plus the same
  seeded 24 totals-matching games. The matched-total sample went from four
  discrepancies to zero. The flagged games went from 20 to 19. The 19
  remaining differences consist of unavailable score-caption/omitted plays,
  ESPN-versus-reference yard-credit disagreements, and one play whose
  underlying fumble/interception chain is replaced by a score-only caption.
  nflverse is a comparison stream, not an unquestioned oracle.
- The five absent SEA–ARI offensive plays (four incompletions, one sack) are
  now visible as count gaps: SEA two, ARI three. Only ARI's -7 sack affected
  the yard reconciliation. This is why matching team yards alone was
  insufficient evidence of complete play metrics.
- A broad rule to exclude spikes appeared to fix two example count gaps but
  produced 84 mismatched team rows across the season. It was rejected; the
  observed exceptions remain flagged.

## Remaining boundary

The 13 raw-total mismatch games are not fully reconciled. Known causes
include ESPN safety/fumble score captions that replace an offensive snap,
plays absent from both ESPN summary and probability feeds, and conflicting
yard credit among ESPN box score, play text, gamebooks, and nflverse. In
TEN–ARI, two raw turnover rows remain wrong because the score caption masks
the underlying chain. The dashboard's final full-game totals use ESPN, but
adjusted efficiency and competitive splits should be read with the displayed
source-gap notice where the feeds disagree. Count-only alerts require similar
care: some are convention differences, not missing plays.

Reproduce the season check with `compare_season_games_report.py` and the
per-play check with `PYTHONPATH=. .venv/bin/python
audits/play_metric_audit_2026-09-29.py`. The latter requires the referenced
nflverse parquet file and both audits' output paths; the exact commands are
recorded in the prior audit and the CLI's `--help`.
