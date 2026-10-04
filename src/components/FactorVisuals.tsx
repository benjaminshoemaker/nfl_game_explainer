import type { PlayDetail, TeamMeta } from '@/types';
import styles from './GameExplorer.module.css';

type Details = Record<string, Record<string, PlayDetail[]>>;
function ordered(plays: PlayDetail[]) {
  return [...plays].sort((a, b) => (a.quarter || 0) - (b.quarter || 0)
    || Number((b.clock || '0:00').split(':')[0]) * 60 + Number((b.clock || '0:00').split(':')[1])
    - Number((a.clock || '0:00').split(':')[0]) * 60 - Number((a.clock || '0:00').split(':')[1]));
}
function ownYard(position: string | undefined, abbr: string) {
  const match = (position || '').match(/\b([A-Z]{2,4})\s+(\d{1,2})\b/);
  if (!match) return null;
  const yard = Number(match[2]);
  return match[1] === abbr ? yard : 100 - yard;
}
export function FactorVisuals({ factor, details, away, home }: { factor: string; details: Details; away: TeamMeta; home: TeamMeta }) {
  if (factor === 'Adjusted Yards Per Play') {
    const teams = [away, home].map(team => {
      const list = ordered(details[team.id]?.['Offensive Plays'] || []);
      let yards = 0;
      const points = [0, ...list.map(play => (yards += play.yards || 0))];
      return { team, list, points };
    });
    const maxPlay = Math.max(1, ...teams.map(t => t.list.length));
    const all = teams.flatMap(t => t.points);
    const minY = Math.min(0, ...all), maxY = Math.max(100, ...all);
    const x = (i: number) => 42 + (i / maxPlay) * 510;
    const y = (n: number) => 150 - ((n - minY) / Math.max(1, maxY - minY)) * 120;
    return <div className={styles.visual}><strong>Yards after each offensive play</strong><small>Same play count and yardage scale for both teams.</small>
      <svg className={styles.lineChart} viewBox="0 0 590 180" role="img" aria-label={`Cumulative offensive yards: ${teams.map(t => `${t.team.abbr} ${t.points.at(-1)} yards in ${t.list.length} plays`).join('; ')}`}>
        {[0, .25, .5, .75, 1].map(tick => <line key={tick} x1="42" x2="552" y1={150 - tick * 120} y2={150 - tick * 120} stroke="#dce2db" />)}
        {teams.map((t, index) => <path key={t.team.id} d={t.points.map((yards, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(yards).toFixed(1)}`).join(' ')} fill="none" stroke={index ? '#9d7424' : '#205273'} strokeWidth="3" />)}
        <text x="45" y="175" fontSize="11" fill="#677570">0 plays</text><text x="552" y="175" textAnchor="end" fontSize="11" fill="#677570">{maxPlay} plays</text>
      </svg><div className={styles.chartLegend}>{teams.map((t, index) => <span key={t.team.id} style={{ color: index ? '#9d7424' : '#205273' }}>{t.team.abbr} · {t.points.at(-1)} yd / {t.list.length} plays</span>)}</div>
    </div>;
  }
  if (factor === 'Explosive Play Rate') {
    return <div className={styles.visual}><strong>When the big gains came</strong><small>Run 10+ yd · pass 20+ yd</small>
      {[1, 2, 3, 4].map(quarter => <div className={styles.quarterLane} key={quarter}><b>Q{quarter}</b>{[away, home].map(team => {
        const list = (details[team.id]?.['Explosive Plays'] || []).filter(play => play.quarter === quarter);
        return <div key={team.id}><span>{team.abbr}</span>{list.length ? list.map((play, i) => <small key={i}>{play.type} {play.yards} yd · {play.clock}</small>) : <em>None</em>}</div>;
      })}</div>)}
    </div>;
  }
  if (factor === 'Ave Start Field Pos') {
    return <div className={styles.visual}><strong>All drive starts on one field</strong><small>Teams face each other; position is normalized from each offense’s goal line.</small>
      <div className={styles.field}><div className={styles.fieldMid} />{[away, home].flatMap((team, teamIndex) => (details[team.id]?.['Drive Starts'] || []).map((event, i) => {
        const own = ownYard(event.start_pos || event.end_pos, team.abbr);
        if (own === null) return null;
        return <i key={`${team.id}-${i}`} title={`${team.abbr} drive ${i + 1}: ${event.start_pos || event.end_pos}`} style={{ left: `${teamIndex ? 100 - own : own}%`, top: `${teamIndex ? 65 : 24}%`, background: teamIndex ? '#9d7424' : '#205273' }} />;
      }))}</div><div className={styles.fieldAxis}><span>{away.abbr} end zone</span><span>50</span><span>{home.abbr} end zone</span></div>
    </div>;
  }
  return null;
}
