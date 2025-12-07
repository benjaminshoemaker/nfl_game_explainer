# AI game summary prioritization for NFL: A research-backed framework

When explaining why a team won an NFL game in 280 characters, **turnovers and explosive plays should dominate narratives for close games, while efficiency metrics lead for blowouts**. Win probability analysis reveals that plays with ≥20% WP delta are "game-changing" and warrant headline treatment, while sustained accumulation patterns call for systemic narratives. The analytics consensus places turnover margin (~4 points per turnover, 70% win rate when winning the battle) and explosiveness (86% win rate) as the most impactful single-game factors, though efficiency proves more predictive across seasons.

## Factor hierarchy from the analytics literature

Bill Connelly's Five Factors framework, validated across decades of football data, provides the clearest empirically-backed hierarchy. When teams win each factor, their overall win percentages are: **explosiveness 86%**, efficiency 83%, drive finishing 75%, turnovers 73%, and field position 72%. However, Football Outsiders' DVOA methodology weights turnovers at only 75% of face value for predictive purposes because turnover margin regresses heavily year-to-year—approximately 45% of variance is attributable to luck.

The recommended prioritization for the user's 10 factors, synthesized from PFF, ESPN FPI, Football Outsiders, and Connelly:

**Tier 1 (Highest explanatory power):**
- **Turnovers**: ~4 points per turnover swing; teams winning the turnover battle win 69.6% of games. Each additional positive turnover worth ~0.2 wins.
- **Non-offensive points**: Pick-sixes, fumble returns, and special teams TDs provide immediate 4-7 point swings plus field position; rare enough to be narrative-worthy.
- **Explosive play rate**: Drives with explosive plays see expected points nearly quadruple. Only 2.3% of runs become explosive vs. much higher rates for passes.

**Tier 2 (Strong explanatory power):**
- **Success rate**: 83% win rate when winning this battle; more stable game-to-game than explosiveness.
- **Points per trip inside 40**: Red zone efficiency distinguishes grinding teams from scoring teams; 75% win rate when won.

**Tier 3 (Contextual importance):**
- **Average starting field position**: 72% win rate; often derivative of other factors (turnovers, special teams).

## Decision rules for narrative selection

**Lead with a single play when:**
- The play's WP delta exceeds 20% (see thresholds below)
- The play occurred in the 4th quarter or overtime
- WP never returned to competitive range (40-60%) after the play

**Lead with a "despite" narrative when:**
- The winning team lost more than 2 of the categories
- Turnover margin, explosive plays, or non-offensive points explain the discrepancy. Research shows teams win "despite losing stats" primarily through turnovers (each worth ~4 points), explosive plays (which can offset sustained drives), and special teams scores

**Lead with a dominant factor when:**
- No single play exceeds 15% WP delta
- One factor shows clear statistical dominance (e.g., +3 turnover margin, 200+ yard rushing advantage)
- The game was a blowout (17+ points) where sustained excellence drove the outcome
- WP trajectory shows steady directional movement ("ramp" pattern) rather than discrete jumps

**Lead with a "comeback" narrative when:**
- If winner dropped below 25% at any point, "comeback" narrative applies; the lower the nadir, the stronger the comeback story

## Win probability delta thresholds

Analysis of ESPN's playoff WP charts and nflfastR methodology suggests these thresholds for categorizing play significance:

| Category | WP Delta | Decision Rule |
|----------|----------|---------------|
| **Game-changing** | ≥20% | Must mention; often should lead the summary |
| **Major impact** | 15-19% | Strong candidate for mention; lead if no 20%+ plays exist |
| **Key play** | 10-14% | Worth mentioning if space permits; mention if clusters with other key plays |
| **Moderate impact** | 5-9% | Only mention if exemplifies dominant theme or no bigger plays occurred |
| **Routine** | <5% | Do not mention individually; may be part of "sustained drives" narrative |

Real-world calibration from ESPN analysis: a 36.5% WP swing was described as "most valuable play"; 29-31% swings characterized "game-defining" moments; 13-15% swings marked "critical conversions" and "key interceptions." These thresholds should adjust based on game context—the same 15% WP swing carries different narrative weight in a blowout versus a game that remained competitive throughout.

