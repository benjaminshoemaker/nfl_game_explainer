# Season 2025 Reconciliation Report

## Summary
- Games analyzed: 1
- Mismatch games: 1
- Games with turnover mismatches: 0
- Games with yards mismatches: 1
- Games with penalty-yards mismatches: 0

## Priority Sort
Sorted by `max(|turnovers_delta|) desc`, then `max(|yards_delta|) desc` per game.

## Suggested Reconciliation Work Items (Heuristic)
- Turnover deltas: review turnover classification (muffed kicks, onside recoveries, replay reversals).
- Yards deltas: review how yards are attributed on turnover plays (interceptions/fumbles with returns) vs offensive yards.
- Penalty deltas: review how penalties are attributed (defensive/offensive, accepted vs no-play).
- Excluded plays with non-zero yards can indicate classification mismatches (penalty/no-play, special teams returns).

Heuristic counts across mismatch games:
- Potential missed turnover-keyword plays (not counted by windelta): 3
- Excluded non-zero-yard plays (not counted as offense by windelta): 29

## Games (Prioritized)

### 401772742 CHI @ LV (TOΔ max 0, YdsΔ max 18, raw=cache)

| Team | ESPN Yds | windelta Yds | Δ | ESPN TO | windelta TO | Δ | ESPN PenYds | windelta PenYds | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CHI | 271 | 253 | -18 | 1 | 1 | +0 | 60 | 60 | +0 |
| LV | 357 | 363 | +6 | 4 | 4 | +0 | 36 | 36 | +0 |

**CHI Reconciliation Clues**

- Windelta counted turnovers (1):
- Q1 4:24 (19 yds) Pass Interception Return: (Shotgun) C.Williams pass short middle intended for R.Odunze INTERCEPTED by M.Crosby at LV 15. M.Crosby pushed ob at LV 34 for 19 yards (D.Moore). [interception]

- Turnover-keyword plays not counted as turnovers (up to 2 shown):
- Q2 12:09 (-6 yds) Fumble Recovery (Own): (Shotgun) C.Williams to LV 29 for -5 yards (M.Crosby). FUMBLES (M.Crosby), and recovers at LV 30.
- Q4 12:27 (-19 yds) Fumble Recovery (Own): (Shotgun) C.Williams FUMBLES (Aborted) at LV 22, and recovers at LV 33.

- Excluded non-zero-yard plays (up to 18 shown):
- Q1 0:04 (-5 yds) Penalty: C.Williams pass short right to D.Swift to CHI 36 for 5 yards (A.Butler).PENALTY on CHI-R.Odunze, Illegal Motion, 5 yards, enforced at CHI 31 - No Play. [nullified]
- Q1 0:08 (23 yds) Kickoff: D.Carlson kicks 57 yards from LV 35 to CHI 8. L.Burden to CHI 31 for 23 yards (T.McCollum). [special_teams]
- Q1 13:24 (7 yds) Punt: T.Taylor punts 46 yards to LV 18, Center-S.Daly. T.Tucker to LV 25 for 7 yards (J.Owens; D.Hardy). [special_teams]
- Q1 15:00 (24 yds) Kickoff: D.Carlson kicks 60 yards from LV 35 to CHI 5. D.Duvernay to CHI 29 for 24 yards (D.Laube; T.Eichenberg). [special_teams]
- Q1 9:53 (46 yds) Field Goal Good: C.Santos 46 yard field goal is GOOD, Center-S.Daly, Holder-T.Taylor. [special_teams]
- Q2 0:53 (52 yds) Field Goal Good: C.Santos 52 yard field goal is GOOD, Center-S.Daly, Holder-T.Taylor. [special_teams]
- Q2 4:03 (25 yds) Kickoff: D.Carlson kicks 61 yards from LV 35 to CHI 4. D.Duvernay to CHI 29 for 25 yards (T.Eichenberg; C.Smith). [special_teams]
- Q2 4:22 (43 yds) Field Goal Good:  C.Santos 43 yard field goal is GOOD, Center-S.Daly, Holder-T.Taylor. [special_teams]
- Q3 12:12 (-5 yds) Penalty: PENALTY on CHI-T.Benedet, False Start, 5 yards, enforced at LV 22 - No Play. [nullified]
- Q3 3:43 (-1 yds) Punt: T.Taylor punts 62 yards to LV 2, Center-S.Daly, downed by CHI-J.Owens.PENALTY on LV-T.Eichenberg, Offensive Holding, 1 yard, enforced at LV 2. [special_teams]
- Q3 3:49 (-5 yds) Penalty: (Run formation) PENALTY on CHI-C.Kmet, False Start, 5 yards, enforced at CHI 41 - No Play. [nullified]
- Q3 5:23 (27 yds) Kickoff: D.Carlson kicks 60 yards from LV 35 to CHI 5. D.Duvernay to CHI 32 for 27 yards (J.Bech; T.Eichenberg). [special_teams]
- Q4 0:33 (-1 yds) Rush: C.Williams kneels to CHI 43 for -1 yards. [spike_kneel]
- Q4 11:38 (51 yds) Field Goal Good: C.Santos 51 yard field goal is GOOD, Center-S.Daly, Holder-T.Taylor. [special_teams]
- Q4 13:18 (5 yds) Penalty: (Shotgun) C.Williams pass incomplete short right to K.Monangai.PENALTY on LV-G.Pratt, Illegal Contact, 5 yards, enforced at LV 24 - No Play. [nullified]
- Q4 14:20 (-10 yds) Penalty: K.Monangai up the middle to LV 16 for 11 yards (D.Porter).PENALTY on CHI-J.Jackson, Offensive Holding, 10 yards, enforced at LV 27 - No Play. [nullified]
- Q4 4:08 (-4 yds) Penalty: PENALTY on CHI-C.Kmet, False Start, 4 yards, enforced at LV 37 - No Play. [nullified]
- Q4 6:45 (23 yds) Kickoff: D.Carlson kicks 57 yards from LV 35 to CHI 8. L.Burden to CHI 31 for 23 yards (D.Laube). [special_teams]

