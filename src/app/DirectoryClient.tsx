'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { ScoreboardResponse, WeekSelection } from '@/types';
import { GameCard } from '@/components/GameCard';
import { WeekPicker } from '@/components/WeekPicker';
import { useAutoRefresh } from '@/hooks/useAutoRefresh';
import { DirectoryLoading } from '@/components/LoadingStates';
import { weekToUrlParam } from '@/lib/weekUtils';
import { buildScoreboardUrl } from '@/lib/scoreboardUrl';
import styles from './Directory.module.css';
import { isTerminalGame } from '@/lib/gameStatus';
import { sortScoreboardGames } from '@/lib/sortScoreboardGames';
import { isScoreboardResponse } from '@/lib/scoreboardResponse';
import { formatCheckAge } from '@/lib/refreshStatus';

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
        if (!isScoreboardResponse(data)) throw new Error('Scoreboard data is unavailable');
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
      <div className={styles.fallback}>
        <h1>Unable to load games</h1>
        <p>{error || 'Please try again later.'}</p>
        <button onClick={() => window.location.reload()}>Retry</button>
      </div>
    );
  }

  return <DirectoryClient initialData={scoreboard} />;
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

  const hasUnfinishedGames = scoreboard.games.some((g) => !isTerminalGame(g.status));

  const fetchScoreboard = useCallback(async (): Promise<ScoreboardResponse> => {
    const response = await fetch(buildScoreboardUrl({ weekNumber, seasonType }), { cache: 'no-store' });
    if (!response.ok) {
      throw new Error('Failed to fetch scoreboard');
    }
    const data = await response.json();
    if (!isScoreboardResponse(data)) throw new Error('Scoreboard data is unavailable');
    return data;
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

  const { isRefreshing, secondsSinceUpdate, hasSuccessfulRefresh, error: refreshError, refresh } = useAutoRefresh({
    fetchFn: fetchScoreboard,
    interval: REFRESH_INTERVAL,
    enabled: hasUnfinishedGames,
    resetKey: `${seasonType}:${weekNumber}`,
    onSuccess: handleRefreshSuccess,
  });

  const sortedGames = sortScoreboardGames(scoreboard.games);
  const activeCount = sortedGames.filter((g) => g.isActive).length;
  const scoreCheckStatus = refreshError
    ? `Updates interrupted · ${hasSuccessfulRefresh ? `last successful check ${formatCheckAge(secondsSinceUpdate)}` : 'no successful check yet'}`
    : isRefreshing ? hasSuccessfulRefresh ? `Checking scores… · last checked ${formatCheckAge(secondsSinceUpdate)}` : 'Checking scores…'
      : hasSuccessfulRefresh ? `Checked ${formatCheckAge(secondsSinceUpdate)}` : 'Checking scores…';

  return <div className={styles.page}>
    <header className={styles.siteHeader}><span className={styles.brand}>GAME<span>/</span>EXPLAINED</span></header>
    <main className={styles.record}>
      <div className={styles.crumb}><span>Games / {scoreboard.week.label}</span><span>{sortedGames.length} games{activeCount > 0 ? ` · ${activeCount} live` : ''}</span></div>
      <section className={styles.intro}>
        <div><span className={styles.kicker}>NFL games</span><h1>{scoreboard.week.label}</h1></div>
        <div className={styles.weekControl}><label htmlFor="directory-week">Choose week</label><WeekPicker currentWeek={currentWeek} onWeekChange={handleWeekChange} id="directory-week" /></div>
      </section>
      <div className={styles.listHead}><strong>{activeCount ? 'Live and scheduled games' : 'Games'}</strong><span>{hasUnfinishedGames ? `Scores checked automatically · ${scoreCheckStatus}` : 'Scores and status from ESPN'}</span></div>
      {refreshError && <div className={styles.refreshError} role="status">Could not refresh scores. Showing the last loaded results and retrying automatically. <button onClick={refresh}>Try again</button></div>}
      <div className={styles.list}>{sortedGames.length ? sortedGames.map(game => <div key={game.gameId} className={changedGameIds.has(game.gameId) ? styles.changed : ''}><GameCard game={game} week={currentWeek} /></div>)
        : <div className={styles.empty}>No games are listed for this week. Choose another week above.</div>}</div>
      <footer className={styles.footer}>Data: ESPN</footer>
    </main>
  </div>;
}
