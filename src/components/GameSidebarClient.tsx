'use client';

import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { GameSidebar } from './GameSidebar';
import { useAutoRefresh } from '@/hooks/useAutoRefresh';
import { ScoreboardResponse, WeekSelection, SeasonType } from '@/types';
import { useWeekContext } from '@/contexts/WeekContext';
import { buildScoreboardUrl } from '@/lib/scoreboardUrl';
import styles from './GameSidebar.module.css';
import { isTerminalGame } from '@/lib/gameStatus';
import { isScoreboardResponse } from '@/lib/scoreboardResponse';
import { formatCheckAge } from '@/lib/refreshStatus';

const REFRESH_INTERVAL = 60000; // 60 seconds

async function fetchScoreboardForWeek(week?: WeekSelection): Promise<ScoreboardResponse> {
  const response = await fetch(buildScoreboardUrl(week), { cache: 'no-store' });
  if (!response.ok) {
    throw new Error('Failed to fetch scoreboard');
  }
  const data = await response.json();
  if (!isScoreboardResponse(data)) throw new Error('Scoreboard data is unavailable');
  return data;
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

  const hasUnfinishedGames = scoreboard?.games.some((g) => !isTerminalGame(g.status)) ?? false;

  // Keep pregame rows current through kickoff, then stop after every game is final.
  const shouldPoll = !initialLoadDone || hasUnfinishedGames;

  // Memoize fetch function to include current week
  const fetchFn = useCallback(async () => {
    return fetchScoreboardForWeek(currentWeek);
  }, [currentWeek]);

  const { refresh, error: refreshError, isRefreshing, hasSuccessfulRefresh, secondsSinceUpdate } = useAutoRefresh({
    fetchFn,
    interval: REFRESH_INTERVAL,
    enabled: shouldPoll,
    resetKey: requestedWeek ? `${requestedWeek.seasonType}:${requestedWeek.weekNumber}` : 'current',
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
    return <div className={styles.sidebar} role="status" aria-label={refreshError ? 'Games unavailable' : 'Loading games'}>
      <div className={styles.header}><span className={styles.brand}>GAME<span>/</span>EXPLAINED</span><div className={styles.week}>{refreshError ? 'Games unavailable' : 'Loading games'}</div></div>
      {refreshError ? <div className={styles.loadError}>Games could not be loaded.<button onClick={refresh}>Try again</button></div>
        : <div className={styles.list}>{[...Array(6)].map((_, i) => <div key={i} className={styles.loadingRow} />)}</div>}
    </div>;
  }

  return (
    <GameSidebar
      games={scoreboard.games}
      weekLabel={scoreboard.week.label}
      week={currentWeek ?? null}
      refreshFailed={!!refreshError}
      refreshStatus={shouldPoll ? refreshError
        ? `Updates interrupted · ${hasSuccessfulRefresh ? `last check ${formatCheckAge(secondsSinceUpdate)}` : 'no successful check yet'}`
        : isRefreshing ? hasSuccessfulRefresh ? `Checking… · last checked ${formatCheckAge(secondsSinceUpdate)}` : 'Checking scores…'
          : hasSuccessfulRefresh ? `Checked ${formatCheckAge(secondsSinceUpdate)}` : 'Checking scores…' : undefined}
    />
  );
}
