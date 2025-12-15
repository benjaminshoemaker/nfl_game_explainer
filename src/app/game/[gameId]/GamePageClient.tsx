'use client';

import { useState, useCallback } from 'react';
import { GameResponse } from '@/types';
import { Scoreboard } from '@/components/Scoreboard';
import { AdvancedStats } from '@/components/AdvancedStats';
import { AISummary } from '@/components/AISummary';
import { GamePlays } from '@/components/GamePlays';
import { ViewToggle } from '@/components/ViewToggle';
import { UpdateIndicator } from '@/components/UpdateIndicator';
import { useAutoRefresh } from '@/hooks/useAutoRefresh';

interface GamePageClientProps {
  initialGameData: GameResponse;
}

type ViewMode = 'competitive' | 'full';

const REFRESH_INTERVAL = 60000; // 60 seconds

export function GamePageClient({ initialGameData }: GamePageClientProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('competitive');
  const [gameData, setGameData] = useState<GameResponse>(initialGameData);
  const [selectedCategory, setSelectedCategory] = useState<string>('Explosive Plays');

  const isLive = gameData.status === 'in-progress';

  const fetchGameData = useCallback(async (): Promise<GameResponse> => {
    const response = await fetch(`/api/game/${gameData.gameId}`);
    if (!response.ok) {
      throw new Error('Failed to fetch game data');
    }
    return response.json();
  }, [gameData.gameId]);

  const { isRefreshing, secondsSinceUpdate } = useAutoRefresh({
    fetchFn: fetchGameData,
    interval: REFRESH_INTERVAL,
    enabled: isLive,
    onSuccess: (data) => setGameData(data),
  });

  // Get home and away teams from team_meta
  const awayMeta = gameData.team_meta.find((t) => t.homeAway === 'away');
  const homeMeta = gameData.team_meta.find((t) => t.homeAway === 'home');

  if (!awayMeta || !homeMeta) {
    return (
      <div className="p-8 text-center text-text-muted">
        Unable to load game data
      </div>
    );
  }

  // Get scores from summary table
  const awayStats = gameData.summary_table.find((s) => s.Team === awayMeta.abbr);
  const homeStats = gameData.summary_table.find((s) => s.Team === homeMeta.abbr);

  const homeTeam = {
    abbr: homeMeta.abbr,
    name: homeMeta.name,
    score: homeStats?.Score ?? 0,
    logo: `https://a.espncdn.com/i/teamlogos/nfl/500/${homeMeta.abbr.toLowerCase()}.png`,
    id: homeMeta.id,
  };

  const awayTeam = {
    abbr: awayMeta.abbr,
    name: awayMeta.name,
    score: awayStats?.Score ?? 0,
    logo: `https://a.espncdn.com/i/teamlogos/nfl/500/${awayMeta.abbr.toLowerCase()}.png`,
    id: awayMeta.id,
  };

  // Get the appropriate data based on view mode
  const advancedStats = viewMode === 'competitive'
    ? gameData.advanced_table
    : gameData.advanced_table_full;

  const rawExpandedDetails = viewMode === 'competitive'
    ? gameData.expanded_details
    : gameData.expanded_details_full;

  // Transform expanded_details from {teamId: {category: plays[]}}
  // to {category: {teamId: plays[]}} format expected by GamePlays
  const expandedDetails = (() => {
    const transformed: Record<string, Record<string, typeof rawExpandedDetails[string][string]>> = {};
    for (const [teamId, categories] of Object.entries(rawExpandedDetails || {})) {
      for (const [category, plays] of Object.entries(categories || {})) {
        if (!transformed[category]) {
          transformed[category] = {};
        }
        transformed[category][teamId] = plays;
      }
    }
    return transformed;
  })();

  // Parse status detail from gameClock or fallback
  const statusDetail = (() => {
    if (gameData.status === 'final') return 'Final';
    if (gameData.status === 'pregame') return 'Pregame';

    // For in-progress games, show quarter and time
    if (gameData.gameClock) {
      const { quarter, clock } = gameData.gameClock;
      if (quarter <= 4) {
        return `Q${quarter} ${clock}`;
      }
      return `OT ${clock}`;
    }
    return 'In Progress';
  })();

  // Handle stat row click to sync with GamePlays
  const handleStatClick = (category: string) => {
    setSelectedCategory(category);
    // Scroll to plays section
    const playsSection = document.getElementById('plays-section');
    if (playsSection) {
      playsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="min-h-screen bg-bg-deep">
      {/* Main content */}
      <div className="max-w-5xl mx-auto px-4 py-4 space-y-4">
        {/* Live Update Indicator */}
        <UpdateIndicator
          isLive={isLive}
          isRefreshing={isRefreshing}
          secondsSinceUpdate={secondsSinceUpdate}
          lastPlayTime={gameData.lastPlayTime}
        />

        {/* Scoreboard */}
        <div className="animate-fade-in-up">
          <Scoreboard
            homeTeam={homeTeam}
            awayTeam={awayTeam}
            status={gameData.status}
            statusDetail={statusDetail}
          />
        </div>

        {/* AI Summary (falls back to analysis if no AI summary) */}
        <div className="animate-fade-in-up delay-1">
          <AISummary
            summary={gameData.ai_summary || gameData.analysis || null}
            isLoading={false}
          />
        </div>

        {/* View Toggle Bar */}
        <div className="animate-fade-in-up delay-2 flex items-center justify-between gap-4 bg-bg-card border border-border-subtle rounded-xl px-5 py-3">
          <div className="flex items-center gap-2">
            <span
              className="w-2 h-2 rounded-full bg-positive flex-shrink-0"
              style={{ boxShadow: '0 0 8px var(--positive)' }}
            />
            <span className="font-condensed text-xs text-text-secondary tracking-wide">
              {viewMode === 'competitive'
                ? (gameData.wp_filter?.description || 'Stats reflect competitive plays only (WP < 97.5%)')
                : 'Showing full-game totals (no WP filter)'}
            </span>
          </div>
          <ViewToggle
            value={viewMode}
            onChange={setViewMode}
            showIndicator={false}
          />
        </div>

        {/* Advanced Stats */}
        <div className="animate-fade-in-up delay-3">
          <AdvancedStats
            stats={advancedStats}
            teamMeta={gameData.team_meta}
            onStatClick={handleStatClick}
            selectedCategory={selectedCategory}
          />
        </div>

        {/* Key Plays */}
        <div id="plays-section" className="animate-fade-in-up delay-4">
          <GamePlays
            expandedDetails={expandedDetails}
            teamMeta={gameData.team_meta}
            selectedCategory={selectedCategory}
          />
        </div>
      </div>
    </div>
  );
}
