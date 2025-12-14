'use client';

import Link from 'next/link';
import Image from 'next/image';
import { ScoreboardGame } from '@/types';
import { getTeamColors, getTeamLogo } from '@/lib/teamColors';

interface GameCardProps {
  game: ScoreboardGame;
}

export function GameCard({ game }: GameCardProps) {
  const { homeTeam, awayTeam, status, statusDetail, gameId, isActive } = game;

  const homeColors = getTeamColors(homeTeam.abbr);
  const awayColors = getTeamColors(awayTeam.abbr);

  const isHomeWinning = homeTeam.score > awayTeam.score;
  const isAwayWinning = awayTeam.score > homeTeam.score;
  const isFinal = status === 'final';
  const isPregame = status === 'pregame';

  return (
    <Link href={`/game/${gameId}`} className="block group">
      <div
        className={`
          relative bg-bg-card rounded-xl border border-border-subtle overflow-hidden
          transition-all duration-300 hover:border-border-medium hover:shadow-lg
          ${isActive ? 'ring-2 ring-positive/30' : ''}
        `}
      >
        {/* Active game indicator */}
        {isActive && (
          <div className="absolute top-2 right-2">
            <span className="flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-positive opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-positive" />
            </span>
          </div>
        )}

        {/* Teams */}
        <div className="p-4">
          {/* Away team row */}
          <div className={`flex items-center gap-3 py-2 ${isAwayWinning && isFinal ? '' : isFinal ? 'opacity-60' : ''}`}>
            <div className="relative w-8 h-8 flex-shrink-0">
              <Image
                src={getTeamLogo(awayTeam.abbr)}
                alt={awayTeam.name}
                fill
                className="object-contain"
              />
            </div>
            <span
              className="font-condensed text-sm font-semibold uppercase tracking-wide flex-1"
              style={{ color: awayColors.primary }}
            >
              {awayTeam.abbr}
            </span>
            <span
              className={`font-display text-xl tracking-wide ${
                isAwayWinning && isFinal ? 'text-gold' : 'text-text-primary'
              }`}
            >
              {isPregame ? '-' : awayTeam.score}
            </span>
          </div>

          {/* Home team row */}
          <div className={`flex items-center gap-3 py-2 ${isHomeWinning && isFinal ? '' : isFinal ? 'opacity-60' : ''}`}>
            <div className="relative w-8 h-8 flex-shrink-0">
              <Image
                src={getTeamLogo(homeTeam.abbr)}
                alt={homeTeam.name}
                fill
                className="object-contain"
              />
            </div>
            <span
              className="font-condensed text-sm font-semibold uppercase tracking-wide flex-1"
              style={{ color: homeColors.primary }}
            >
              {homeTeam.abbr}
            </span>
            <span
              className={`font-display text-xl tracking-wide ${
                isHomeWinning && isFinal ? 'text-gold' : 'text-text-primary'
              }`}
            >
              {isPregame ? '-' : homeTeam.score}
            </span>
          </div>
        </div>

        {/* Status bar */}
        <div
          className={`
            px-4 py-2 border-t border-border-subtle
            ${isActive ? 'bg-positive/10' : 'bg-bg-elevated'}
          `}
        >
          <span
            className={`
              font-condensed text-xs uppercase tracking-wider
              ${isActive ? 'text-positive' : isFinal ? 'text-text-muted' : 'text-text-secondary'}
            `}
          >
            {statusDetail}
          </span>
        </div>

        {/* Hover gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-gold/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
      </div>
    </Link>
  );
}
