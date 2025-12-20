# Season 2025 Logic Recommendations (Auto)

Generated from cached `pbp_cache/*.json` plus `audits/season_*_team_comparison.csv`-equivalent data.

## Aggregate Percent Deltas
- Percent deltas are computed as `(sum(windelta) - sum(espn)) / sum(espn) * 100`.
- Total Yards: -13.057% (Δ -82)
- Turnovers: +0.000% (Δ +0)
- Penalty Yards: +0.000% (Δ +0)

## Remaining Mismatch Counts (Team Rows)
- Yards mismatches: 2/2
- Turnover mismatches: 0/2
- Penalty-yards mismatches: 0/2

## Heuristic Attribution (Yards)
- Rows analyzed (with cache available): 2
- Rows exactly explained by kneel/spike exclusion: 0
- Rows exactly explained by fumble credited-yards mismatch: 0

## Recommendations
- Inspect top remaining yards deltas; remaining issues are likely edge cases (special teams attribution, rare replay phrasing, unusual play types).

## Top Remaining Yard Deltas (Team Rows)
- 401772742 CHI: YdsΔ -68 TOΔ +0 PenYdsΔ +0
- 401772742 LV: YdsΔ -14 TOΔ +0 PenYdsΔ +0

## Suggested Deep-Dive Command
- For any game above: `python diagnose_game_discrepancies.py <game_id>`
