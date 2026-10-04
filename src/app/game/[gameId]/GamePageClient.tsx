'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { GameResponse } from '@/types';
import { GameExplorer } from '@/components/GameExplorer';
import { useAutoRefresh } from '@/hooks/useAutoRefresh';
import { useWeekContext } from '@/contexts/WeekContext';
import { GameDebugView } from '@/components/GameDebugView';
import styles from './GamePageClient.module.css';
import { gameStatusLabel, isTerminalGame } from '@/lib/gameStatus';
import { ErrorState } from '@/components/ErrorState';
import { formatCheckAge, latestPlayLabel, playFeedKey } from '@/lib/refreshStatus';

interface GamePageClientProps {
  initialGameData: GameResponse;
  debugMode?: boolean;
}
type ViewMode = 'competitive' | 'full';
const REFRESH_INTERVAL = 60000;

export function GamePageClient({ initialGameData, debugMode = false }: GamePageClientProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('competitive');
  const [gameData, setGameData] = useState<GameResponse>(initialGameData);
  const [noNewPlays, setNoNewPlays] = useState(false);
  const lastPlayKeyRef = useRef(playFeedKey(initialGameData.plays));
  const currentGameId = initialGameData.gameId;
  const { setGameWeek } = useWeekContext();
  const isLive = gameData.status === 'in-progress';
  const wpFilterAvailable = gameData.wp_filter?.enabled !== false;
  const effectiveViewMode: ViewMode = wpFilterAvailable ? viewMode : 'full';

  useEffect(() => {
    setGameData(initialGameData);
    setViewMode('competitive');
    setNoNewPlays(false);
    lastPlayKeyRef.current = playFeedKey(initialGameData.plays);
  }, [initialGameData]);

  useEffect(() => {
    if (gameData.week && gameData.week.number > 0) {
      setGameWeek({ weekNumber: gameData.week.number, seasonType: gameData.week.seasonType });
    } else {
      setGameWeek(null);
    }
  }, [gameData.week, setGameWeek]);

  const fetchGameData = useCallback(async (): Promise<GameResponse> => {
    const response = await fetch(`/api/game/${gameData.gameId}${debugMode ? '?debug=true' : ''}`, { cache: 'no-store' });
    if (!response.ok) throw new Error('Failed to fetch game data');
    return response.json();
  }, [gameData.gameId, debugMode]);

  const { isRefreshing, secondsSinceUpdate, hasSuccessfulRefresh, error: refreshError, refresh } = useAutoRefresh({
    fetchFn: fetchGameData,
    interval: REFRESH_INTERVAL,
    enabled: !isTerminalGame(gameData.status),
    resetKey: currentGameId,
    onSuccess: data => {
      if (data.gameId !== currentGameId) return;
      const nextPlayKey = playFeedKey(data.plays);
      setNoNewPlays(nextPlayKey === lastPlayKeyRef.current);
      lastPlayKeyRef.current = nextPlayKey;
      setGameData(data);
    },
  });

  if (debugMode) return <GameDebugView gameData={gameData} />;
  const away = gameData.team_meta.find(team => team.homeAway === 'away');
  const home = gameData.team_meta.find(team => team.homeAway === 'home');
  if (!away || !home) return <ErrorState title="Game data incomplete" message="ESPN has not provided both teams for this game. Please try again shortly." />;
  const isPolling = !isTerminalGame(gameData.status);
  const checkStatus = refreshError
    ? `Updates interrupted · ${hasSuccessfulRefresh ? `last successful check ${formatCheckAge(secondsSinceUpdate)}` : 'no successful check yet'}`
    : isRefreshing ? hasSuccessfulRefresh ? `Checking for updates… · last checked ${formatCheckAge(secondsSinceUpdate)}` : 'Checking for updates…'
      : hasSuccessfulRefresh ? `Checked ${formatCheckAge(secondsSinceUpdate)}` : 'Checking for updates…';
  const latestPlay = gameData.plays?.[gameData.plays.length - 1];
  const latestPlayText = latestPlayLabel(latestPlay);

  return <div className={styles.page}>
    <div className={styles.scopeBar}>
      <span className={isLive ? styles.live : ''}>{isLive ? '● ' : ''}{gameStatusLabel(gameData.status, gameData.statusDetail)}{isPolling ? ` · ${checkStatus}` : ''}</span>
      {gameData.status !== 'pregame' && gameData.status !== 'postponed' && gameData.status !== 'canceled' && <div className={styles.scopeControls}>
        <span>{effectiveViewMode === 'competitive' || !wpFilterAvailable ? gameData.wp_filter?.description : 'Showing full-game totals'}</span>
        {wpFilterAvailable && <div role="group" aria-label="Stat scope" className={styles.scopeButtons}>
          <button type="button" aria-pressed={viewMode === 'competitive'} onClick={() => setViewMode('competitive')}>Competitive</button>
          <button type="button" aria-pressed={viewMode === 'full'} onClick={() => setViewMode('full')}>Full game</button>
        </div>}
      </div>}
    </div>
    {latestPlayText && (gameData.status === 'in-progress' || gameData.status === 'delayed') && <div className={styles.playFreshness} role="status"><span>{latestPlayText}</span>{noNewPlays && !refreshError && <span>No new plays since last check</span>}</div>}
    {refreshError && <div className={styles.refreshError} role="status">Could not refresh this game. Showing the last loaded report and retrying automatically. <button onClick={refresh}>Try again</button></div>}
    <GameExplorer key={gameData.gameId} game={gameData} scope={effectiveViewMode} home={home} away={away} />
  </div>;
}
