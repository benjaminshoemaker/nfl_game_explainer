'use client';

import { useState } from 'react';
import type { PregamePreview, PreviewMetric, PreviewTeam } from '@/types';
import styles from './PregameReport.module.css';

const FACTOR_UNITS: Record<string, string> = {
  point_margin: 'Points / game', success_rate: 'Percentage points', yards_per_play: 'Yards / play',
  explosive_rate: 'Percentage points', points_per_trip: 'Points / trip inside 40',
  turnovers: 'Takeaways − giveaways / game', field_position: 'Yards of field position',
  penalties: 'Opponent − own yards / game', non_offensive_points: 'Points / game',
};
const formatNet = (key: string, value: number | null) => value == null ? '—'
  : signed(['success_rate', 'explosive_rate'].includes(key) ? value * 100 : value);
const seasonNet = (team: PreviewTeam, key: string) => key === 'point_margin' ? team.scoringMarginPerGame ?? null : team.factors[key]?.net.value ?? null;
const MATCHUP_KEYS = ['success_rate', 'yards_per_play', 'explosive_rate', 'points_per_trip'];
const signed = (value: number) => `${value < 0 ? '−' : '+'}${Math.abs(value).toFixed(2)}`;
const format = (key: string, value: number | null) => value == null ? '—'
  : ['success_rate', 'explosive_rate'].includes(key) ? `${(value * 100).toFixed(1)}%`
    : key === 'field_position' ? `${value > 50 ? 'Opp' : 'Own'} ${(value > 50 ? 100 - value : value).toFixed(1)}` : value.toFixed(2);
const rank = (metric: PreviewMetric) => metric.rank == null ? 'Unranked' : `${metric.tied ? 'T-' : '#'}${metric.rank}`;

