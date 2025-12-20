'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { ScoreboardResponse, ScoreboardGame, WeekSelection } from '@/types';
import { GameCard } from '@/components/GameCard';
import { WeekPicker } from '@/components/WeekPicker';
import { useAutoRefresh } from '@/hooks/useAutoRefresh';
import { DirectoryLoading } from '@/components/LoadingStates';
import { weekToUrlParam } from '@/lib/weekUtils';
import { buildScoreboardUrl } from '@/lib/scoreboardUrl';

interface DirectoryClientProps {
  initialData: ScoreboardResponse;
}

const REFRESH_INTERVAL = 60000; // 60 seconds

/**
 * Fallback component that loads scoreboard data client-side
 * Used when server-side fetch fails
 */
export function DirectoryClientFallback() {
  const [scoreboard, setScoreboard] = useState<ScoreboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadScoreboard() {
      try {
        const response = await fetch('/api/scoreboard');
        if (!response.ok) {
          throw new Error(`Failed to load: ${response.status}`);
        }
        const data = await response.json();
        setScoreboard(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load games');
      } finally {
        setLoading(false);
      }
    }
    loadScoreboard();
  }, []);

  if (loading) {
    return <DirectoryLoading />;
  }

  if (error || !scoreboard) {
    return (
      <div className="container mx-auto px-6 py-12 text-center">
        <h1 className="font-display text-4xl text-text-primary mb-4">Unable to Load Games</h1>
        <p className="text-text-secondary mb-4">{error || 'Please try again later.'}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-gold text-bg-deep rounded-lg font-condensed uppercase tracking-wider"
        >
          Retry
        </button>
      </div>
    );
  }

  if (scoreboard.games.length === 0) {
    return (
      <div className="container mx-auto px-6 py-12 text-center">
        <h1 className="font-display text-4xl text-text-primary mb-4">No Games Today</h1>
        <p className="text-text-secondary">Check back during game days.</p>
      </div>
    );
  }

  return <DirectoryClient initialData={scoreboard} />;
}

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
  const router = useRouter();
  const [scoreboard, setScoreboard] = useState<ScoreboardResponse>(initialData);
  const [changedGameIds, setChangedGameIds] = useState<Set<string>>(new Set());
  const prevScoresRef = useRef<Record<string, { home: number; away: number }>>({});

  // Current week from scoreboard data
  const currentWeek: WeekSelection = {
    weekNumber: scoreboard.week.number,
    seasonType: scoreboard.week.seasonType,
  };
  const { weekNumber, seasonType } = currentWeek;

  const handleWeekChange = useCallback((week: WeekSelection) => {
    const param = weekToUrlParam(week);
    router.push(`/?week=${param}`);
    router.refresh();
  }, [router]);

  // Update scoreboard when initialData changes (e.g., week picker navigation)
  useEffect(() => {
    setScoreboard(initialData);
  }, [initialData]);

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
    const response = await fetch(buildScoreboardUrl({ weekNumber, seasonType }));
    if (!response.ok) {
      throw new Error('Failed to fetch scoreboard');
    }
    return response.json();
  }, [weekNumber, seasonType]);

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
        <div className="flex items-center justify-center gap-4 flex-wrap">
          <WeekPicker currentWeek={currentWeek} onWeekChange={handleWeekChange} />
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
            <GameCard game={game} week={currentWeek} />
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
