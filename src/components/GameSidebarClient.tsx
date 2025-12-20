'use client';

import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { GameSidebar } from './GameSidebar';
import { useAutoRefresh } from '@/hooks/useAutoRefresh';
import { ScoreboardResponse, WeekSelection, SeasonType } from '@/types';
import { useWeekContext } from '@/contexts/WeekContext';
import { buildScoreboardUrl } from '@/lib/scoreboardUrl';

const REFRESH_INTERVAL = 60000; // 60 seconds

async function fetchScoreboardForWeek(week?: WeekSelection): Promise<ScoreboardResponse> {
  const response = await fetch(buildScoreboardUrl(week));
  if (!response.ok) {
    throw new Error('Failed to fetch scoreboard');
  }
  return response.json();
}

function parseWeekFromSearchParams(searchParams: ReturnType<typeof useSearchParams>): WeekSelection | null {
  const weekParam = searchParams.get('week');
  const seasonTypeParam = searchParams.get('seasontype');

  if (!weekParam && !seasonTypeParam) return null;

  const weekNumber = Number.parseInt(weekParam ?? '', 10);
  const seasonTypeNumber = Number.parseInt(seasonTypeParam ?? '', 10);

  if (!Number.isFinite(weekNumber) || weekNumber <= 0) return null;
  if (seasonTypeNumber !== 1 && seasonTypeNumber !== 2 && seasonTypeNumber !== 3) return null;

  return { weekNumber, seasonType: seasonTypeNumber as SeasonType };
}

export function GameSidebarClient() {
  const searchParams = useSearchParams();
  const [scoreboard, setScoreboard] = useState<ScoreboardResponse | null>(null);
  const [initialLoadDone, setInitialLoadDone] = useState(false);
  const { gameWeek } = useWeekContext();
  const lastWeekSyncAttemptRef = useRef<string | null>(null);

  const requestedWeek = useMemo<WeekSelection | null>(() => {
    return parseWeekFromSearchParams(searchParams) ?? gameWeek ?? null;
  }, [gameWeek, searchParams]);

  // Track the current week for refreshes - use game week from context if available
  const currentWeek = useMemo<WeekSelection | undefined>(() => {
    // If the URL explicitly includes a week (e.g., from the directory page), honor it.
    if (requestedWeek && requestedWeek.weekNumber > 0) {
      return requestedWeek;
    }
    // Otherwise fall back to the scoreboard's week
    if (!scoreboard) return undefined;
    if (scoreboard.week.number <= 0) return undefined;
    return { weekNumber: scoreboard.week.number, seasonType: scoreboard.week.seasonType };
  }, [requestedWeek, scoreboard]);

  const hasActiveGames = scoreboard?.games.some((g) => g.isActive) ?? false;

  // Enable polling if we haven't loaded yet OR if there are active games
  const shouldPoll = !initialLoadDone || hasActiveGames;

  // Memoize fetch function to include current week
  const fetchFn = useCallback(async () => {
    return fetchScoreboardForWeek(currentWeek);
  }, [currentWeek]);

  const { refresh } = useAutoRefresh({
    fetchFn,
    interval: REFRESH_INTERVAL,
    enabled: shouldPoll,
    onSuccess: (data) => {
      setScoreboard(data);
      setInitialLoadDone(true);
    },
  });

  // If the viewed game week is known (via URL params or game payload), sync the sidebar immediately,
  // even when polling is disabled (e.g., no live games).
  useEffect(() => {
    if (!requestedWeek || requestedWeek.weekNumber <= 0 || !scoreboard) return;

    const needsRefetch =
      scoreboard.week.number !== requestedWeek.weekNumber ||
      scoreboard.week.seasonType !== requestedWeek.seasonType;

    if (!needsRefetch) return;

    const attemptKey = `${requestedWeek.seasonType}:${requestedWeek.weekNumber}`;
    if (lastWeekSyncAttemptRef.current === attemptKey) return;
    lastWeekSyncAttemptRef.current = attemptKey;

    refresh();
  }, [requestedWeek, refresh, scoreboard]);

  // Show loading state on initial load
  if (!scoreboard) {
    return (
      <div className="h-full bg-bg-card border-r border-border-subtle flex flex-col">
        <div className="p-4 border-b border-border-subtle">
          <div className="h-6 bg-bg-elevated rounded animate-pulse" />
          <div className="h-4 bg-bg-elevated rounded animate-pulse mt-2 w-24" />
        </div>
        <div className="flex-1 p-2 space-y-2">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-12 bg-bg-elevated rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <GameSidebar
      games={scoreboard.games}
      weekLabel={scoreboard.week.label}
      week={currentWeek ?? null}
    />
  );
}
