# Team seasons and predictive power rankings

Accepted direction, October 4, 2026. This is the working plan for this feature;
metric definitions live in `documentation.txt`, usage in `README.md`, and
generated evidence in `game_summaries/team_seasons/`.

## Product decisions

- Add a Teams directory, team-season pages, Power Rankings, rating methodology,
  and prediction results. Reuse the site's methodology surface where useful;
  distinguish descriptive same-game studies from predictive evaluation.
- Team pages show season performance through all eight factors, including the
  team's own output, opponents' output, and net performance. Include values,
  league ranks, league context, coverage, and a schedule linking to game pages.
- Predicted strength belongs in a distinct **Power Rankings** section on the
  team page. Do not add a game-by-game heatmap or a selectable factor/rating
  history chart to that page.
- Power Rankings supports plotting any two metrics across the league and
  comparing any number of selected teams on eight-factor radar plots. Provide
  a readable table or small multiples when overlays get crowded. Preserve
  filters in shareable URLs.
- Keep the eight factors central. Prior-season performance is an acceptable
  model input; other additions need demonstrated incremental predictive value.
- Exclude betting odds, Vegas rankings, market priors, and imported commercial
  ratings from model features. Those may be independent comparison baselines,
  not ingredients. Do not indirectly import them via pregame WP filters.
- Begin with current and previous completed seasons on the product; audit more
  seasons for research. Default to full-game regular-season statistics, keep
  playoffs separate, and use completed games with explicit publication cutoffs.

## Sequence and status

1. **Exact data foundation and coverage audit: implemented.**
   `api/lib/team_season.py` builds paired descriptive factors from the existing
   canonical game parser's unrounded counters. The research builder produces
   schedule-checked season and weekly snapshots, source checksums, game rows,
   and coverage reports. The independent audit recomputes the three efficiency
   factors from nflverse, using this app's success and explosive definitions.
2. **Resolve the source/definition discrepancies.**
   The first audit includes all 272 regular-season games in 2024 and 2025 and
   all 48 games through Week 3 of 2026. Independent counter agreement is
   233/544, 528/544, and 84/96 team-games respectively. These are exact
   four-counter matches, not estimated error rates. They do not independently
   validate finishing drives, field position, turnovers, penalties, or scoring.
   Keep discrepancies explicit; do not replace missing values with zero or
   blend providers without provenance and a defined adapter.
3. **Review a real-data interactive prototype.**
   Include strong/weak teams, ties, byes, zero opportunities, and incomplete
   sources. Use the established visual direction. Do not invent power ratings
   to fill the prototype. Productionize after the shared presentation is sound.
4. **Run chronological predictive experiments.**
   Compare an interpretable eight-factor model with conservative prior-season
   information, opponent-adjusted point differential, Elo, and EPA baselines.
   Fit only on earlier data; tune and test on distinct later periods. Learn
   offense/defense adjustments jointly, stabilize small samples, account for
   overlapping factors, and permit near-zero predictive weights.
5. **Publish ratings with explanations and an accuracy archive.**
   Publish only supported claims. Evaluate scoring-margin error, probability
   loss/calibration, uncertainty, and early/late-season behavior. Obtain and
   verify historical benchmark snapshots before making FPI/DVOA comparisons.

## Current data boundary

User selected nflverse as the analysis source. The dedicated adapter and
builder now produce all eight factors without blending ESPN data. All 592
final scores reconcile across 2024, 2025, and 2026 through Week 3. Every factor
has complete coverage for all 32 teams in 2024 and the 2026 snapshot. Two 2025
games retain explicit source ambiguities (drive start and multiple fumbles).

The interactive prototype is implemented in `prototypes/team-seasons.html`;
`research/render_team_prototype.py` embeds the audited snapshots into a portable
review file under `game_summaries/nflverse/`. It includes the directory, team
pages, scatterplot, radar plus comparison table, methodology, and an honest
unpublished prediction-results state. Production routes and the trained model
remain pending. The original ESPN discrepancy counts above describe the earlier
cross-provider audit and do not gate the selected nflverse data.

Next: chronological predictive experiments, conservative prior-season
shrinkage, opponent adjustment, and baseline evaluation. Do not present source
completeness or same-game correlation as proof of forecast quality.

## Predictive experiment v1 completed

`research/team_power_model.py` implements joint opponent adjustment, conservative
previous-season priors, chronological training/selection/evaluation, simple
baselines, per-game prediction exports, probability calibration, week-block
uncertainty, and additive experimental team contributions. Tests guard future
week isolation, missing observations, prior shrinkage, adjustment direction, and
training-only scaling. The prototype's Prediction results page shows the output.

Held-out 2024–2025 margin RMSE is 13.006 for eight factors versus 13.027 for
opponent-adjusted point differential; the difference interval crosses zero.
Probability scores are worse. This is no demonstrated predictive advantage.
Do not publish superiority claims or silently tune against the now-observed
test. Next research should preregister ablations and a new evaluation policy,
address probability calibration, and acquire dated FPI/DVOA benchmarks before
claiming competitiveness. Production integration remains pending.

