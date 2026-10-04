'use client';

import Link from 'next/link';
import Image from 'next/image';
import { ScoreboardGame, WeekSelection } from '@/types';
import { getTeamColorVars } from '@/lib/teamColors';
import styles from './GameCard.module.css';
import { gameStatusLabel } from '@/lib/gameStatus';

interface GameCardProps {
  game: ScoreboardGame;
  week?: WeekSelection | null;
}

function buildGameHref(gameId: string, week?: WeekSelection | null): string {
  if (!week || week.weekNumber <= 0) return `/game/${gameId}`;
  const params = new URLSearchParams();
  params.set('week', String(week.weekNumber));
  params.set('seasontype', String(week.seasonType));
  return `/game/${gameId}?${params.toString()}`;
}

export function GameCard({ game, week }: GameCardProps) {
  const { homeTeam, awayTeam, status, statusDetail, gameId, isActive } = game;
  const hasNoScore = status === 'pregame' || status === 'postponed' || status === 'canceled';
  const awayWinning = awayTeam.score > homeTeam.score && status === 'final';
  const homeWinning = homeTeam.score > awayTeam.score && status === 'final';
  const awayColors = getTeamColorVars(awayTeam.abbr);
  const homeColors = getTeamColorVars(homeTeam.abbr);

  return (
    <Link href={buildGameHref(gameId, week)} className={styles.game} aria-label={`${awayTeam.name} at ${homeTeam.name}, ${gameStatusLabel(status, statusDetail)}`}>
      <span className={`${styles.status} ${isActive ? styles.live : ''}`}>{isActive ? '● ' : ''}{gameStatusLabel(status, statusDetail)}</span>
      <span className={styles.teams}>
        <span className={styles.team}>
          <span className={styles.logo}><Image src={awayColors.logo} alt="" fill className="object-contain" /></span>
          <span><strong>{awayTeam.abbr}</strong><small>{awayTeam.name}</small></span>
        </span>
        <span className={styles.at}>at</span>
        <span className={styles.team}>
          <span className={styles.logo}><Image src={homeColors.logo} alt="" fill className="object-contain" /></span>
          <span><strong>{homeTeam.abbr}</strong><small>{homeTeam.name}</small></span>
        </span>
      </span>
      <span className={styles.score} aria-label={hasNoScore ? gameStatusLabel(status, statusDetail) : `${awayTeam.score} to ${homeTeam.score}`}>
        {hasNoScore ? <span className={styles.upcoming}>{status === 'pregame' ? 'Upcoming' : gameStatusLabel(status, statusDetail)}</span> : <><span className={awayWinning ? styles.winner : ''}>{awayTeam.score}</span><span className={styles.divider}>–</span><span className={homeWinning ? styles.winner : ''}>{homeTeam.score}</span></>}
      </span>
      <span className={styles.open}>Game report <span aria-hidden="true">→</span></span>
    </Link>
  );
}
