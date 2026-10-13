# 2026 Week 5: retrospective replay

Inputs through Week 4. All margins are home minus away, in points.

This model predicts scoring margin, not betting returns. nflverse closing spreads are the market benchmark; odds do not enter the model.

| Predictor | RMSE ↓ | MAE ↓ | Winners (ties excluded) |
|---|---:|---:|---:|
| model | 12.500 | 9.543 | 11/14 |
| pointBaseline | 13.697 | 10.663 | 9/14 |
| vegas | 13.044 | 10.400 | 9/14 |

15/15 finished; 0 missing closing lines.

| Game (away @ home) | Actual | Model | Point baseline | Closing line |
|---|---:|---:|---:|---:|
| TB @ DAL | -8 | +5.31 | +3.99 | +9.5 |
| PHI @ JAX | +2 | +5.58 | +9.62 | +7.5 |
| CHI @ GB | +24 | +0.77 | -5.32 | -1.5 |
| CIN @ MIA | -7 | -4.13 | -4.32 | -7.0 |
| LV @ NE | +28 | +4.48 | +3.77 | +3.5 |
| MIN @ NO | -10 | -1.98 | -4.60 | -2.5 |
| CLE @ NYJ | +5 | +3.83 | -0.02 | +2.5 |
| IND @ PIT | +12 | +2.98 | +1.34 | +3.0 |
| HOU @ TEN | -23 | -3.01 | -2.30 | -6.5 |
| NYG @ WSH | +0 | -2.05 | -1.43 | +3.5 |
| DEN @ LAC | -6 | -3.50 | -1.42 | -3.5 |
| DET @ ARI | -24 | -3.09 | -2.51 | -5.5 |
| SF @ SEA | -3 | +0.29 | +0.96 | +3.0 |
| BAL @ ATL | -7 | -1.67 | -0.63 | +3.5 |
| BUF @ LAR | -3 | +1.34 | +1.49 | +3.5 |

A single week is a small sample. A replay uses corrected data available now, strictly filtered to earlier weeks; it was not published before those games. The frozen coefficients were fit only through 2025. Past QB usage is not confirmed starter knowledge.

[nflverse schedule definitions](https://nflreadr.nflverse.com/articles/dictionary_schedules.html)
