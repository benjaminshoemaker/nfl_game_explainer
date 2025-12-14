'use client';

import { ScoreboardProps } from '@/types';
import { getTeamColors, getTeamLogo } from '@/lib/teamColors';
import Image from 'next/image';

export function Scoreboard({ homeTeam, awayTeam, status, statusDetail }: ScoreboardProps) {
  const awayColors = getTeamColors(awayTeam.abbr);
  const homeColors = getTeamColors(homeTeam.abbr);

  const isHomeWinning = homeTeam.score > awayTeam.score;
  const isAwayWinning = awayTeam.score > homeTeam.score;
  const isFinal = status === 'final';

  return (
    <div className="relative w-full overflow-hidden rounded-2xl bg-bg-card">
      {/* Background with team colors */}
      <div className="absolute inset-0 overflow-hidden">
        {/* Away team side */}
        <div
          className="absolute inset-y-0 left-0 w-1/2"
          style={{
            background: `linear-gradient(135deg, ${awayColors.primary}40 0%, ${awayColors.primary}10 100%)`
          }}
        />
        {/* Home team side */}
        <div
          className="absolute inset-y-0 right-0 w-1/2"
          style={{
            background: `linear-gradient(225deg, ${homeColors.primary}40 0%, ${homeColors.primary}10 100%)`
          }}
        />
        {/* Diagonal separator */}
        <div
          className="absolute inset-0"
          style={{
            background: `linear-gradient(to right, transparent 48%, var(--bg-card) 50%, transparent 52%)`
          }}
        />
      </div>

      {/* Content */}
      <div className="relative z-10 px-4 py-8 md:px-8 md:py-12">
        <div className="flex items-center justify-between">
          {/* Away Team */}
          <div className={`flex flex-col items-center gap-3 flex-1 ${isAwayWinning && isFinal ? 'opacity-100' : isFinal ? 'opacity-70' : ''}`}>
            <div className="relative w-16 h-16 md:w-24 md:h-24">
              <Image
                src={getTeamLogo(awayTeam.abbr)}
                alt={awayTeam.name}
                fill
                className="object-contain"
              />
            </div>
            <span
              className="font-condensed text-lg md:text-xl font-semibold tracking-wide uppercase"
              style={{ color: awayColors.secondary }}
            >
              {awayTeam.abbr}
            </span>
          </div>

          {/* Score */}
          <div className="flex flex-col items-center gap-2 flex-shrink-0 px-4">
            <div className="flex items-center gap-4 md:gap-8">
              <span
                className={`font-display text-5xl md:text-7xl tracking-wide ${isAwayWinning && isFinal ? 'text-gold' : 'text-text-primary'}`}
              >
                {awayTeam.score}
              </span>
              <span className="font-display text-3xl md:text-5xl text-text-muted">-</span>
              <span
                className={`font-display text-5xl md:text-7xl tracking-wide ${isHomeWinning && isFinal ? 'text-gold' : 'text-text-primary'}`}
              >
                {homeTeam.score}
              </span>
            </div>
            {/* Status */}
            <div className="flex items-center gap-2">
              {status === 'in-progress' && (
                <span className="w-2 h-2 rounded-full bg-positive animate-pulse-glow" />
              )}
              <span className={`font-condensed text-sm md:text-base uppercase tracking-wider ${status === 'in-progress' ? 'text-positive' : 'text-text-secondary'}`}>
                {statusDetail || status}
              </span>
            </div>
          </div>

          {/* Home Team */}
          <div className={`flex flex-col items-center gap-3 flex-1 ${isHomeWinning && isFinal ? 'opacity-100' : isFinal ? 'opacity-70' : ''}`}>
            <div className="relative w-16 h-16 md:w-24 md:h-24">
              <Image
                src={getTeamLogo(homeTeam.abbr)}
                alt={homeTeam.name}
                fill
                className="object-contain"
              />
            </div>
            <span
              className="font-condensed text-lg md:text-xl font-semibold tracking-wide uppercase"
              style={{ color: homeColors.secondary }}
            >
              {homeTeam.abbr}
            </span>
          </div>
        </div>
      </div>

      {/* Winner glow effect */}
      {isFinal && (isHomeWinning || isAwayWinning) && (
        <div
          className="absolute inset-y-0 w-1/3 pointer-events-none"
          style={{
            [isAwayWinning ? 'left' : 'right']: 0,
            background: `radial-gradient(ellipse at ${isAwayWinning ? 'left' : 'right'} center, ${isAwayWinning ? awayColors.primary : homeColors.primary}30 0%, transparent 70%)`
          }}
        />
      )}
    </div>
  );
}
