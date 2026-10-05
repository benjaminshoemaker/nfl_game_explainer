import type { Metadata } from 'next';
import Link from 'next/link';
import results from '@/data/factor-wins-2025.json';
import styles from './page.module.css';

export const metadata: Metadata = {
  title: 'How it works | NFL Game Explainer',
  description: 'Understand the eight game factors, competitive plays, and how factor wins tracked NFL results in the 2025 regular season.',
};

const factors = [
  ['Turnovers', 'Fewer is better', 'Giveaways from interceptions, lost fumbles and muffed kicks. An onside kick recovered by the kicking team also counts against the receiving team, an addition to ESPN’s official turnover total. Turnover on downs is excluded.'],
  ['Success rate', 'Higher is better', 'The share of eligible offensive plays that gain at least 40% of the yards needed on first down, 60% on second down, and 100% on third or fourth down. This measures how consistently an offense gains enough yards.'],
  ['Adjusted yards per play', 'Higher is better', 'Adjusted offensive yards divided by eligible offensive plays in the selected view. Kneels and spikes are excluded; aborted snaps are included. This can differ from official box-score yards per play.'],
  ['Explosive-play rate', 'Higher is better', 'The share of eligible offensive plays gaining at least 10 yards on a run or 20 yards on a pass dropback. Scrambles and sacks count as pass dropbacks throughout the offensive metrics.'],
  ['Points per trip', 'Higher is better', 'Average points from drives that reach the opponent’s 40-yard line, including trips that score zero. A touchdown that crosses the 40 on the scoring play also qualifies. This covers a wider area than the red zone.'],
  ['Starting field position', 'Closer to the opponent’s goal is better', 'The average starting spot of offensive drives. Own 35 is better than Own 22; Opp 32 is better still. On the opponent’s half, Opp 20 is better than Opp 32.'],
  ['Penalty yards', 'Fewer is better', 'Yards assessed against each team. Full game uses ESPN’s box score; Competitive uses accepted play-level penalties in that scope. If accepted penalty yards or team attribution are unresolved, the comparison stays undecided.'],
  ['Non-offensive points', 'Higher is better', 'Points credited to defensive and special-teams scores, such as interception and fumble returns, kick and punt returns, blocked-kick returns, and safeties. Ordinary offensive field goals are not included.'],
];
const full = results.tables.full_clean;
const competitive = results.tables.competitive_clean;
const pct = (value: number | null) => value === null ? '—' : `${value.toFixed(1)}%`;

