# Game-factor bar calibration

A factor bar shows the absolute gap between the two teams divided by a reference gap, capped at 100%. The shaded value cell identifies which team leads. A full bar means the gap is large compared with completed games **in the selected full-game or competitive view**; it does not measure how much the factor caused the result. Ties and unresolved comparisons have no bar.

The references below are rounded 90th-percentile **nonzero** gaps. We calculated them with the app's current factor rules from 224 completed 2025 regular-season games (weeks 1–15). We checked them against 48 completed games from 2026 weeks 1–3 and, where source data permitted, 272 games from 2024.

| Factor | Full game | Competitive plays |
|---|---:|---:|
| Turnovers | 3 | 3 |
| Success rate | 19 percentage points | 20 percentage points |
| Adjusted yards per play | 2.75 | 3.25 |
| Explosive-play rate | 11 percentage points | 11 percentage points |
| Points per trip inside the 40 | 3.25 | 3.75 |
| Average starting field position | 15 yards | 14 yards |
| Penalty yards | 60 yards | 55 yards |
| Non-offensive points | 14 | 7 |

The backtest required at least 20 eligible offensive plays per team for rate factors, two qualifying trips per team for points per trip, and five drive starts per team for starting field position. The app applies the same minimums before drawing those bars. Competitive results needed at least 95% per-play win-probability coverage; unresolved accepted penalties and games with relevant ESPN/play-by-play source gaps were excluded. Full-game penalty yards use ESPN's box score, while competitive penalty yards use attributed play-level penalties. Most 2024 play-derived games had source gaps, and 2024 play data lacked the structured penalties needed for competitive penalty yards.

**Live-game limit:** these references were calibrated at final. Quarter-end replay found much larger early rate gaps: the full-game success-rate 90th percentile was 33.8 percentage points after Q1 versus 18.9 at final. Live bars use the completed-game references and are labeled provisional until checked against saved live snapshots. The non-offensive-points values are also less certain: only 47 full-game and 45 competitive-game 2025 gaps were nonzero, and resampling moved the 90th-percentile threshold between 7 and 14 points.