export function PregameReport({ preview: p }: { preview: PregamePreview }) {
  const [offense, setOffense] = useState(p.away);
  const [modelOpen, setModelOpen] = useState(false);
  const teams = Object.fromEntries(p.teams.map(team => [team.id, team]));
  const ratings = Object.fromEntries(p.power.map(team => [team.id, team]));
  const away = teams[p.away], home = teams[p.home];
  const defense = offense === p.away ? p.home : p.away;
  const netDifference = (key: string) => {
    const a = seasonNet(away, key), h = seasonNet(home, key);
    return a == null || h == null ? null : a - h;
  };
  const labels = Object.fromEntries(p.factors.map(factor => [factor.id, factor.label]));
  labels.point_margin = 'Scoring margin'; labels.quarterback = 'QB history';
  const entries = Object.keys(ratings[p.away].contributions).map(key => ({
    key, gap: ratings[p.away].contributions[key] - ratings[p.home].contributions[key],
  })).sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap));
  const extent = Math.max(1, Math.ceil(Math.max(...entries.map(entry => Math.abs(entry.gap)))));
  const influenceMax = Math.max(5, Math.ceil(Math.max(...Object.values(p.weights)) / 5) * 5);
  const ratingGap = ratings[p.away].rating - ratings[p.home].rating;
  const context = -p.model - ratingGap;
  const edge = (value: number) => Math.abs(value) < 0.005 ? 'Even' : `${value > 0 ? away.abbr : home.abbr} +${Math.abs(value).toFixed(2)}`;
  const projection = Math.abs(p.model) < 0.05 ? 'Even matchup' : `${p.model > 0 ? home.abbr : away.abbr} by ${Math.abs(p.model).toFixed(1)}`;
  const evidenceText = (id: string) => {
    const [teamId, key, side] = id.split('.');
    const metric = teams[teamId]?.factors[key]?.[side as 'own' | 'opponent'];
    if (!metric) return null;
    const name = key === 'turnovers' ? side === 'own' ? 'Giveaways / game' : 'Takeaways / game'
      : `${labels[key]}${side === 'opponent' ? ' allowed' : ''}`;
    return `${teamId} ${name}: ${format(key, metric.value)} (${rank(metric)})`;
  };

  return <article className={styles.report} aria-label="Pregame report">
    <div className={styles.kicker}>The pregame brief · Week {p.week} · Season data through Week {p.throughWeek}</div>
    <header className={styles.matchHeader}>
      {[away, home].map((team, i) => <div key={team.id} className={i ? styles.homeTeam : styles.awayTeam}>
        <span className={styles.monogram}>{team.abbr}</span><div><h2>{team.name}</h2>
          <p>{team.record.wins}–{team.record.losses}{team.record.ties ? `–${team.record.ties}` : ''} · Power rank #{ratings[team.id].rank}</p></div>
      </div>)}
    </header>
    <div className={styles.gameNav}>Game preview <span>Live report at kickoff</span></div>
    <div className={styles.lead}>
      <div><div className={styles.kicker}>{p.narrative ? 'The matchup in a sentence' : 'Season matchup'}</div>
        <h1>{p.narrative?.headline || `${away.name} at ${home.name}`}</h1>
        <p>{p.narrative?.summary || `Compare each offense with the opposing defense, then see what drives the difference in rated strength.`}</p>
      </div>
      <aside className={styles.model}><div className={styles.kicker}>Model outlook</div><strong>{projection}</strong>
        <p>Projected margin, including venue and rest.</p>
        <a href="#pregame-model" onClick={() => setModelOpen(true)}>What goes into this? ↓</a>
      </aside>
    </div>
    <section aria-labelledby="pregame-matchup"><div className={styles.sectionHeading}><h2 id="pregame-matchup">When they have the ball</h2><span>Season production meets opponent prevention</span></div>
      <div className={styles.tabs} role="group" aria-label="Choose offense">{[away, home].map(team =>
        <button type="button" key={team.id} aria-pressed={offense === team.id} onClick={() => setOffense(team.id)}>{team.abbr} on offense</button>)}</div>
      <div aria-live="polite"><div className={styles.tableHead}><span>Season metric</span><span>{offense} offense</span><span>{defense} defense · allowed</span></div>
        {MATCHUP_KEYS.map(key => <div className={styles.metric} key={key}><div>{labels[key]}</div>
          {[teams[offense].factors[key].own, teams[defense].factors[key].opponent].map((metric, i) => <div key={i} className={styles.metricValue}>
            <strong>{format(key, metric.value)}</strong><span>{rank(metric)}</span>
            {metric.percentile != null && metric.rank != null && <div className={styles.track} aria-hidden="true"><i style={{ left: `${metric.percentile}%`, background: (i ? defense : offense) === p.away ? 'var(--data-away)' : 'var(--data-home)' }} /></div>}
          </div>)}</div>)}
      </div>
      <p className={styles.note}>Dots show league standing: left = #32 (worst), right = #1 (best). Season averages describe past games; they do not predict this game.</p>
    </section>
    {p.narrative && <section aria-labelledby="pregame-watch"><div className={styles.sectionHeading}><h2 id="pregame-watch">Things to watch</h2><span>AI-generated from the season data</span></div>
      <div className={styles.watch}>{p.narrative.watchPoints.map((point, i) => <article key={point.title}>
        <div className={styles.kicker}>{String(i + 1).padStart(2, '0')}</div><h3>{point.title}</h3><p>{point.body}</p>
        <ul>{point.factIds.map(id => <li key={id}>{evidenceText(id)}</li>)}</ul>
      </article>)}</div>
    </section>}
    <section aria-labelledby="pregame-drivers"><div className={styles.sectionHeading}><h2 id="pregame-drivers">What separates these teams?</h2><span>Rating drivers · through Week {p.throughWeek}</span></div>
      <p className={styles.driverIntro}>{Math.abs(ratingGap) < 0.005 ? 'The teams have equal ratings.' : `${ratingGap > 0 ? away.name : home.name} are rated ${Math.abs(ratingGap).toFixed(1)} points better on a neutral field at equal rest.`}</p>
      <p className={styles.edgeExplanation}>Read left to right: each team’s net season performance, the difference ({away.abbr} minus {home.abbr}), then how strongly the model generally uses that factor. The final column shows that factor’s contribution to the <b>neutral-field rating edge</b>, in points at equal rest.</p>
      <details className={styles.edgeHelp}><summary>How model edge works</summary>
        <p>Net difference is the raw gap in the factor’s own units. Model influence describes typical contribution size in training data—it is not a multiplier. The model uses fitted coefficients on opponent-adjusted offensive, defensive and net inputs, weighted toward recent games and blended with prior-season evidence.</p>
        <p>For yards per play, {away.abbr} has a net of {formatNet('yards_per_play', away.factors.yards_per_play.net.value)} and {home.abbr} has {formatNet('yards_per_play', home.factors.yards_per_play.net.value)}: a difference of {formatNet('yards_per_play', netDifference('yards_per_play'))} yards/play. After the model’s adjustments, the point contributions are {signed(ratings[p.away].contributions.yards_per_play)} and {signed(ratings[p.home].contributions.yards_per_play)}. Subtracting those gives {signed(ratings[p.away].contributions.yards_per_play - ratings[p.home].contributions.yards_per_play)} points toward the neutral-field rating edge.</p>
        <p>Each row explains part of the total rating gap, not a separate predicted winning margin. Influence percentages total 100% but do not measure predictive accuracy. Team net values are production minus opponents’ production, reversed for turnovers and penalties so positive is better. Scoring margin is the observed points differential per game. QB history combines several inputs; no single observed value is supplied for it.</p>
      </details>
      <div className={styles.driverTable}>
        <div className={`${styles.driverRow} ${styles.driverHead}`}><div>Factor</div><div>{away.abbr}<small>Net this season</small></div><div>{home.abbr}<small>Net this season</small></div><div>Net difference<small>{away.abbr} − {home.abbr}</small></div><div>Model influence<small>0–{influenceMax}%</small></div><div>Model edge<small>Neutral field · equal rest</small></div></div>
        {entries.map(({ key, gap }) => <div className={styles.driverRow} key={key} role="group" aria-label={`${labels[key]} comparison`}>
          <div className={styles.driverLabel}>{labels[key]}<small>{FACTOR_UNITS[key] || 'Additional model context'}</small></div>
          {[away, home].map(team => <div className={styles.teamValues} key={team.id} aria-label={`${team.abbr} season values`}>
            <span className={styles.mobileTeam}>{team.abbr}</span>
            {FACTOR_UNITS[key] ? <div><strong>{formatNet(key, seasonNet(team, key))}</strong>{team.factors[key] && !team.factors[key].net.complete && <span> · partial</span>}</div> : <span className={styles.notAvailable}>—<small>Not supplied</small></span>}
          </div>)}
          <div className={styles.netDifference} aria-label="Net difference"><span className={styles.mobileNetLabel}>Net difference · {away.abbr} − {home.abbr}</span><strong>{formatNet(key, netDifference(key))}</strong></div>
          <div className={styles.influence}><strong>{p.weights[key].toFixed(1)}%</strong><span className={styles.influenceTrack} aria-hidden="true"><i style={{ width: `${p.weights[key] / influenceMax * 100}%` }} /></span><span className={styles.mobileInfluence}>Model influence</span></div>
          <div className={styles.edgeCell}>
            <div className={styles.gapValue}>{Math.abs(gap) < 0.005 ? 'Even' : `${gap > 0 ? away.abbr : home.abbr} +${Math.abs(gap).toFixed(2)}`}<span> pts</span></div>
            <div className={styles.gapPlot} role="img" aria-label={`${labels[key]}: ${edge(gap)} rating points`}><i className={styles.gapFill} style={{ left: `${gap < 0 ? 50 + gap / extent * 50 : 50}%`, width: `${Math.abs(gap) / extent * 50}%`, background: gap < 0 ? 'var(--data-home)' : 'var(--data-away)' }} /></div>
            <span className={styles.mobileEdgeLabel}>Neutral-field model edge</span>
          </div>
        </div>)}
      </div>
      <p className={styles.note}>Largest model edges first. All edge bars use the same scale: {extent} points either side of zero.</p>
      <div className={styles.bridge}>{[[edge(ratingGap), 'Neutral-field rating edge', 'Equal rest · all ten components'], [edge(context), 'Matchup context adjustment', 'Venue/designation and rest'], [edge(-p.model), 'Projected game margin', 'Components sum before rounding']].map(([value, title, detail]) => <div key={title}><b>{value}</b><span>{title}<br />{detail}</span></div>)}</div>
    </section>
    <details className={styles.details}><summary>Observed season statistics <span>All eight factors · raw team output</span></summary>
      <div className={styles.scroll}><table><thead><tr><th>Factor</th><th>{away.abbr}</th><th>{home.abbr}</th></tr></thead><tbody>{p.factors.map(f => <tr key={f.id}><th>{f.label}<small>{f.unit}</small></th>{[away, home].map(team => <td key={team.id}>{format(f.id, team.factors[f.id].own.value)} <small>{rank(team.factors[f.id].own)} · {team.factors[f.id].own.rankPool} qualified teams{!team.factors[f.id].own.complete ? ' · incomplete coverage' : ''}</small></td>)}</tr>)}</tbody></table></div>
      <p className={styles.note}>Own-team output only; opposing defense is shown above. Ties share ranks. Incomplete factors remain visible without a rank.</p>
    </details>
    <details id="pregame-model" className={styles.details} open={modelOpen} onToggle={event => setModelOpen(event.currentTarget.open)}><summary>Behind the model outlook</summary>
      <p>The frozen model combines opponent-adjusted performance, prior-season evidence, and quarterback usage history. Venue and rest adjust the matchup projection. QB history does not identify a confirmed starter. Team ratings measure points relative to league average, at equal rest with venue excluded.</p>
      <p>Projection published {new Date(p.publishedAt).toLocaleDateString('en-US', { timeZone: 'UTC', month: 'long', day: 'numeric', year: 'numeric' })}, using games through Week {p.throughWeek}. No win probability is inferred from the margin.</p>
    </details>
    <footer className={styles.footer}>Season data: nflverse · {p.season} through Week {p.throughWeek} · {away.abbr}: {away.gamesAvailable} games; {home.abbr}: {home.gamesAvailable} games · Full-game regular-season statistics. Live report: ESPN.</footer>
  </article>;
}
