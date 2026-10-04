'use client';

import { useEffect, useMemo, useState } from 'react';
import type { AdvancedStats, CanonicalPlay, GameResponse, PlayDetail, TeamMeta } from '@/types';
import { CanonicalPlayCard } from './CanonicalPlayCard';
import { FactorVisuals } from './FactorVisuals';
import styles from './GameExplorer.module.css';
import { gameStatusLabel } from '@/lib/gameStatus';

type Factor = { id: string; label: string; sub: string; details: string; tabs: Array<[string, string]>; eventKey: string };
const FACTORS: Factor[] = [
  { id: 'Turnovers', label: 'Turnovers', sub: 'Possession changes', details: 'Each giveaway and the resulting change of possession.', tabs: [], eventKey: 'Turnovers' },
  { id: 'Success Rate', label: 'Success rate', sub: 'Consistent offense', details: 'Successful plays divided by eligible offensive plays. The target changes by down and distance.', tabs: [['type', 'Run / pass'], ['down', 'By down'], ['quarter', 'By quarter']], eventKey: 'Offensive Plays' },
  { id: 'Adjusted Yards Per Play', label: 'Adjusted yards / play', sub: 'Offensive efficiency', details: 'Adjusted offensive yards per eligible play. Scrambles and sacks count as pass dropbacks.', tabs: [['type', 'Run / pass'], ['down', 'By down'], ['quarter', 'By quarter']], eventKey: 'Offensive Plays' },
  { id: 'Explosive Play Rate', label: 'Explosive-play rate', sub: '10+ run · 20+ pass', details: 'Runs of at least 10 yards or passes of at least 20, divided by eligible offensive plays.', tabs: [['type', 'Run / pass'], ['quarter', 'By quarter']], eventKey: 'Explosive Plays' },
  { id: 'Points Per Trip (Inside 40)', label: 'Points per trip', sub: 'Inside opponent 40', details: 'Points scored on each drive that reached the opponent’s 40-yard line.', tabs: [['outcome', 'Drive result'], ['quarter', 'By quarter']], eventKey: 'Points Per Trip (Inside 40)' },
  { id: 'Ave Start Field Pos', label: 'Starting field position', sub: 'Where drives began', details: 'Drive starts, measured from the offense’s goal line.', tabs: [['source', 'By source'], ['quarter', 'By quarter']], eventKey: 'Drive Starts' },
  { id: 'Penalty Yards', label: 'Penalty yards', sub: 'Assessed yards', details: 'Accepted penalty yards charged to each team; unavailable yardage stays unresolved.', tabs: [['type', 'By type'], ['quarter', 'By quarter']], eventKey: 'Penalty Yards' },
  { id: 'Non-Offensive Points', label: 'Non-offensive points', sub: 'Defense / special teams', details: 'Defensive and special teams scoring plays.', tabs: [], eventKey: 'Non-Offensive Points' },
];
type Event = PlayDetail & { teamId: string; team: string; down?: number | null };
const format = (factor: string, value: number | string | null | undefined) => {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') return value;
  if (factor === 'Success Rate' || factor === 'Explosive Play Rate') return `${(value * 100).toFixed(1)}%`;
  if (factor === 'Adjusted Yards Per Play' || factor === 'Points Per Trip (Inside 40)') return value.toFixed(2);
  return String(value);
};
const playTime = (p: { quarter?: number | null; clock?: string | null }) => (p.quarter || 0) * 10000 - Number((p.clock || '0:00').split(':')[0]) * 60 - Number((p.clock || '0:00').split(':')[1]);
const eventGroup = (event: Event, split: string) => {
  if (split === 'quarter') return `Q${event.quarter || '?'}`;
  if (split === 'type') return event.penalty_type || event.type || 'Other';
  if (split === 'down') {
    const down = event.down;
    return down && down >= 1 && down <= 4 ? `${down}${down === 1 ? 'st' : down === 2 ? 'nd' : down === 3 ? 'rd' : 'th'} down` : 'Other';
  }
  if (split === 'outcome') return (event.points || 0) >= 6 ? 'Touchdown' : event.points === 3 ? 'Field goal' : 'No points';
  if (split === 'source') {
    const text = `${event.type} ${event.text}`.toLowerCase();
    if (text.includes('kickoff')) return 'Kickoff';
    if (text.includes('punt')) return 'Punt';
    if (text.includes('intercept') || text.includes('fumble')) return 'Takeaway';
    if (text.includes('downs')) return 'Turnover on downs';
    return 'Other';
  }
  return 'All';
};
function statFor(rows: AdvancedStats[], abbr: string, id: string) {
  return rows.find(row => row.Team === abbr)?.[id as keyof AdvancedStats] as number | string | null | undefined;
}
function scoreFor(game: GameResponse, team: TeamMeta) {
  return game.summary_table_full.find(row => row.Team === team.abbr)?.Score ?? 0;
}
function playTypeGroup(play: CanonicalPlay) {
  const type = play.type.toLowerCase();
  if (type.includes('fumble')) return /\bpass\b|\bsacked\b/i.test(play.text) ? 'pass' : 'rush';
  if (/pass|interception|sack/.test(type)) return 'pass';
  if (/rush|run/.test(type)) return 'rush';
  if (/kickoff|punt|field goal|extra point/.test(type)) return 'kick';
  if (play.penalty || type.includes('penalty')) return 'penalty';
  return 'other';
}
function isRankablePlay(play: CanonicalPlay) {
  return !/timeout|end of|warning|coin toss/i.test(play.type)
    && !/\bNo Play\b/i.test(play.text);
}
function ownYard(event: Event) {
  const position = event.start_pos || event.end_pos || '';
  const relative = position.match(/^(Own|Opp)\s+(\d{1,2})$/i);
  if (relative) return relative[1].toLowerCase() === 'own' ? Number(relative[2]) : 100 - Number(relative[2]);
  const absolute = position.match(/\b([A-Z]{2,4})\s+(\d{1,2})\b/);
  if (!absolute) return null;
  return absolute[1] === event.team ? Number(absolute[2]) : 100 - Number(absolute[2]);
}
function fieldPosition(yards: number) {
  const spot = Math.floor(yards);
  return spot > 50 ? `Opp ${100 - spot}` : `Own ${spot}`;
}
function eventNote(event: Event, factor: string) {
  if (factor === 'Points Per Trip (Inside 40)') return `Trip result · ${event.team} · ${event.points ?? '?'} points`;
  if (factor === 'Ave Start Field Pos') return `Drive start · ${event.team} at ${event.start_pos || event.end_pos || 'unknown spot'}`;
  if (factor === 'Success Rate') return `${event.success ? 'Successful' : 'Unsuccessful'} play · ${event.yards ?? '?'} yd credited`;
  if (factor === 'Adjusted Yards Per Play') return `${event.yards ?? '?'} offensive yards credited`;
  if (factor === 'Penalty Yards') return `Penalty charged to ${event.team}`;
  if (factor === 'Turnovers') return `${event.team} turnover${event.end_pos ? ` · opponent took over at ${event.end_pos}` : ''}`;
  if (factor === 'Non-Offensive Points') return `${event.team} non-offensive score`;
  return `${event.team} explosive play`;
}

