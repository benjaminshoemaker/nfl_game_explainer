'use client';

import { useState } from 'react';
import { GameSidebar } from './GameSidebar';
import { useAutoRefresh } from '@/hooks/useAutoRefresh';
import { ScoreboardResponse } from '@/types';

const REFRESH_INTERVAL = 60000; // 60 seconds

async function fetchScoreboard(): Promise<ScoreboardResponse> {
  const response = await fetch('/api/scoreboard');
  if (!response.ok) {
    throw new Error('Failed to fetch scoreboard');
  }
  return response.json();
}

export function GameSidebarClient() {
  const [scoreboard, setScoreboard] = useState<ScoreboardResponse | null>(null);
  const [initialLoadDone, setInitialLoadDone] = useState(false);

  const hasActiveGames = scoreboard?.games.some((g) => g.isActive) ?? false;

  // Enable polling if we haven't loaded yet OR if there are active games
  const shouldPoll = !initialLoadDone || hasActiveGames;

  useAutoRefresh({
    fetchFn: fetchScoreboard,
    interval: REFRESH_INTERVAL,
    enabled: shouldPoll,
    onSuccess: (data) => {
      setScoreboard(data);
      setInitialLoadDone(true);
    },
  });

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
    />
  );
}
