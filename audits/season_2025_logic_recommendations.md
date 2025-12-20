# Season 2025 Logic Recommendations (Auto)

Generated from cached `pbp_cache/*.json` plus `audits/season_*_team_comparison.csv`-equivalent data.

## Aggregate Percent Deltas
- Percent deltas are computed as `(sum(windelta) - sum(espn)) / sum(espn) * 100`.
- Total Yards: -1.501% (Δ -2207)
- Turnovers: -2.091% (Δ -11)
- Penalty Yards: +0.000% (Δ +0)

## Remaining Mismatch Counts (Team Rows)
- Yards mismatches: 233/448
- Turnover mismatches: 11/448
- Penalty-yards mismatches: 0/448

## Heuristic Attribution (Yards)
- Rows analyzed (with cache available): 233
- Rows exactly explained by kneel/spike exclusion: 6
- Rows exactly explained by fumble credited-yards mismatch: 32

## Recommendations
- Inspect top remaining yards deltas; remaining issues are likely edge cases (special teams attribution, rare replay phrasing, unusual play types).
- Inspect turnover mismatches; remaining issues are likely muffed-kick or touchback corner cases.

## Top Remaining Yard Deltas (Team Rows)
- 401772742 CHI: YdsΔ -68 TOΔ +0 PenYdsΔ +0
- 401772726 CLE: YdsΔ +66 TOΔ +0 PenYdsΔ +0
- 401772928 PHI: YdsΔ -53 TOΔ +0 PenYdsΔ +0
- 401772814 KC: YdsΔ -50 TOΔ +0 PenYdsΔ +0
- 401772862 MIN: YdsΔ -50 TOΔ +0 PenYdsΔ +0
- 401772908 NO: YdsΔ -49 TOΔ +0 PenYdsΔ +0
- 401772877 NO: YdsΔ -43 TOΔ -1 PenYdsΔ +0
- 401772877 CAR: YdsΔ +43 TOΔ +0 PenYdsΔ +0
- 401772817 KC: YdsΔ -42 TOΔ +0 PenYdsΔ +0
- 401772834 NYG: YdsΔ -42 TOΔ +0 PenYdsΔ +0
- 401772839 LAR: YdsΔ +42 TOΔ +0 PenYdsΔ +0
- 401772864 DAL: YdsΔ -41 TOΔ +0 PenYdsΔ +0
- 401772716 DEN: YdsΔ -40 TOΔ +0 PenYdsΔ +0
- 401772843 SF: YdsΔ -40 TOΔ +0 PenYdsΔ +0
- 401772885 ARI: YdsΔ -40 TOΔ +0 PenYdsΔ +0
- 401772900 ATL: YdsΔ -40 TOΔ +0 PenYdsΔ +0
- 401772938 SEA: YdsΔ -39 TOΔ -1 PenYdsΔ +0
- 401772783 JAX: YdsΔ -34 TOΔ +0 PenYdsΔ +0
- 401772779 KC: YdsΔ -31 TOΔ +0 PenYdsΔ +0
- 401772780 CHI: YdsΔ -31 TOΔ +0 PenYdsΔ +0
- 401772845 TB: YdsΔ +31 TOΔ +0 PenYdsΔ +0
- 401772720 LV: YdsΔ -30 TOΔ +0 PenYdsΔ +0
- 401772721 NYJ: YdsΔ -30 TOΔ +0 PenYdsΔ +0
- 401772734 HOU: YdsΔ -30 TOΔ +0 PenYdsΔ +0
- 401772748 CLE: YdsΔ -30 TOΔ +0 PenYdsΔ +0

## Remaining Turnover Deltas (Team Rows)
- 401772877 NO: YdsΔ -43 TOΔ -1 PenYdsΔ +0
- 401772938 SEA: YdsΔ -39 TOΔ -1 PenYdsΔ +0
- 401772747 TEN: YdsΔ +3 TOΔ -1 PenYdsΔ +0
- 401772747 ARI: YdsΔ -18 TOΔ -1 PenYdsΔ +0
- 401772822 PHI: YdsΔ +0 TOΔ -1 PenYdsΔ +0
- 401772822 LAC: YdsΔ -17 TOΔ -1 PenYdsΔ +0
- 401772776 BUF: YdsΔ -12 TOΔ -1 PenYdsΔ +0
- 401772826 SEA: YdsΔ -12 TOΔ -1 PenYdsΔ +0
- 401772896 SEA: YdsΔ +1 TOΔ -1 PenYdsΔ +0
- 401772890 PHI: YdsΔ +0 TOΔ -1 PenYdsΔ +0
- 401772946 BUF: YdsΔ +0 TOΔ -1 PenYdsΔ +0

## Suggested Deep-Dive Command
- For any game above: `python diagnose_game_discrepancies.py <game_id>`
