'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { ScoreboardResponse, ScoreboardGame } from '@/types';
import { GameCard } from '@/components/GameCard';
import { useAutoRefresh } from '@/hooks/useAutoRefresh';

interface DirectoryClientProps {
  initialData: ScoreboardResponse;
}

const REFRESH_INTERVAL = 60000; // 60 seconds

function sortGames(games: ScoreboardGame[]): ScoreboardGame[] {
  return [...games].sort((a, b) => {
    // In-progress games first
    if (a.isActive && !b.isActive) return -1;
    if (!a.isActive && b.isActive) return 1;

    // Then pregame by start time
    if (a.status === 'pregame' && b.status === 'pregame') {
      const aTime = a.startTime ? new Date(a.startTime).getTime() : 0;
      const bTime = b.startTime ? new Date(b.startTime).getTime() : 0;
      return aTime - bTime;
    }
    if (a.status === 'pregame') return -1;
    if (b.status === 'pregame') return 1;

    // Final games last
    return 0;
  });
}

export function DirectoryClient({ initialData }: DirectoryClientProps) {
  const [scoreboard, setScoreboard] = useState<ScoreboardResponse>(initialData);
  const [changedGameIds, setChangedGameIds] = useState<Set<string>>(new Set());
  const prevScoresRef = useRef<Record<string, { home: number; away: number }>>({});

  // Store initial scores
  useEffect(() => {
    const scores: Record<string, { home: number; away: number }> = {};
    initialData.games.forEach((game) => {
      scores[game.gameId] = {
        home: game.homeTeam.score,
        away: game.awayTeam.score,
      };
    });
    prevScoresRef.current = scores;
  }, [initialData]);

  const hasActiveGames = scoreboard.games.some((g) => g.isActive);

  const fetchScoreboard = useCallback(async (): Promise<ScoreboardResponse> => {
    const response = await fetch('/api/scoreboard');
    if (!response.ok) {
      throw new Error('Failed to fetch scoreboard');
    }
    return response.json();
  }, []);

  const handleRefreshSuccess = useCallback((data: ScoreboardResponse) => {
    // Detect score changes
    const newChangedIds = new Set<string>();
    data.games.forEach((game) => {
      const prevScore = prevScoresRef.current[game.gameId];
      if (prevScore) {
        if (prevScore.home !== game.homeTeam.score || prevScore.away !== game.awayTeam.score) {
          newChangedIds.add(game.gameId);
        }
      }
      // Update stored scores
      prevScoresRef.current[game.gameId] = {
        home: game.homeTeam.score,
        away: game.awayTeam.score,
      };
    });

    if (newChangedIds.size > 0) {
      setChangedGameIds(newChangedIds);
      // Clear highlight after animation
      setTimeout(() => setChangedGameIds(new Set()), 2000);
    }

    setScoreboard(data);
  }, []);

  const { isRefreshing, secondsSinceUpdate } = useAutoRefresh({
    fetchFn: fetchScoreboard,
    interval: REFRESH_INTERVAL,
    enabled: hasActiveGames,
    onSuccess: handleRefreshSuccess,
  });

  const sortedGames = sortGames(scoreboard.games);
  const activeCount = sortedGames.filter((g) => g.isActive).length;

  return (
    <div className="container mx-auto px-6 py-8">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="font-display text-4xl md:text-5xl tracking-wide text-text-primary mb-2">
          NFL {scoreboard.week.label}
        </h1>
        <div className="flex items-center justify-center gap-4">
          <p className="font-condensed text-lg text-text-secondary uppercase tracking-wider">
            {sortedGames.length} Games
            {activeCount > 0 && (
              <span className="ml-2 text-positive">
                • {activeCount} Live
              </span>
            )}
          </p>
        </div>

        {/* Refresh indicator */}
        {hasActiveGames && (
          <div className="mt-4 flex items-center justify-center gap-3 text-text-muted">
            {isRefreshing ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                <span className="font-condensed text-xs uppercase tracking-wider">
                  Updating scores...
                </span>
              </>
            ) : (
              <span className="font-condensed text-xs uppercase tracking-wider">
                Scores update automatically
              </span>
            )}
          </div>
        )}
      </div>

      {/* Games grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {sortedGames.map((game) => (
          <div
            key={game.gameId}
            className={`transition-all duration-500 ${
              changedGameIds.has(game.gameId)
                ? 'ring-2 ring-positive ring-offset-2 ring-offset-bg-deep'
                : ''
            }`}
          >
            <GameCard game={game} />
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="mt-12 text-center">
        <p className="font-condensed text-xs text-text-muted uppercase tracking-wider">
          Data from ESPN • Click any game for detailed analysis
          {hasActiveGames && secondsSinceUpdate > 0 && (
            <span className="ml-2">
              • Updated {secondsSinceUpdate < 60 ? `${secondsSinceUpdate}s` : `${Math.floor(secondsSinceUpdate / 60)}m`} ago
            </span>
          )}
        </p>
      </div>
    </div>
  );
}
