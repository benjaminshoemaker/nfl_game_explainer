'use client';

import Link from 'next/link';
import Image from 'next/image';
import { ScoreboardGame } from '@/types';
import { getTeamColorVars } from '@/lib/teamColors';

interface GameCardProps {
  game: ScoreboardGame;
}

export function GameCard({ game }: GameCardProps) {
  const { homeTeam, awayTeam, status, statusDetail, gameId, isActive } = game;

  const homeColors = getTeamColorVars(homeTeam.abbr);
  const awayColors = getTeamColorVars(awayTeam.abbr);

  const isHomeWinning = homeTeam.score > awayTeam.score;
  const isAwayWinning = awayTeam.score > homeTeam.score;
  const isFinal = status === 'final';
  const isPregame = status === 'pregame';

  return (
    <Link href={`/game/${gameId}`} className="block group">
      <div
        className={`
          relative bg-bg-card rounded-xl border border-border-subtle overflow-hidden
          transition-all duration-300 hover:border-border-medium hover:shadow-lg hover:-translate-y-1
          ${isActive ? 'ring-2 ring-positive/30' : ''}
        `}
      >
        {/* Team color diagonal background */}
        <div className="absolute inset-0 opacity-10 pointer-events-none">
          <div
            className="absolute inset-0"
            style={{
              background: `linear-gradient(135deg, ${awayColors.primary} 0%, ${awayColors.primary} 50%, ${homeColors.primary} 50%, ${homeColors.primary} 100%)`,
            }}
          />
        </div>

        {/* Active game indicator */}
        {isActive && (
          <div className="absolute top-2 right-2 z-10">
            <span className="flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-positive opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-positive" />
            </span>
          </div>
        )}

        {/* Teams */}
        <div className="relative p-4 z-[1]">
          {/* Away team row */}
          <div className={`flex items-center gap-3 py-2 transition-opacity ${isFinal && !isAwayWinning ? 'opacity-50' : ''}`}>
            <div className="relative w-8 h-8 flex-shrink-0">
              <Image
                src={awayColors.logo}
                alt={awayTeam.name}
                fill
                className="object-contain"
              />
            </div>
            <span
              className="font-condensed text-sm font-semibold uppercase tracking-wider flex-1"
              style={{ color: awayColors.text }}
            >
              {awayTeam.abbr}
            </span>
            <span
              className={`font-display text-2xl tracking-wide ${
                isAwayWinning && isFinal ? 'text-gold' : 'text-text-primary'
              }`}
            >
              {isPregame ? '-' : awayTeam.score}
            </span>
          </div>

          {/* Home team row */}
          <div className={`flex items-center gap-3 py-2 transition-opacity ${isFinal && !isHomeWinning ? 'opacity-50' : ''}`}>
            <div className="relative w-8 h-8 flex-shrink-0">
              <Image
                src={homeColors.logo}
                alt={homeTeam.name}
                fill
                className="object-contain"
              />
            </div>
            <span
              className="font-condensed text-sm font-semibold uppercase tracking-wider flex-1"
              style={{ color: homeColors.text }}
            >
              {homeTeam.abbr}
            </span>
            <span
              className={`font-display text-2xl tracking-wide ${
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
            relative px-4 py-2.5 border-t border-border-subtle
            ${isActive ? 'bg-positive/10' : 'bg-bg-elevated'}
          `}
        >
          <div className="flex items-center gap-2">
            {isActive && (
              <span
                className="w-1.5 h-1.5 rounded-full bg-positive"
                style={{ boxShadow: '0 0 6px var(--positive)' }}
              />
            )}
            <span
              className={`
                font-condensed text-xs uppercase tracking-wider
                ${isActive ? 'text-positive font-semibold' : isFinal ? 'text-text-muted' : 'text-text-secondary'}
              `}
            >
              {statusDetail}
            </span>
          </div>
        </div>

        {/* Hover gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-gold/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
      </div>
    </Link>
  );
}