export function GameExplorer({ game, scope, home, away }: { game: GameResponse; scope: 'competitive' | 'full'; home: TeamMeta; away: TeamMeta }) {
  const [selected, setSelected] = useState('Success Rate');
  const [split, setSplit] = useState('type');
  const [showEvents, setShowEvents] = useState(false);
  const [eventFilter, setEventFilter] = useState<string | null>(null);
  const [eventLimit, setEventLimit] = useState(8);
  const [quarterFilter, setQuarterFilter] = useState('all');
  const [teamFilter, setTeamFilter] = useState('all');
  const [benefitFilter, setBenefitFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [outcomeFilter, setOutcomeFilter] = useState('all');
  const [playSort, setPlaySort] = useState('game');
  const [playLimit, setPlayLimit] = useState(20);
  const [focusedPlay, setFocusedPlay] = useState<string | null>(null);
  useEffect(() => {
    if (focusedPlay) document.getElementById(`play-${focusedPlay}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [focusedPlay, playLimit, quarterFilter, teamFilter, benefitFilter, typeFilter, outcomeFilter, playSort]);
  const rows = scope === 'competitive' ? game.advanced_table : game.advanced_table_full;
  const details = scope === 'competitive' ? game.expanded_details : game.expanded_details_full;
  const factorValue = (factorId: string, team: TeamMeta) => {
    const teamDetails = details[team.id];
    const sample = factorId === 'Success Rate' || factorId === 'Adjusted Yards Per Play' || factorId === 'Explosive Play Rate'
      ? teamDetails?.['Offensive Plays']
      : factorId === 'Points Per Trip (Inside 40)' ? teamDetails?.['Points Per Trip (Inside 40)']
        : factorId === 'Ave Start Field Pos' ? teamDetails?.['Drive Starts'] : null;
    if (sample !== null && (!sample || sample.length === 0)) return '—';
    return format(factorId, statFor(rows, team.abbr, factorId));
  };
  const factor = FACTORS.find(item => item.id === selected) || FACTORS[0];
  const plays = useMemo(() => game.plays || [], [game.plays]);
  const byId = useMemo(() => new Map(plays.map(play => [play.id, play])), [plays]);
  const events = useMemo(() => [away, home].flatMap(team => (details[team.id]?.[factor.eventKey] || []).map(event => ({
    ...event, teamId: team.id, team: team.abbr,
    down: event.source_play_id ? byId.get(event.source_play_id)?.down : null,
    penalty_type: event.penalty_type || (event.source_play_id ? byId.get(event.source_play_id)?.penalty?.type : null),
  }))).sort((a, b) => playTime(a) - playTime(b)), [away, home, details, factor.eventKey, byId]);
  const eligible = [away, home].flatMap(team => (details[team.id]?.['Offensive Plays'] || []).map(event => ({
    ...event, teamId: team.id, team: team.abbr,
    down: event.source_play_id ? byId.get(event.source_play_id)?.down : null,
  })));
  const presentGroups = [...new Set(events.map(event => eventGroup(event, split)))];
  const groups = split === 'type' && factor.id !== 'Penalty Yards'
    ? ['Run', 'Pass'] : split === 'down' ? ['1st down', '2nd down', '3rd down', '4th down']
      : split === 'quarter' ? ['Q1', 'Q2', 'Q3', 'Q4', ...presentGroups.filter(value => !['Q1', 'Q2', 'Q3', 'Q4'].includes(value))]
        : split === 'outcome' ? ['Touchdown', 'Field goal', 'No points'] : presentGroups;
  const visibleEvents = eventFilter ? events.filter(event => eventGroup(event, split) === eventFilter) : events;
  const rankableCount = plays.filter(isRankablePlay).length;
  const impact = plays.filter(p => isRankablePlay(p) && !p.wpAttributionUncertain && p.homeWpDelta !== null && Math.abs(p.homeWpDelta) >= .05)
    .sort((a, b) => Math.abs(b.homeWpDelta!) - Math.abs(a.homeWpDelta!));
  const impactReady = rankableCount >= 20 && impact.length >= 3;
  const filteredPlays = plays.filter(play => (quarterFilter === 'all' || String(play.quarter) === quarterFilter)
    && (teamFilter === 'all' || play.sourceTeam === teamFilter)
    && (benefitFilter === 'all' || (play.homeWpDelta !== null && (benefitFilter === 'none' ? play.homeWpDelta === 0 : benefitFilter === home.abbr ? play.homeWpDelta > 0 : play.homeWpDelta < 0)))
    && (typeFilter === 'all' || playTypeGroup(play) === typeFilter)
    && (outcomeFilter === 'all' || (outcomeFilter === 'score' ? !!play.scoreChange : outcomeFilter === 'penalty' ? !!play.penalty : outcomeFilter === 'turnover' ? /interception|fumble recovery \(opponent\)/i.test(play.type) : play.down === 4 && !/timeout|end of|warning/i.test(play.type))));
  if (playSort === 'wp') filteredPlays.sort((a, b) => (b.homeWpDelta === null ? -1 : Math.abs(b.homeWpDelta)) - (a.homeWpDelta === null ? -1 : Math.abs(a.homeWpDelta)));
  else if (playSort === 'game' && game.status === 'in-progress') filteredPlays.reverse();
  const homeScore = scoreFor(game, home), awayScore = scoreFor(game, away);
  const winner = homeScore === awayScore ? null : homeScore > awayScore ? home : away;
  const title = game.status === 'final'
    ? winner ? `${winner.name} won ${Math.max(homeScore, awayScore)}–${Math.min(homeScore, awayScore)}` : `${away.name} and ${home.name} tied ${homeScore}–${awayScore}`
    : `${away.name} at ${home.name}`;
  const reasons = [
    { id: 'Turnovers', summary: 'takeaways', note: 'Inspect each change of possession.' },
    { id: 'Success Rate', summary: 'pp success rate', note: 'Compare consistent offense by play type and down.' },
    { id: 'Non-Offensive Points', summary: 'non-offensive points', note: 'See scores from defense and special teams.' },
  ].map(item => {
    const awayValue = statFor(rows, away.abbr, item.id);
    const homeValue = statFor(rows, home.abbr, item.id);
    if (typeof awayValue !== 'number' || typeof homeValue !== 'number' || awayValue === homeValue) return null;
    const lower = item.id === 'Turnovers';
    const leader = (awayValue > homeValue) !== lower ? away : home;
    const difference = Math.abs(awayValue - homeValue);
    const amount = item.id === 'Success Rate' ? (difference * 100).toFixed(1) : difference.toFixed(0);
    return { ...item, leader, amount };
  }).filter((item): item is NonNullable<typeof item> => item !== null);
  const selectFactor = (next: Factor) => { setSelected(next.id); setSplit(next.tabs[0]?.[0] || ''); setShowEvents(next.tabs.length === 0); setEventFilter(null); setEventLimit(8); };
  const renderEvent = (event: Event, index: number) => {
    const source = event.source_play_id ? byId.get(event.source_play_id) : null;
    return <div className={styles.eventEntry} key={`${event.teamId}-${event.source_play_id || event.text}-${index}`}>
      <div className={styles.entryContext}>{eventNote(event, factor.id)}</div>
      {source ? <CanonicalPlayCard play={source} home={home} away={away} /> : <div className={styles.missing}>Source play unavailable for this event.</div>}
    </div>;
  };
  if (plays.length === 0) {
    const noPlayHeading = game.status === 'pregame' ? 'Upcoming game' : game.status === 'postponed' ? 'Game postponed'
      : game.status === 'canceled' ? 'Game canceled' : game.status === 'delayed' ? 'Game delayed'
        : game.status === 'final' ? 'Play-by-play unavailable' : 'Waiting for the first play';
    const noPlayMessage = game.status === 'pregame' ? 'Analysis and play-by-play will appear when ESPN begins reporting this game. This page checks for updates every minute.'
      : game.status === 'postponed' ? 'ESPN reports that this game has been postponed. The page will check for a new status every minute.'
        : game.status === 'canceled' ? 'ESPN reports that this game has been canceled. There is no game report to show.'
          : game.status === 'delayed' ? 'ESPN reports a delay. No plays are available yet; this page will keep checking for updates.'
            : game.status === 'final' ? 'ESPN reports a final score, but play-by-play is unavailable. Factor comparisons cannot be shown.'
              : 'ESPN marks the game as live, but no plays are available yet. This page will keep checking for updates.';
    return <div className={styles.explorer}>
    <div className={styles.wrap}>
      <header className={styles.brandRow}><strong>GAME<span>/</span>EXPLAINED</strong><span>NFL · Week {game.week?.number || '—'} · {gameStatusLabel(game.status, game.statusDetail)}</span></header>
      <section className={styles.pregame}>
        <div className={styles.eyebrow}>{noPlayHeading}</div>
        <h1>{away.name} at {home.name}</h1>
        <p>{noPlayMessage}</p>
        {game.source_gaps?.length ? <p role="status">ESPN box-score totals or offensive-play counts differ from available play-by-play for {game.source_gaps.map(g => g.team).join(', ')}. Full-game totals use ESPN; play-based metrics and competitive splits may be incomplete.</p> : null}
        <div className={styles.pregameTeams}><span>{away.abbr}</span><span>at</span><span>{home.abbr}</span></div>
        {(game.status === 'in-progress' || game.status === 'delayed' || game.status === 'final') && <p className={styles.noPlayScore}>Score {away.abbr} {awayScore} · {home.abbr} {homeScore}</p>}
      </section>
      <footer className={styles.footer}>Game {game.gameId} · Game data from ESPN.</footer>
    </div>
  </div>;
  }
  return <div className={styles.explorer}>
    <div className={styles.wrap}>
      <header className={styles.brandRow}><strong>GAME<span>/</span>EXPLAINED</strong><span>NFL · Week {game.week?.number || '—'} · {gameStatusLabel(game.status, game.statusDetail || game.gameClock?.displayValue)}</span></header>
      <section className={styles.gameHead}>
        <div><div className={styles.eyebrow}>Game story</div><h1>{title}</h1>
          {game.status !== 'pregame' && <p>{game.status === 'delayed' || game.status === 'postponed' || game.status === 'canceled'
            ? 'Play is paused or stopped. The report below reflects the last plays ESPN provided.'
            : rankableCount < 20 && game.status !== 'final' ? 'The game is underway. Factor comparisons will become more useful as plays accumulate.'
              : (game.status === 'final' ? game.ai_summary || game.analysis : game.analysis || game.ai_summary) || 'Explore the game factors and their contributing plays below.'}</p>}
        </div>
        <div className={styles.scoreBox}><small>{game.status === 'final' ? 'Final score' : 'Current score'}</small><div><span>{away.abbr}</span><strong className={winner?.id === away.id ? styles.winningScore : ''}>{awayScore}</strong></div><div><span>{home.abbr}</span><strong className={winner?.id === home.id ? styles.winningScore : ''}>{homeScore}</strong></div></div>
      </section>
      {rankableCount >= 20 && game.status !== 'pregame' && reasons.length > 0 && <section className={styles.reasons} aria-label="Game story factors">
        {reasons.map(reason => <button key={reason.id} className={styles.reason} onClick={() => { const target = FACTORS.find(item => item.id === reason.id); if (target) selectFactor(target); document.getElementById('game-factors')?.scrollIntoView({ behavior: 'smooth' }); }}>
          <span className={styles.eyebrow}>{reason.id}</span><strong>{reason.leader.abbr} +{reason.amount} {reason.summary}</strong><small>{reason.note}</small>
        </button>)}
      </section>}
      {game.source_gaps?.length ? <div role="status" className={styles.notice}>ESPN box-score totals or offensive-play counts differ from available play-by-play for {game.source_gaps.map(g => g.team).join(', ')}. Full-game totals use ESPN; play-based metrics and competitive splits may be incomplete.</div> : null}
      {game.status === 'delayed' || game.status === 'postponed' || game.status === 'canceled' ? <div role="status" className={styles.notice}>{gameStatusLabel(game.status, game.statusDetail)}. This report shows the last plays ESPN provided.</div> : null}
      {rankableCount < 20 && game.status === 'in-progress' && <div role="status" className={styles.notice}>Early game: {rankableCount} classified {rankableCount === 1 ? 'play' : 'plays'} available. Factor comparisons are preliminary.</div>}
      <div className={styles.sectionHead}><div><div className={styles.eyebrow}>What shaped the game</div><h2>Explore all eight factors</h2></div><p>Choose a factor to inspect its split and contributing plays.</p></div>
      <section className={styles.workspace} id="game-factors" aria-label="Game factors and evidence">
        <div className={styles.rail} role="tablist" aria-label="Game factors"><div className={styles.railHeader}><strong>Game factors</strong><small>{away.abbr} · {home.abbr}</small></div>
          {FACTORS.map((item, index) => <button className={styles.category} key={item.id} role="tab" aria-selected={item.id === selected} onClick={() => selectFactor(item)}>
            <span className={styles.index}>{String(index + 1).padStart(2, '0')}</span><span><strong>{item.label}</strong><small>{item.sub}</small></span>
            <span className={styles.factorNumbers}><b>{factorValue(item.id, away)}</b> · <em>{factorValue(item.id, home)}</em></span>
          </button>)}
        </div>
        <article className={styles.detail} aria-label={`${factor.label} details`}>
          <div className={styles.detailTop}><div><div className={styles.eyebrow}>Category {String(FACTORS.indexOf(factor) + 1).padStart(2, '0')} of 08</div><h3>{factor.label}</h3><p>{factor.details}</p></div>
            <div className={styles.pills}><span>{away.abbr} {factorValue(factor.id, away)}</span><span>{home.abbr} {factorValue(factor.id, home)}</span></div></div>
          {factor.id === 'Success Rate' && <div className={styles.visual}><strong>Were they staying on schedule?</strong><small>Each mark represents one eligible offensive play.</small>
            {[away, home].map(team => { const list = (details[team.id]?.['Offensive Plays'] || []); return <div className={styles.markRow} key={team.id}><b>{team.abbr}</b><div>{list.map((e, i) => <i key={i} className={e.success ? styles.hit : ''} title={`Q${e.quarter} ${e.clock}: ${e.success ? 'successful' : 'unsuccessful'}`} />)}</div><small>{list.filter(e => e.success).length}/{list.length}</small></div>; })}</div>}
          {factor.id === 'Points Per Trip (Inside 40)' && <div className={styles.visual}><strong>Points on each trip</strong>{[away, home].map(team => <div className={styles.tripRow} key={team.id}><b>{team.abbr}</b>{(details[team.id]?.['Points Per Trip (Inside 40)'] || []).map((e, i) => <span key={i} title={`Trip ${i + 1}: ${e.points ?? '?'} points`}>{e.points ?? '?'}</span>)}</div>)}</div>}
          <FactorVisuals factor={factor.id} details={details} away={away} home={home} />
          <div className={styles.detailBody}>
            {factor.tabs.length > 0 && <div className={styles.controls}><div className={styles.tabs}>{factor.tabs.map(([id, label]) => <button key={id} aria-pressed={split === id && !showEvents} onClick={() => { setSplit(id); setShowEvents(false); setEventFilter(null); }}>{label}</button>)}</div><button className={styles.textButton} onClick={() => { setShowEvents(!showEvents); setEventFilter(null); }}>{showEvents ? '← Back to splits' : `See all contributing ${factor.id === 'Points Per Trip (Inside 40)' || factor.id === 'Ave Start Field Pos' ? 'drives' : 'plays'}`}</button></div>}
            {!showEvents && factor.tabs.length ? <><div className={styles.splitHead}><span>Split</span><span>{away.abbr}</span><span>{home.abbr}</span></div>{groups.map(group => { const a = events.filter(e => e.teamId === away.id && eventGroup(e, split) === group); const h = events.filter(e => e.teamId === home.id && eventGroup(e, split) === group); const display = (list: Event[], teamId: string) => {
                if (factor.id === 'Success Rate') return `${list.filter(e => e.success).length}/${list.length}`;
                if (factor.id === 'Adjusted Yards Per Play') return list.length ? `${(list.reduce((n, e) => n + (e.yards || 0), 0) / list.length).toFixed(2)} yd/play` : '—';
                if (factor.id === 'Explosive Play Rate') {
                  const denominator = eligible.filter(e => e.teamId === teamId && eventGroup(e, split) === group).length;
                  return denominator ? `${list.length}/${denominator} · ${(100 * list.length / denominator).toFixed(1)}%` : '—';
                }
                if (factor.id === 'Points Per Trip (Inside 40)') return `${list.length} trips · ${list.reduce((n, e) => n + (e.points || 0), 0)} pts`;
                if (factor.id === 'Ave Start Field Pos') {
                  const positions = list.map(ownYard).filter((value): value is number => value !== null);
                  return positions.length ? `${fieldPosition(positions.reduce((n, value) => n + value, 0) / positions.length)} · ${positions.length} starts` : '—';
                }
                if (factor.id === 'Penalty Yards') return list.some(e => e.yards === null) ? 'Unresolved' : `${list.reduce((n, e) => n + Math.abs(e.yards || 0), 0)} yd`;
                return `${list.length} plays`;
              }; return <button key={group} className={styles.splitRow} onClick={() => { setEventFilter(group); setShowEvents(true); }}><span>{group}</span><strong>{display(a, away.id)}</strong><strong>{display(h, home.id)}</strong></button>; })}
              <p className={styles.help}>Select a split to see its contributing plays.</p></> : <><div className={styles.listHeading}><strong>{eventFilter ? `${eventFilter} · ` : ''}{visibleEvents.length} contributing {factor.id === 'Ave Start Field Pos' || factor.id === 'Points Per Trip (Inside 40)' ? 'drives' : 'events'}</strong><span>Chronological</span></div>
              {visibleEvents.length ? visibleEvents.slice(0, eventLimit).map(renderEvent) : <div className={styles.missing}>No contributing events in this selection.</div>}
              {visibleEvents.length > eventLimit && <button className={styles.more} onClick={() => setEventLimit(eventLimit + 8)}>Show more · {visibleEvents.length - eventLimit} remaining</button>}</>}
          </div>
        </article>
      </section>
      <div className={styles.sectionHead}><div><div className={styles.eyebrow}>The game as it unfolded</div><h2>Explore the plays</h2></div><p>ESPN play-by-play, including kicks, penalties, and timeouts.</p></div>
      <section className={styles.tapeGrid} aria-label="Game play browser">
        <article className={styles.panel}><div className={styles.panelHead}><h3>Most impactful plays</h3><p>Ranked by absolute win probability change.</p></div>
          {impactReady ? impact.slice(0, 5).map((play, index) => <div className={styles.eventEntry} key={play.id}><div className={styles.entryContext}><span>{String(index + 1).padStart(2, '0')} · Most impactful</span><button onClick={() => { setQuarterFilter('all'); setTeamFilter('all'); setBenefitFilter('all'); setTypeFilter('all'); setOutcomeFilter('all'); setPlaySort('game'); const playIndex = plays.findIndex(item => item.id === play.id); setPlayLimit(Math.max(20, game.status === 'in-progress' ? plays.length - playIndex : playIndex + 1)); setFocusedPlay(play.id); }}>Show in all plays ↗</button></div><CanonicalPlayCard play={play} home={home} away={away} /></div>) : <div className={styles.missing}>This view appears after at least 20 plays and three measured swings of 5 pp or more. {rankableCount} classified plays are available.</div>}
        </article>
        <article className={styles.panel}><div className={styles.panelHead}><h3>All plays <span>{plays.length}</span></h3><p>Available play-by-play from ESPN.</p></div>
          <div className={styles.filters}><label>Quarter<select value={quarterFilter} onChange={e => { setQuarterFilter(e.target.value); setPlayLimit(20); }}><option value="all">All</option>{[1,2,3,4,5].map(q => <option key={q} value={q}>{q === 5 ? 'OT' : `Q${q}`}</option>)}</select></label>
            <label>Listed team<select value={teamFilter} onChange={e => { setTeamFilter(e.target.value); setPlayLimit(20); }}><option value="all">Both teams</option><option>{away.abbr}</option><option>{home.abbr}</option></select></label>
            <label>Benefited<select value={benefitFilter} onChange={e => { setBenefitFilter(e.target.value); setPlayLimit(20); }}><option value="all">Either team</option><option value={away.abbr}>{away.abbr} gained WP</option><option value={home.abbr}>{home.abbr} gained WP</option><option value="none">Neither gained</option></select></label>
            <label>Play type<select value={typeFilter} onChange={e => { setTypeFilter(e.target.value); setPlayLimit(20); }}><option value="all">All types</option><option value="pass">Pass / sack</option><option value="rush">Rush</option><option value="kick">Kick / punt</option><option value="penalty">Penalty play</option><option value="other">Other</option></select></label>
            <label>Outcome<select value={outcomeFilter} onChange={e => { setOutcomeFilter(e.target.value); setPlayLimit(20); }}><option value="all">All outcomes</option><option value="score">Scoring</option><option value="turnover">Turnover</option><option value="penalty">Penalty involved</option><option value="fourth">Fourth down</option></select></label>
            <label>Sort<select value={playSort} onChange={e => { setPlaySort(e.target.value); setPlayLimit(20); }}><option value="game">{game.status === 'in-progress' ? 'Newest first' : 'Game order'}</option>{game.status === 'in-progress' && <option value="oldest">Oldest first</option>}<option value="wp">Biggest WP swing</option></select></label></div>
          <div className={styles.tapeList}>{filteredPlays.slice(0, playLimit).map((play: CanonicalPlay) => <div className={`${styles.tapeEntry} ${focusedPlay === play.id ? styles.focus : ''}`} id={`play-${play.id}`} key={play.id}><CanonicalPlayCard play={play} home={home} away={away} /></div>)}
            {!filteredPlays.length && <div className={styles.missing}>No plays match these filters.</div>}
            {filteredPlays.length > playLimit && <button className={styles.more} onClick={() => setPlayLimit(playLimit + 20)}>Show 20 more · {filteredPlays.length - playLimit} remaining</button>}</div>
          <div className={styles.panelFoot}>Showing {Math.min(filteredPlays.length, playLimit)} of {filteredPlays.length} matching plays · pp = percentage points. The latest play’s EPA may wait for the next play state.</div>
        </article>
      </section>
      <footer className={styles.footer}>Game {game.gameId} · Statistics and win probability from ESPN. EPA is shown only when a verified play estimate is available.</footer>
    </div>
  </div>;
}