## Predictive experiment v2 completed

The requested smaller-factor, point-plus-factor, separate-side, stabilization,
and recency experiments are implemented in `research/team_power_experiments.py`.
Reports and full provenance are in `game_summaries/nflverse/model-v2/`.
Selection uses six rolling validation seasons (2018–2023), with yearly training
updates and strict earlier-week features. 2024–2025 remains a disclosed,
already-inspected follow-up sample. The original experiment is preserved.

Validation favors point differential plus success rate, yards per play, and
points per trip. The fewer-factor family selects seven factors (omits explosive
rate), with negligible change relative to eight. Separate sides gives the lowest
combined follow-up margin RMSE, but every nonbaseline difference interval crosses
zero. All nonbaseline models improve 2024 margin error and worsen 2025 versus the
point baseline. Stronger prior stabilization and an eight-week recency half-life
win validation, with mixed follow-up effects. No production rating is promoted.

## Active goal: extended predictive search (round three)

The user explicitly authorized a persistent goal to find a model that beats a
fairly tuned opponent-adjusted point-differential baseline. Do not mark success
from exploratory gains or a weaker selected comparator. The goal remains active.

New research code: `team_power_extended_data.py` creates strict earlier-week
passing/rushing rates, opportunity-normalized turnovers/penalties/non-offensive
points, several stabilization/recency estimates, and whitelisted rest/neutral
schedule context. `team_power_flexible.py` tests ridge, elastic net, nonlinear
boosting, and separate probability-focused selection. Artifacts live in
`game_summaries/nflverse/model-v3/`; earlier rounds remain intact. All 45 focused
checks passed before the convergence guard refinement. The restored 2025 PBP
matches its original manifest checksum exactly.

The initial flexible run produced modest exploratory improvements, but some
unselected elastic-net candidates failed convergence. A corrected search is
running with a larger iteration allowance, reproducible randomized coordinate
updates, and explicit failed-candidate recording. No unconverged model may be
selected. Its authoritative process is unified exec session 92513; inspect that
handle or process state before restarting. Next: verify terminal status and
results, compare against BOTH the v3 validation-selected baseline and the stronger
v2 follow-up baseline, then pursue chronological nested evaluation and additional
non-market inputs. No evidence yet proves the full goal achieved. 2024–2025 is
still development follow-up, not a newly untouched test.

Round-three corrected run finished successfully (session 92513 exit 0). The three extended tests pass after the convergence guard. Stronger-baseline comparison is saved in model-v3/stronger-baseline-audit.json. Inspect that evidence next; do not restart the completed job.

## Nested replay completed (round four)

`research/team_power_nested.py` and three regression tests implement annual outer
evaluation 2018–2025, with candidate selection on only the preceding three
seasons' rolling forecasts. Completed unified exec session 23192 returned exit 0;
no convergence failures were recorded. Artifacts: `model-v4-nested/`.

The selected-nonbaseline procedure improves margin RMSE from 13.2453 to 13.1797,
winning six of eight seasons. Season-block bootstrap difference interval is
[-0.1297,-0.0067] points. Probability selection remains inconclusive. These are
retrospective development results: candidate families were designed after recent
outcomes were inspected, and intervals do not erase research-design hindsight.
The goal is NOT yet marked complete. Next: compare against fixed strong v2
baseline settings and a broader properly venue-adjusted point baseline, audit
selection artifacts/cutoffs, and assess remaining non-market information.
The external source review found official nflverse issue reports of missing
2025 injury data; no injury inputs have been downloaded or silently imputed.

## Stronger baseline audit completed (round five)

`research/team_power_baseline_audit.py` jointly fits team strength and venue
advantage, recognizes neutral sites, tests rest, expands priors/recency, and
selects settings only on preceding-three-season forecasts. Original baseline
candidates remain eligible. The candidate predictions are unchanged from v4.
Session 40199 completed with exit 0; three new regression tests passed.

Candidate RMSE remains 13.1797. Expanded comparator is 13.2543, but the paired
season interval is [-0.1615,+0.0049]. Fixed strong v2 comparator is 13.2155 with
interval [-0.0971,+0.0355]. Thus the earlier apparent significant gain is not
robust to comparator checks; do NOT mark the goal complete or claim superiority.
Artifacts are in `model-v5-baseline/`, including every outer-season selection
and game-level predictions. Next: useful additional non-market information,
especially situation-adjusted efficiency and QB continuity with strict pregame
availability. Existing nflfastR EPA support can inform research, but its fitted
model vintage must be considered before treating provider EPA as temporally
independent; avoid silently importing a model trained on future outcomes.

## Situation and quarterback-history experiment completed (round six)

`team_power_situation.py` builds early-down and close-state efficiency plus
past-only QB-usage features. No next-game starter, injury, WP, market, or EPA
fields are used. For all games in a week, QB features are computed before any
same-week usage is ingested. The last observed team passer is used only as a
historical proxy, with missingness and sample size; it is not asserted to be
the next starter. `team_power_situation_experiment.py` declares a bounded set
and reuses nested annual evaluation. `team_power_nested.run` now accepts an
optional output directory, preserving earlier artifacts. Sessions 89277 and
16168 completed with exit 0. All 53 focused tests passed.

