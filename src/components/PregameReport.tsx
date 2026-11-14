'use client';

import { useState } from 'react';
import type { PregamePreview, PreviewMetric } from '@/types';
import styles from './PregameReport.module.css';

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
      <p className={styles.driverIntro}>{Math.abs(ratingGap) < 0.005 ? 'The teams have equal ratings.' : `${ratingGap > 0 ? away.name : home.name} lead by ${Math.abs(ratingGap).toFixed(1)} rating points.`}</p>
      <p className={styles.note}>Each bar shows the difference between adjusted rating contributions. Left favors {home.abbr}; right favors {away.abbr}. Largest differences first.</p>
      <div className={`${styles.driverRow} ${styles.driverHead}`}><div>Component · team contributions</div><div className={styles.axis}><span>← {home.abbr}<br />{extent} pts</span><span>0</span><span>{away.abbr} →<br />{extent} pts</span></div><div>Difference</div><div className={styles.influence}><div>Model influence<div className={styles.axis}><span>0%</span><span>{influenceMax}%</span></div></div></div></div>
      {entries.map(({ key, gap }) => <div className={styles.driverRow} key={key}>
        <div className={styles.driverLabel}>{labels[key]}<small>{away.abbr} {signed(ratings[p.away].contributions[key])} · {home.abbr} {signed(ratings[p.home].contributions[key])} pts</small></div>
        <div className={styles.gapPlot} role="img" aria-label={`${labels[key]}: ${edge(gap)} rating points`}><i className={styles.gapFill} style={{ left: `${gap < 0 ? 50 + gap / extent * 50 : 50}%`, width: `${Math.abs(gap) / extent * 50}%`, background: gap < 0 ? 'var(--data-home)' : 'var(--data-away)' }} /></div>
        <div className={styles.gapValue}>{Math.abs(gap).toFixed(2)}<small>{Math.abs(gap) < 0.005 ? 'Even' : `${gap > 0 ? away.abbr : home.abbr} edge`} · pts</small></div>
        <div className={styles.influence}><span className={styles.mobileInfluence}>Model influence</span><span className={styles.influenceTrack} aria-hidden="true"><i style={{ width: `${p.weights[key] / influenceMax * 100}%` }} /></span><strong>{p.weights[key].toFixed(1)}%</strong></div>
      </div>)}
      <p className={styles.note}><b>Model influence</b> is typical contribution size in training data, normalized to total 100% across all ten components. It is fixed across teams, not a percentage of predictive accuracy. Contributions include opponent adjustment and prior-season evidence.</p>
      <div className={styles.bridge}>{[[edge(ratingGap), 'Team rating difference', 'All ten components combined'], [edge(context), 'Matchup context adjustment', 'Venue/designation and rest'], [edge(-p.model), 'Projected game margin', 'Components sum before rounding']].map(([value, title, detail]) => <div key={title}><b>{value}</b><span>{title}<br />{detail}</span></div>)}</div>
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
