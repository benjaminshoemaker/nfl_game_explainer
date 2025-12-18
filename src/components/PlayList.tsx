'use client';

import { PlayDetail } from '@/types';

interface PlayListProps {
  plays: PlayDetail[];
  teamSecondary: string;
  teamTextColor: string;
  side: 'away' | 'home';
}

function formatWpDelta(delta: number): string {
  const sign = delta >= 0 ? '+' : '';
  return `${sign}${(delta * 100).toFixed(1)}%`;
}

function getWpDeltaClass(delta: number): { bg: string; text: string; isBig: boolean } {
  const isBig = Math.abs(delta) > 0.15;
  if (delta > 0.01) {
    return {
      bg: 'rgba(16, 185, 129, 0.2)',
      text: 'var(--positive)',
      isBig,
    };
  }
  if (delta < -0.01) {
    return {
      bg: 'rgba(239, 68, 68, 0.2)',
      text: 'var(--negative)',
      isBig,
    };
  }
  return {
    bg: 'var(--bg-deep)',
    text: 'var(--text-muted)',
    isBig: false,
  };
}

function getPlayTypeBadge(type: string): { bg: string; text: string; label: string } {
  const typeLower = type.toLowerCase();
  if (typeLower.includes('pass') || typeLower.includes('passing')) {
    return {
      bg: 'rgba(59, 130, 246, 0.2)',
      text: '#60a5fa',
      label: 'PASS',
    };
  }
  if (typeLower.includes('run') || typeLower.includes('rush')) {
    return {
      bg: 'rgba(251, 146, 60, 0.2)',
      text: '#fb923c',
      label: 'RUN',
    };
  }
  if (typeLower.includes('interception') || typeLower.includes('fumble') || typeLower.includes('turnover')) {
    return {
      bg: 'rgba(239, 68, 68, 0.2)',
      text: 'var(--negative)',
      label: 'TURNOVER',
    };
  }
  if (typeLower.includes('punt')) {
    return {
      bg: 'rgba(156, 163, 175, 0.2)',
      text: 'var(--text-muted)',
      label: 'PUNT',
    };
  }
  if (typeLower.includes('kick') || typeLower.includes('field goal')) {
    return {
      bg: 'rgba(251, 191, 36, 0.2)',
      text: 'var(--gold)',
      label: 'KICK',
    };
  }
  return {
    bg: 'var(--bg-deep)',
    text: 'var(--text-muted)',
    label: type.toUpperCase().slice(0, 10),
  };
}

function extractHeadline(text: string, type: string): string {
  // Try to extract a short headline from the play text
  const parts = text.split(' to ');
  if (parts.length > 1) {
    const receiver = parts[1].split(' ')[0];
    const match = text.match(/for (\d+) yards?/);
    if (match) {
      return `${receiver} ${match[1]} YD ${type.includes('Pass') ? 'PASS' : type.includes('Run') ? 'RUN' : type.toUpperCase()}`;
    }
    return `${receiver} ${type.toUpperCase()}`;
  }
  // Fallback: use type and yards
  const yardsMatch = text.match(/(\d+) yard/);
  if (yardsMatch) {
    return `${yardsMatch[1]} YD ${type.toUpperCase()}`;
  }
  return type.toUpperCase();
}