- Total-yards penalty corrections (up to 2 shown):
- Q2 5:34 Pass Reception: TotalYards -17 -> 3: (Shotgun) C.Williams pass short right to D.Moore to LV 7 for 9 yards (I.Pola-Mao; D.Holmes).PENALTY on CHI-O.Zaccheaus, Offensive Holding, 10 yards, enforced at LV 13.
- Q3 14:42 Rush: TotalYards -27 -> 3: D.Swift left guard pushed ob at LV 33 for 7 yards (G.Pratt).PENALTY on CHI-D.Swift, Face Mask, 15 yards, enforced at LV 37.

**LV Reconciliation Clues**

- Windelta counted turnovers (4):
- Q1 11:00 (35 yds) Pass Interception Return: (Shotgun) G.Smith pass short middle intended for J.Meyers INTERCEPTED by K.Byard at CHI 41. K.Byard to LV 24 for 35 yards (J.Powers-Johnson). [interception]
- Q1 7:21 (0 yds) Fumble Recovery (Opponent): A.Jeanty up the middle to LV 30 for -5 yards (A.Billings, N.Sewell). FUMBLES (N.Sewell), touched at LV 24, RECOVERED by CHI-T.Stevenson at LV 20. [fumble]
- Q2 8:58 (12 yds) Pass Interception Return: (Shotgun) G.Smith pass short right intended for J.Meyers INTERCEPTED by K.Byard at LV 36. K.Byard to LV 24 for 12 yards (J.Powers-Johnson). [interception]
- Q3 14:54 (3 yds) Pass Interception Return: (Shotgun) G.Smith pass deep right intended for J.Meyers INTERCEPTED by T.Stevenson at LV 43. T.Stevenson to LV 40 for 3 yards (J.Meyers; I.Thomas). CHI-T.Stevenson was injured during the play. [interception]

- Turnover-keyword plays not counted as turnovers (up to 1 shown):
- Q4 0:38 (54 yds) Blocked Field Goal: D.Carlson 54 yard field goal is BLOCKED (J.Blackwell), Center-J.Bobenmoyer, Holder-A.Cole.

- Excluded non-zero-yard plays (up to 11 shown):
- Q1 3:32 (6 yds) Penalty: PENALTY on CHI-A.Billings, Neutral Zone Infraction, 6 yards, enforced at LV 43 - No Play. [nullified]
- Q1 9:53 (19 yds) Kickoff: C.Santos kicks 58 yards from CHI 35 to LV 7. D.Laube to LV 26 for 19 yards (C.Jones; D.Hardy). [special_teams]
- Q2 0:53 (-3 yds) Kickoff: C.Santos kicks 65 yards from CHI 35 to LV 0. R.Mostert to LV 32 for 32 yards (E.Hicks).PENALTY on LV-J.Shorter, Offensive Holding, 10 yards, enforced at LV 25. [special_teams]
- Q2 4:22 (37 yds) Kickoff: C.Santos kicks 66 yards from CHI 35 to LV -1. D.Laube to LV 36 for 37 yards (D.Hardy). [special_teams]
- Q3 11:38 (-4 yds) Kickoff: C.Santos kicks 62 yards from CHI 35 to LV 3. R.Mostert to LV 36 for 33 yards (C.Jones; J.Jones).PENALTY on LV-J.Bech, Offensive Holding, 10 yards, enforced at LV 30. [special_teams]
- Q3 15:00 (22 yds) Kickoff: C.Santos kicks 60 yards from CHI 35 to LV 5. R.Mostert to LV 27 for 22 yards (J.Walker; D.Jackson). [special_teams]
- Q3 1:22 (19 yds) Punt: A.Cole punts 60 yards to CHI 32, Center-J.Bobenmoyer. D.Duvernay to LV 49 for 19 yards (M.Koonce). [special_teams]
- Q4 0:38 (54 yds) Blocked Field Goal: D.Carlson 54 yard field goal is BLOCKED (J.Blackwell), Center-J.Bobenmoyer, Holder-A.Cole. [special_teams]
- Q4 11:38 (22 yds) Kickoff: T.Taylor kicks 61 yards from CHI 35 to LV 4. R.Mostert to LV 26 for 22 yards (R.Johnson). [special_teams]
- Q4 1:34 (38 yds) Kickoff: T.Taylor kicks 61 yards from CHI 35 to LV 4. D.Laube pushed ob at LV 42 for 38 yards (T.Taylor). [special_teams]
- Q4 6:45 (29 yds) Field Goal Good: D.Carlson 29 yard field goal is GOOD, Center-J.Bobenmoyer, Holder-A.Cole. [special_teams]

- Total-yards penalty corrections (up to 1 shown):
- Q1 9:05 Rush: TotalYards -15 -> 5: T.Tucker right end ran ob at CHI 45 for 20 yards (N.Wright).PENALTY on LV-J.Meyers, Offensive Holding, 10 yards, enforced at LV 40.
