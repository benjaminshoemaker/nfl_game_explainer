'use client';

import { useState } from 'react';
import { PlayDetail } from '@/types';

interface PlayListProps {
  plays: PlayDetail[];
  teamAbbr: string;
  teamColor: string;
}

function formatWpDelta(delta: number): string {
  const sign = delta >= 0 ? '+' : '';
  return `${sign}${(delta * 100).toFixed(1)}%`;
}

function getWpDeltaColor(delta: number): string {
  if (delta > 0.01) return 'text-positive';
  if (delta < -0.01) return 'text-negative';
  return 'text-text-muted';
}

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + '...';
}

export function PlayList({ plays, teamAbbr, teamColor }: PlayListProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  if (plays.length === 0) {
    return (
      <div className="py-4 text-center text-text-muted font-body text-sm">
        No plays in this category
      </div>
    );
  }

  return (
    <div className="divide-y divide-border-subtle">
      {plays.map((play, index) => {
        const isExpanded = expandedIndex === index;
        const wpDelta = play.probability?.homeDelta ?? play.probability?.awayDelta ?? 0;
        const hasSignificantWp = Math.abs(wpDelta) > 0.01;

        return (
          <div
            key={index}
            className="group cursor-pointer transition-colors hover:bg-bg-elevated/50"
            onClick={() => setExpandedIndex(isExpanded ? null : index)}
          >
            {/* Collapsed row */}
            <div className="flex items-center gap-3 py-3 px-2">
              {/* Quarter/Clock */}
              <div className="flex-shrink-0 w-16">
                <span className="font-condensed text-xs text-text-muted uppercase tracking-wider">
                  Q{play.quarter || '?'} {play.clock || ''}
                </span>
              </div>

              {/* Play type badge */}
              <div
                className="flex-shrink-0 px-2 py-0.5 rounded text-xs font-condensed uppercase tracking-wider"
                style={{
                  backgroundColor: `${teamColor}20`,
                  color: teamColor,
                }}
              >
                {play.type}
              </div>

              {/* Description */}
              <div className="flex-1 min-w-0">
                <p className="font-body text-sm text-text-secondary truncate">
                  {isExpanded ? play.text : truncateText(play.text, 50)}
                </p>
              </div>

              {/* WP Delta */}
              {hasSignificantWp && (
                <div className={`flex-shrink-0 font-mono text-xs ${getWpDeltaColor(wpDelta)}`}>
                  {formatWpDelta(wpDelta)}
                </div>
              )}

              {/* Expand indicator */}
              <div className="flex-shrink-0 text-text-muted">
                <svg
                  className={`w-4 h-4 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </div>

            {/* Expanded content */}
            <div
              className={`overflow-hidden transition-all duration-200 ease-in-out ${
                isExpanded ? 'max-h-40 opacity-100' : 'max-h-0 opacity-0'
              }`}
            >
              <div className="px-2 pb-3 pt-1">
                <div
                  className="p-3 rounded-lg text-sm font-body text-text-primary leading-relaxed"
                  style={{ backgroundColor: `${teamColor}10` }}
                >
                  {play.text}
                  {play.yards !== undefined && play.yards !== 0 && (
                    <span className="ml-2 font-condensed text-xs text-text-muted">
                      ({play.yards > 0 ? '+' : ''}{play.yards} yards)
                    </span>
                  )}
                  {play.points !== undefined && play.points > 0 && (
                    <span className="ml-2 font-condensed text-xs text-gold">
                      +{play.points} pts
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