export function PlayList({ plays, teamSecondary, teamTextColor, side }: PlayListProps) {
  if (plays.length === 0) {
    return (
      <div className="py-8 px-4 text-center border border-dashed border-border-medium rounded-xl">
        <svg
          className="w-12 h-12 mx-auto mb-4 opacity-30"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="font-body text-sm text-text-muted">
          No plays in this category
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3.5">
      {plays.map((play, index) => {
        // Determine WP delta for this team
        const wpDelta = side === 'away'
          ? (play.probability?.awayDelta ?? 0)
          : (play.probability?.homeDelta ?? 0);

        const hasWpDelta = Math.abs(wpDelta) > 0.005;
        const wpStyle = getWpDeltaClass(wpDelta);
        const typeBadge = getPlayTypeBadge(play.type);
        const headline = extractHeadline(play.text, play.type);

        // Big play: significant yards or WP swing
        const isBigPlay = (play.yards && Math.abs(play.yards) >= 20) || Math.abs(wpDelta) > 0.15;

        return (
          <div
            key={index}
            className={`
              relative rounded-xl p-5 border transition-all duration-200
              hover:-translate-y-[3px] hover:shadow-xl
              ${isBigPlay ? 'border-2' : 'border border-border-subtle'}
            `}
            style={{
              background: isBigPlay
                ? `linear-gradient(135deg, var(--bg-elevated) 0%, var(--bg-card) 100%)`
                : 'var(--bg-elevated)',
              borderColor: isBigPlay ? teamSecondary : undefined,
              animationDelay: `${index * 0.05}s`,
            }}
          >
            {/* Left color bar */}
            <div
              className={`absolute top-0 left-0 h-full rounded-l-xl ${isBigPlay ? 'w-1.5' : 'w-1'}`}
              style={{ backgroundColor: teamSecondary }}
            />

            {/* Big play corner ribbon */}
            {isBigPlay && (
              <div
                className="absolute top-0 right-0 w-0 h-0 opacity-80"
                style={{
                  borderStyle: 'solid',
                  borderWidth: '0 32px 32px 0',
                  borderColor: `transparent ${teamSecondary} transparent transparent`,
                }}
              />
            )}

            {/* Play header */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                {/* Quarter badge */}
                <span
                  className="px-2 py-1 rounded text-xs font-condensed font-semibold uppercase tracking-wider"
                  style={{
                    background: 'var(--bg-deep)',
                    color: 'var(--text-secondary)',
                  }}
                >
                  Q{play.quarter || '?'}
                </span>
                {/* Clock */}
                {play.clock && (
                  <span className="font-condensed text-xs text-text-muted uppercase tracking-wider">
                    {play.clock}
                  </span>
                )}
              </div>

              {/* Play type badge */}
              <span
                className="px-2 py-1 rounded text-xs font-display tracking-wider"
                style={{
                  background: typeBadge.bg,
                  color: typeBadge.text,
                }}
              >
                {typeBadge.label}
              </span>
            </div>

            {/* Headline */}
            <h4
              className="font-display text-lg md:text-xl tracking-wide leading-tight mb-2"
              style={{ color: teamTextColor }}
            >
              {headline}
            </h4>

            {/* Full text */}
            <p className="font-body text-sm text-text-muted leading-relaxed mb-3 max-h-[4.5rem] overflow-hidden">
              {play.text}
            </p>

            {/* Footer */}
            <div className="flex items-center justify-between flex-wrap gap-2">
              {/* Yards badge */}
              {play.yards !== undefined && play.yards !== 0 && (
                <span
                  className="font-display text-sm px-3 py-1 rounded-md"
                  style={{
                    background: 'var(--bg-deep)',
                    color: play.yards > 0 ? 'var(--positive)' : 'var(--negative)',
                  }}
                >
                  {play.yards > 0 ? '+' : ''}{play.yards} YDS
                </span>
              )}

              {/* Points badge */}
              {play.points !== undefined && play.points > 0 && (
                <span
                  className="font-display text-sm px-3 py-1 rounded-md"
                  style={{
                    background: 'rgba(251, 191, 36, 0.2)',
                    color: 'var(--gold)',
                  }}
                >
                  +{play.points} PTS
                </span>
              )}

              {/* WP Delta */}
              {hasWpDelta && (
                <div className="flex items-center gap-2 ml-auto">
                  <span
                    className={`font-display text-sm px-3 py-1 rounded-md tracking-wide ${wpStyle.isBig ? 'animate-pulse' : ''}`}
                    style={{
                      background: wpStyle.bg,
                      color: wpStyle.text,
                      boxShadow: wpStyle.isBig ? `0 0 15px ${wpStyle.text}40` : 'none',
                    }}
                  >
                    WP {formatWpDelta(wpDelta)}
                  </span>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
