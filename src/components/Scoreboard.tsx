'use client';

import { ScoreboardProps } from '@/types';
import { getTeamColorVars } from '@/lib/teamColors';
import Image from 'next/image';

export function Scoreboard({ homeTeam, awayTeam, status, statusDetail }: ScoreboardProps) {
  const awayColors = getTeamColorVars(awayTeam.abbr);
  const homeColors = getTeamColorVars(homeTeam.abbr);

  const isHomeWinning = homeTeam.score > awayTeam.score;
  const isAwayWinning = awayTeam.score > homeTeam.score;
  const isFinal = status === 'final';

  return (
    <section className="relative flex flex-col overflow-hidden rounded-2xl">
      {/* Hero Background - Diagonal Split */}
      <div className="absolute inset-0 z-0">
        {/* Diagonal team colors */}
        <div
          className="absolute inset-0"
          style={{
            background: `linear-gradient(135deg, ${awayColors.primary} 0%, ${awayColors.primary} 50%, ${homeColors.primary} 50%, ${homeColors.primary} 100%)`
          }}
        />
        {/* Gradient overlays for depth */}
        <div
          className="absolute inset-0"
          style={{
            background: `
              radial-gradient(ellipse 60% 80% at 20% 50%, rgba(0,0,0,0.3) 0%, transparent 60%),
              radial-gradient(ellipse 60% 80% at 80% 50%, rgba(0,0,0,0.3) 0%, transparent 60%),
              linear-gradient(180deg, transparent 60%, var(--bg-deep) 100%)
            `
          }}
        />
        {/* Stadium lights effect */}
        <div
          className="absolute top-[-50%] left-1/2 w-[200%] h-full -translate-x-1/2 pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse 50% 30% at 50% 0%, rgba(255,255,255,0.08) 0%, transparent 60%)'
          }}
        />
      </div>

      {/* Content */}
      <div className="relative z-10 flex-1 flex flex-col">
        <div className="container mx-auto px-4 md:px-6">
          {/* Scoreboard Grid */}
          <div className="grid grid-cols-3 items-center gap-2 md:gap-4 py-4 md:py-5 max-w-4xl mx-auto w-full">
            {/* Away Team */}
            <div className="flex flex-col items-center md:items-end gap-2 md:gap-4 text-center md:text-right">
              <div
                className="w-[70px] h-[70px] md:w-[100px] md:h-[100px] flex items-center justify-center rounded-2xl backdrop-blur-md transition-all duration-300 hover:scale-105 hover:shadow-xl"
                style={{
                  background: 'rgba(255,255,255,0.1)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  boxShadow: '0 8px 32px rgba(0,0,0,0.3)'
                }}
              >
                <div className="relative w-[50px] h-[50px] md:w-[70px] md:h-[70px]">
                  <Image
                    src={awayColors.logo}
                    alt={awayTeam.name}
                    fill
                    className="object-contain"
                  />
                </div>
              </div>
              <div className="flex flex-col gap-0.5">
                <h2
                  className="font-display text-xl md:text-3xl lg:text-4xl tracking-wide text-text-primary"
                  style={{ textShadow: '0 2px 10px rgba(0,0,0,0.5)' }}
                >
                  {awayTeam.name.split(' ').pop()}
                </h2>
              </div>
            </div>

            {/* Score Center */}
            <div className="flex flex-col items-center gap-3 md:gap-4 px-2 md:px-8">
              <div className="flex items-center gap-2 md:gap-4">
                <span
                  className={`font-display text-5xl md:text-7xl lg:text-8xl leading-none tracking-tight relative ${isAwayWinning && isFinal ? 'text-gold' : 'text-text-primary'}`}
                  style={{ textShadow: '0 4px 20px rgba(0,0,0,0.5)' }}
                >
                  {awayTeam.score}
                  {isAwayWinning && isFinal && (
                    <span
                      className="absolute bottom-[-8px] left-1/2 -translate-x-1/2 w-4/5 h-1 rounded bg-gold"
                      style={{ boxShadow: '0 0 20px var(--gold)' }}
                    />
                  )}
                </span>
                <span className="font-display text-4xl md:text-5xl text-white/30">-</span>
                <span
                  className={`font-display text-5xl md:text-7xl lg:text-8xl leading-none tracking-tight relative ${isHomeWinning && isFinal ? 'text-gold' : 'text-text-primary'}`}
                  style={{ textShadow: '0 4px 20px rgba(0,0,0,0.5)' }}
                >
                  {homeTeam.score}
                  {isHomeWinning && isFinal && (
                    <span
                      className="absolute bottom-[-8px] left-1/2 -translate-x-1/2 w-4/5 h-1 rounded bg-gold"
                      style={{ boxShadow: '0 0 20px var(--gold)' }}
                    />
                  )}
                </span>
              </div>

              {/* Game Status Indicator */}
              <div
                className="px-4 py-1.5 rounded-full backdrop-blur-md"
                style={{
                  background: 'rgba(255,255,255,0.1)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
                }}
              >
                <span className="font-condensed text-xs md:text-sm font-semibold uppercase tracking-wider text-text-secondary">
                  {isFinal ? 'Final' : statusDetail}
                </span>
              </div>
            </div>

            {/* Home Team */}
            <div className="flex flex-col items-center md:items-start gap-2 md:gap-4 text-center md:text-left">
              <div
                className="w-[70px] h-[70px] md:w-[100px] md:h-[100px] flex items-center justify-center rounded-2xl backdrop-blur-md transition-all duration-300 hover:scale-105 hover:shadow-xl"
                style={{
                  background: 'rgba(255,255,255,0.1)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  boxShadow: '0 8px 32px rgba(0,0,0,0.3)'
                }}
              >
                <div className="relative w-[50px] h-[50px] md:w-[70px] md:h-[70px]">
                  <Image
                    src={homeColors.logo}
                    alt={homeTeam.name}
                    fill
                    className="object-contain"
                  />
                </div>
              </div>
              <div className="flex flex-col gap-0.5">
                <h2
                  className="font-display text-xl md:text-3xl lg:text-4xl tracking-wide text-text-primary"
                  style={{ textShadow: '0 2px 10px rgba(0,0,0,0.5)' }}
                >
                  {homeTeam.name.split(' ').pop()}
                </h2>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