export default function HowItWorks() {
  return <div className={styles.page}>
    <header className={styles.header}>
      <Link className={styles.brand} href="/">GAME<span>/</span>EXPLAINED</Link>
      <Link href="/">← All games</Link>
    </header>
    <article className={styles.article}>
      <div className={styles.intro}>
        <p className={styles.eyebrow}>The numbers behind the game</p>
        <h1>How it works</h1>
        <p className={styles.lede}>Eight factors help explain how a game was won. Read them together with the plays, the score, and the size of each advantage.</p>
        <nav aria-label="On this page" className={styles.contents}>
          <a href="#factor-count">Reading the count</a><a href="#results-2025">2025 results</a><a href="#eight-factors">The eight factors</a><a href="#game-scope">Game scope</a><a href="#sources">Sources & limits</a>
        </nav>
      </div>

      <section id="factor-count" className={styles.section}>
        <p className={styles.eyebrow}>01 / Reading the dashboard</p>
        <h2>What does winning 5/8 mean?</h2>
        <p>A team wins a factor when its value is better than its opponent’s in the selected view. Fewer turnovers and penalty yards are better; higher values win the other factors, with field position measured from the offense’s own goal line.</p>
        <p><strong>Tied factors count for neither team.</strong> An unavailable comparison stays undecided. The two teams’ counts therefore do not always add up to eight. For example, 5 factors for one team, 2 for the other, and 1 tie accounts for all eight.</p>
        <p>Each factor contributes one to the count, regardless of its margin. A narrow edge in yards per play counts the same as a large edge. The count does not weight importance, and the factors overlap.</p>
      </section>

      <section id="results-2025" className={styles.section}>
        <p className={styles.eyebrow}>02 / The historical check</p>
        <h2>How often did those teams win?</h2>
        <p>In the 2025 regular season, teams winning five full-game factors had an <strong>{pct(full.bins[5].win_pct)} winning percentage</strong>. At six factors, it was <strong>{pct(full.bins[6].win_pct)}</strong>.</p>
        <p>We checked all {results.games} games. After excluding games with source discrepancies or unavailable comparisons, {full.games} games remained for Full game and {competitive.games} for Competitive. Playoffs are excluded.</p>
        <p className={styles.scrollHint}>Scroll the table sideways to compare both views →</p>
        <div className={styles.tableWrap} role="region" aria-label="2025 factor wins and game results" tabIndex={0}>
          <table>
            <caption>2025 regular season · final statistics</caption>
            <thead>
              <tr><th scope="col" rowSpan={2}>Factors<br />won</th><th scope="colgroup" colSpan={3}>Full game · {full.games} games</th><th scope="colgroup" colSpan={3}>Competitive · {competitive.games} games</th></tr>
              <tr><th scope="col">W–L–T</th><th scope="col">Teams*</th><th scope="col">Win %</th><th scope="col">W–L–T</th><th scope="col">Teams*</th><th scope="col">Win %</th></tr>
            </thead>
            <tbody>{full.bins.map((row, index) => {
              const comp = competitive.bins[index];
              return <tr key={row.factors}><th scope="row">{row.factors}/8</th>
                <td>{row.wins}–{row.losses}–{row.ties}</td><td>{row.teams}</td><td className={styles.percentage}>{pct(row.win_pct)}</td>
                <td>{comp.wins}–{comp.losses}–{comp.ties}</td><td>{comp.teams}</td><td className={styles.percentage}>{pct(comp.win_pct)}</td>
              </tr>;
            })}</tbody>
          </table>
        </div>
        <p className={styles.note}>*Team appearances, not distinct franchises. Each game contributes two observations. W–L–T means wins, losses and ties. Winning percentage = (wins + ½ × ties) ÷ team appearances.</p>
        <aside className={styles.callout}><strong>A strong association, with limits.</strong><p>These are statistics measured at the end of the game. Points per trip and non-offensive points incorporate scoring directly, while several efficiency factors overlap. This table does not establish prediction accuracy before kickoff or at halftime. Only four teams went 8/8 in the Full game sample; their 100% record is not a guarantee.</p></aside>
        <details className={styles.details}>
          <summary>How we checked the 2025 sample</summary>
          <p>We calculated the factors from ESPN game summaries using the same metric and comparison rules as the dashboard. All 272 game IDs and final score pairs matched the nflverse schedule. Ties were determined from the returned metric values, including the displayed whole-yard field position.</p>
          <p>Full game excluded 15 games where parsed yardage, turnovers or offensive-play counts did not reconcile with the box score, plus one game with an unavailable factor comparison. Competitive excluded 28 games in total: 15 with source discrepancies, 5 with unavailable comparisons (including one already excluded for a discrepancy), and 9 with less than 95% play-level win-probability coverage. Competitive also required a structured penalty feed.</p>
          <p>A rate, trip or field-position comparison needs a nonempty eligible sample for both teams. The larger sample thresholds used to draw bars do not change the factor count. Unavailable factors were never treated as losses in this table.</p>
          <p>As a sensitivity check, including all 272 games gave a full-game win rate of {pct(results.tables.full_all.bins[5].win_pct)} at 5/8 and {pct(results.tables.full_all.bins[6].win_pct)} at 6/8, close to the checked sample. This is a fixed analysis prepared October 4, 2026, not a live-updating forecast.</p>
        </details>
      </section>

      <section id="eight-factors" className={styles.section}>
        <p className={styles.eyebrow}>03 / The definitions</p>
        <h2>The eight factors</h2>
        <p>The framework builds on efficiency, explosiveness, finishing drives, field position and turnovers, with penalties and non-offensive scoring providing additional context.</p>
        <div className={styles.factors}>{factors.map(([name, direction, description], index) => <div className={styles.factor} key={name}>
          <span className={styles.number}>{String(index + 1).padStart(2, '0')}</span>
          <div><h3>{name}</h3><p className={styles.direction}>{direction}</p><p>{description}</p></div>
        </div>)}</div>
        <p className={styles.note}>Offensive rates use eligible plays under the app’s parsing rules, rather than every line in the play feed. Kneels, spikes, special-teams plays, penalty-only plays and nullified plays are excluded; credited action on some penalty plays can still count.</p>
      </section>

      <section id="game-scope" className={styles.section}>
        <p className={styles.eyebrow}>04 / Choose the lens</p>
        <h2>Competitive or Full game?</h2>
        <p><strong>Full game</strong> uses the whole game’s available data. The offensive-play exclusions described above still apply.</p>
        <p><strong>Competitive</strong> keeps the game through the latest play where both teams’ win probabilities are below 97.5% at the start or end of the play. Everything before that point stays included. Only the trailing stretch after the last competitive state is removed.</p>
        <p>If a comeback brings the game back into range, earlier plays return to the sample. Plays with incomplete win-probability data are conservatively retained. If the feed is unavailable, the app falls back to full-game data and identifies that limitation.</p>
        <h3>What do the bars mean?</h3>
        <p>The shaded value identifies the factor leader. The bar compares the size of the gap with a historical large-gap reference for that factor and view, capped at a full bar. It does not measure how much that factor caused the win.</p>
        <p>The references are rounded 90th percentiles of nonzero gaps from 224 completed 2025 games in weeks 1–15, with checks against 2026 weeks 1–3 and usable 2024 data. That calibration sample is separate from the full-season outcome study above.</p>
        <p>Bars require at least 20 eligible offensive plays per team for rate factors, two trips per team for points per trip, or five drive starts per team for field position. Ties and unresolved comparisons have no bar. Live bars use completed-game references, so their scale is provisional.</p>
      </section>

      <section id="sources" className={styles.section}>
        <p className={styles.eyebrow}>05 / Sources & limits</p>
        <h2>Follow the numbers back to the plays</h2>
        <p><a href="https://www.espn.com/nfl/scoreboard">ESPN</a> supplies game scores, box scores, play-by-play and win probabilities. The app calculates the derived factors from that feed. Expand a factor on a game page to inspect its supporting plays and drives.</p>
        <p>Live data can arrive late or be corrected. A source-gap notice means the available plays do not reproduce official totals; play-derived factors may be incomplete even when the final score is correct. Missing values remain unavailable rather than becoming zero.</p>
        <h3>WP and EPA</h3>
        <p><strong>WP</strong> is a team’s win probability. A change from 40% to 50% is a rise of 10 percentage points (pp), not 10%.</p>
        <p><strong>EPA</strong> estimates expected points added by a play for the team named on its card. It uses the <a href="https://www.nflfastr.com/">nflfastR</a> expected-points model and a separate 2025 field-goal baseline. A live estimate may wait for the next play’s state; unsupported or incomplete inputs stay unavailable.</p>
        <p>The 2025 outcome study used the <a href="https://github.com/nflverse/nfldata/blob/master/data/games.csv">nflverse game schedule</a> to cross-check game coverage and final scores. Final-stat associations do not establish that any single factor caused a result.</p>
      </section>
      <footer className={styles.footer}><span>Methodology & 2025 study · October 4, 2026</span><Link href="/">Explore the games →</Link></footer>
    </article>
  </div>;
}
