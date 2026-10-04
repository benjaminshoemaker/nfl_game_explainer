'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ScoreboardGame, WeekSelection } from '@/types';
import styles from './GameSidebar.module.css';
import { gameStatusLabel } from '@/lib/gameStatus';
import { sortScoreboardGames } from '@/lib/sortScoreboardGames';

interface GameSidebarProps {
  games: ScoreboardGame[];
  weekLabel: string;
  week?: WeekSelection | null;
  refreshFailed?: boolean;
  refreshStatus?: string;
}

function buildGameHref(gameId: string, week?: WeekSelection | null): string {
  if (!week || week.weekNumber <= 0) return `/game/${gameId}`;
  const params = new URLSearchParams();
  params.set('week', String(week.weekNumber));
  params.set('seasontype', String(week.seasonType));
  return `/game/${gameId}?${params.toString()}`;
}

function GameRow({ game, current, week }: { game: ScoreboardGame; current: boolean; week?: WeekSelection | null }) {
  const hasNoScore = game.status === 'pregame' || game.status === 'postponed' || game.status === 'canceled';
  const awayWinning = game.status === 'final' && game.awayTeam.score > game.homeTeam.score;
  const homeWinning = game.status === 'final' && game.homeTeam.score > game.awayTeam.score;
  return <Link href={buildGameHref(game.gameId, week)} aria-current={current ? 'page' : undefined} className={`${styles.row} ${current ? styles.current : ''}`}>
    <span className={styles.matchup}><strong>{game.awayTeam.abbr}</strong><span>at</span><strong>{game.homeTeam.abbr}</strong></span>
    {hasNoScore ? <span className={styles.rowStatus}>{gameStatusLabel(game.status)}</span> : <span className={styles.score}><b className={awayWinning ? styles.winner : ''}>{game.awayTeam.score}</b><span>–</span><b className={homeWinning ? styles.winner : ''}>{game.homeTeam.score}</b></span>}
    <span className={`${styles.detail} ${game.isActive ? styles.live : ''}`}>{game.isActive ? '● ' : ''}{game.status === 'pregame' ? game.statusDetail || 'Kickoff time unavailable' : gameStatusLabel(game.status, game.statusDetail)}</span>
  </Link>;
}

export function GameSidebar({ games, weekLabel, week, refreshFailed = false, refreshStatus }: GameSidebarProps) {
  const pathname = usePathname();
  const currentGameId = pathname?.split('/').pop();
  const sortedGames = sortScoreboardGames(games);
  const liveCount = games.filter(game => game.isActive).length;
  const delayedCount = games.filter(game => game.status === 'delayed').length;
  return <div className={styles.sidebar}>
    <div className={styles.header}><Link href="/" className={styles.brand}>GAME<span>/</span>EXPLAINED</Link><div className={styles.week}>NFL games · {weekLabel}</div></div>
    <nav className={styles.list} aria-label={`${weekLabel} games`}>{sortedGames.map(game => <GameRow key={game.gameId} game={game} current={game.gameId === currentGameId} week={week} />)}</nav>
    {refreshFailed && <div className={styles.loadError} role="status">Scores may be out of date.</div>}
    <div className={styles.footer}>{liveCount ? `${liveCount} live ${liveCount === 1 ? 'game' : 'games'}` : delayedCount ? `${delayedCount} delayed ${delayedCount === 1 ? 'game' : 'games'}` : 'No live games'}{refreshStatus && <span>{refreshStatus}</span>}<Link href="/">All games →</Link></div>
  </div>;
}