Artifacts: `model-v6-situation/nested/` and `stronger-baseline-audit.json`.
Selected-nonbaseline margin RMSE = 13.1220; prior fixed-v2 baseline = 13.2155.
Against fixed-v2, difference -0.09355 with season-block interval
[-0.182197,-0.015453]. Against expanded venue baseline, difference -0.13236 with
interval [-0.239379,-0.046280]. Against original nested baseline, difference
-0.12328 with interval [-0.226704,-0.046991]. The selection procedure beats the
original nested baseline in all eight outer seasons, selecting qb_history or
qb_history_elastic in every outer year. Additional situation splits do not drive
the selected result. Probability selection also improves its original baseline
with an interval excluding zero; broader probability comparator audit remains.

This is the first candidate to survive all tested margin comparator checks.
It is still retrospective development, with research-design hindsight disclosed.
Goal remains active pending final leakage/provenance/selection audit, a usable
frozen model artifact, and assessment of what improvement is due to QB data versus
eight-factor inputs (point-plus-QB ablation). Do not re-run completed sessions.

## Final audit completed

Session 12531 finished with exit 0. `team_power_final_audit.py` verified all 47
source hashes, exactly replayed all eight annual choices and 2,127 forecasts,
and exported a 2026-intended linear margin model using no 2026 outcomes. The
raw coefficient formula matches the fitted pipeline to 1e-10 points. All 55
focused regression tests pass. Point-plus-QB ablation RMSE is 13.1762 versus
13.1220 for the full procedure, with interval [-0.1120,-0.0041].

The full requirement-by-requirement audit and qualified conclusion are in
`game_summaries/nflverse/model-v7-audit/FINDINGS.md`. The baseline-comparison
research objective is achieved in historical chronological replay. This is not
prospective proof, an FPI/DVOA comparison, or completion of production team-page
integration. No game-highlight weights or production ratings were changed.

## Expected-strength review integration (2026-10-05)

Implemented the frozen model's centered team-strength component in
`research/team_power_ratings.py`, preserving the exact coefficient artifact in
`research/models/`. Rank all 32 teams under equal conditions; exclude intercept,
rest and venue/designation terms from league strength. Actual matchup inference
retains the original formula in `predict_matchup`. Neutral rank differences
match the antisymmetric average of that formula over both designations.

Connected the 2026 Week-3 snapshot to directory cards, team power sections,
component breakdowns, rankings table, hypothetical neutral comparison and
scatterplot axes. Updated methodology/results to the final research evidence
and explicitly distinguish annual retrospective evaluation from the frozen
coefficient vector and from a prospective archive. No season forecast added.

The missing 2026 PBP file was downloaded from official nflverse; its checksum
is newer than the original snapshot. QB aggregation admits only game IDs in
the through-week snapshot and records the refreshed file hash. Week 4 data is
excluded. Historical factor inputs remain the audited snapshots.

This is a local review integration, not a production deployment. Prospective
publication and baseline archiving still require a separate operational flow;
no completed game has been relabeled a pregame prediction.

## Team power context (2026-10-05)

Added fixed training-reference standardized component weights with exact
coefficient disclosure, tied league component ranks, a ten-spoke percentile
radar comparing the actual 16th- and 1st-overall teams, and corresponding
comparison columns. Added point gaps to both benchmarks. Grouped contributions
are ranked, not raw season rates. The frozen prediction formula is unchanged.

## Calculation walkthrough (2026-10-05)

Added raw factors and added-input rows, controlled current-season opponent
comparison, expandable exact per-term arithmetic, and the three-subtotal
rating equation. Diagnostic opponent-off fitting holds real priors/recency/
regularization fixed and never changes the published ratings. Tests cover
harder-opponent credit, unchanged priors without observations, and end-to-end
term/component/rating reconciliation.

## Opponent-adjustment explainer (2026-10-05)

Added an explanation before Step 2 of the joint league fit, factor-specific
opponent effects and their conversion into points. Added current-season
adjustment impact, league impact rank, before/after ratings, observed opponents,
league median/extremes, expandable all-team comparison and component changes.
Counterfactual QB/context remain unchanged; prior, recency and coefficients
are held fixed. The published model/rankings are unchanged.

## Schedule clarity and conservative-adjustment audit

User excluded proposed item 2 (a side-by-side schedule difficulty/adjustment/
before-after-rating display). Replaced the confusing adjustment-impact callout
with a schedule-only measure: equal-weight opponent strength, focal current-
season games excluded, rank 1=hardest, per-opponent detail and league table.
Added exact current-data/prior contribution decomposition, with QB separate.

Completed bounded chronological audit of less prior influence, amplified
opponent adjustment and explicit schedule features; tested early/late and
extreme schedule groups against incumbent and strong PD baseline. No reliable
overall gain (13.1286 vs 13.1236 incumbent RMSE; 4/8 seasons improved). Preserve
frozen model. No replacement was promoted; prospective validation is still
required before promoting a future candidate. Report: model-v8-schedule.
