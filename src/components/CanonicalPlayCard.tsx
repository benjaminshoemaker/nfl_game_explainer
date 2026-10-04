import type { CanonicalPlay, TeamMeta } from '@/types';
import styles from './GameExplorer.module.css';

const ordinal = (down: number) => `${down}${down === 1 ? 'st' : down === 2 ? 'nd' : down === 3 ? 'rd' : 'th'}`;
const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

function cleanDescription(value: string) {
  return (value || 'No play description available.')
    .replace(/([.!?])\s*(?=PENALTY\b)/gi, '$1 ')
    .replace(/\bWAS\b/g, 'WSH')
    .replace(/\b([A-Z])\.([A-Z][a-z])/g, '$1. $2')
    .replace(/\bpushed ob\b/gi, 'pushed out of bounds')
    .replace(/\bPENALTY\b/g, 'Penalty')
    .replace(/\bTOUCHDOWN\b/g, 'Touchdown')
    .replace(/\bINTERCEPTED\b/g, 'intercepted')
    .replace(/\s+/g, ' ').trim();
}

export function CanonicalPlayCard({ play, home, away }: { play: CanonicalPlay; home: TeamMeta; away: TeamMeta }) {
  const spot = play.ballBefore === '50' ? 'midfield' : play.ballBefore ? `the ${play.ballBefore}` : null;
  const down = play.down && play.down >= 1 && play.down <= 4
    ? `${ordinal(play.down)} and ${play.distance === 0 ? 'goal' : play.distance ?? '?'}` : null;
  const situation = [down, spot && `from ${spot}`].filter(Boolean).join(' ');
  const score = play.scoreBefore ? `${away.abbr} ${play.scoreBefore.away} · ${home.abbr} ${play.scoreBefore.home}` : 'Unavailable';
  const callouts: Array<{ label: string; value: string }> = [];
  if (play.penalty) {
    const p = play.penalty;
    const details = p.status === 'declined' ? 'declined' : p.note || (p.yards === null ? 'charged yards unresolved' : `${p.yards}-yard penalty`);
    const extra = /\bNo Play\b/i.test(play.text) ? '; no play' : /enforced between downs/i.test(play.text) ? '; enforced between downs' : '';
    callouts.push({ label: 'Penalty', value: `${p.type}${p.team ? ` on ${p.team}` : ''} — ${details}${extra}` });
  }
  if (play.scoreChange?.team) {
    callouts.push({
      label: play.scoreChange.non_offensive && /interception|fumble|safety/i.test(`${play.type} ${play.text}`) ? 'Defensive points' : 'Points scored',
      value: `${play.scoreChange.team} +${play.scoreChange.points}`,
    });
  }
  const delta = play.homeWpDelta;
  const benefited = delta === null ? null : delta >= 0 ? home : away;
  const magnitude = delta === null ? null : Math.abs(delta);
  const wp = magnitude === null ? 'Unavailable' : magnitude === 0 ? 'No measured change'
    : `${benefited?.abbr} +${magnitude < .001 ? '<0.1' : (magnitude * 100).toFixed(1)} pp`;
  const showRange = magnitude !== null && magnitude >= .1 && play.homeWpBefore !== null && play.homeWpAfter !== null;
  const wpBefore = play.homeWpBefore !== null ? (benefited?.id === home.id ? play.homeWpBefore : 1 - play.homeWpBefore) : null;
  const wpAfter = play.homeWpAfter !== null ? (benefited?.id === home.id ? play.homeWpAfter : 1 - play.homeWpAfter) : null;
  const epa = play.epa === null ? 'Unavailable' : `${play.sourceTeam || 'Play'} ${play.epa >= 0 ? '+' : '−'}${Math.abs(play.epa).toFixed(2)} points`;
  return <article className={styles.playCard} data-play-id={play.id}>
    <div className={styles.cardTop}>
      <span className={styles.teamChip} style={{ background: play.sourceTeam === home.abbr ? '#9d7424' : '#205273' }}>{play.sourceTeam || '—'}</span>
      <span className={styles.cardTime}>Q{play.quarter ?? '?'} · {play.clock || '—'}{situation ? ` · ${situation}` : ''}</span>
      <span className={styles.scoreLine}>Score <strong>{score}</strong></span>
    </div>
    <span className={styles.playType}>{play.type}</span>
    <p className={styles.description}>{cleanDescription(play.text)}</p>
    {callouts.length > 0 && <div className={styles.callouts}>{callouts.map((callout, i) =>
      <div className={styles.callout} key={`${callout.label}-${i}`}><span>{callout.label}</span><strong>{callout.value}</strong></div>
    )}</div>}
    <div className={styles.metrics}>
      <div className={styles.metric}><span>Play EPA</span><strong>{epa}</strong></div>
      <div className={styles.metric}><span>Win probability change</span><strong>{wp}</strong>
        {showRange && wpBefore !== null && wpAfter !== null && <small>{percent(wpBefore)} → {percent(wpAfter)}</small>}
        {play.wpAttributionUncertain && <small>ESPN updated win probability after the preceding score; this change may include that update.</small>}
      </div>
    </div>
  </article>;
}