## Play-by-play analysis guidance for identifying narratives

**Detecting narrative types from WP shapes:**
- **Step function**: Large discrete jumps indicate big-play narrative; identify the largest step
- **Ramp**: Gradual consistent slope indicates grinding/dominant performance
- **Sawtooth**: Up-and-down oscillation indicates competitive back-and-forth
- **Cliff**: Sharp drop that never recovers indicates "the play that broke it open"

**Looking for clusters vs. single spikes:** The system should identify whether the decisive WP movement came from one play or a sequence. Calculate WP delta for each drive, not just each play. If a single drive (multiple plays) produced 30%+ cumulative WP swing, the drive itself becomes the story rather than any individual play within it.

## Anti-patterns to avoid

Research on automated sports journalism and analytics framing reveals several pitfalls:

**Overclaiming causation:** Sports statistics are correlational. Avoid "Team X won *because of* turnovers" when "Team X won *with* a +3 turnover margin" is more accurate. The user's research question correctly identifies this concern—use language like "contributed to," "coincided with," "capitalized on" rather than causal claims. Turnovers correlate with wins, but defensive dominance may cause both the turnovers and the win.

**Ignoring regression to mean:** Turnover margin explains 41.9% of season-level win variance, but teams with extreme margins regress heavily (double-digit positive margins see an average 10.3-point decrease the following year). Don't frame fluky turnover games as sustainable patterns.

**Leading with penalty yards:** Penalties have the weakest correlation with outcomes among the 10 factors. Unless a specific penalty directly decided the game (pass interference in the end zone, roughing the passer extending a scoring drive), don't lead with penalty yards.

**Generic descriptors without specificity:** "Great game" or "big win" waste characters. Every word must add information. "Cruised past" implies blowout; "escaped" implies close game—the verb does the descriptive work.

**Burying the score:** Professional sports tweets virtually always include the final score. Even when leading with a narrative hook, the score should appear within the first sentence.

**Confusing correlation with prediction:** Just because a team that won the turnover battle won this game doesn't mean turnovers "predicted" the outcome—they happened during the game. Frame as description, not prediction.

**Treating possession count without context:** More possessions can mean defensive excellence (forcing quick punts) or offensive dysfunction (quick three-and-outs). Never mention possession count without explaining what drove it.

**Over-indexing on yards:** Teams that lose yardage battles win approximately 30% of the time—common enough that "won despite being outgained" is a frequent legitimate narrative. Don't treat yardage as deterministic.

**Ignoring WP trajectory for late-game plays:** A 4th-quarter interception may have a 25% WP delta while a 1st-quarter interception in the same situation has only 8%. The same play means different things at different times—weight late-game plays appropriately.

**Missing cluster patterns:** If three consecutive plays each produced 8% WP swings, that drive (24% cumulative) matters more than any single 15% play. Look for momentum-building sequences, not just isolated spikes.

## Synthesis: The complete decision framework

For each game, the AI system should execute this sequence:

1. **Calculate WP metrics**: Find max single-play WPA, accumulation ratio, 50% crossings, winner's minimum WP
2. **Identify narrative pattern**: Classify as blowout, controlled, comeback, back-and-forth, or single-play-decisive based on WP shape
3. **Rank the 10 factors**: Order by deviation from opponent (standardized), with Tier 1 factors weighted highest
4. **Check for "despite" trigger**: If winning team lost 3+ stat categories, activate despite-narrative mode
5. **Select lead**: Apply decision rules—single play if WPA ≥20% and game-deciding; dominant factor if no play ≥15% and clear statistical edge; despite narrative if activated; score itself for historic margins
6. **Apply verb intensity**: Match outcome verb (cruised/edged/survived) to point margin and WP trajectory
7. **Fill remaining characters**: Add star stat line, context, or supporting factor based on available space

This framework balances the analytics literature's factor hierarchy with professional journalism's narrative instincts, producing summaries that are both statistically grounded and narratively compelling.