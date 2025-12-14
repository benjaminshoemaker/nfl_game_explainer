'use client';

import { useState } from 'react';
import { GameResponse } from '@/types';
import { Scoreboard } from '@/components/Scoreboard';
import { AdvancedStats } from '@/components/AdvancedStats';
import { AISummary } from '@/components/AISummary';
import { GamePlays } from '@/components/GamePlays';
import { ViewToggle } from '@/components/ViewToggle';

interface GamePageClientProps {
  gameData: GameResponse;
}

type ViewMode = 'competitive' | 'full';

export function GamePageClient({ gameData }: GamePageClientProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('competitive');

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

  const expandedDetails = viewMode === 'competitive'
    ? gameData.expanded_details
    : gameData.expanded_details_full;

  // Parse status detail from label
  const statusDetail = gameData.status === 'final'
    ? 'Final'
    : gameData.status === 'pregame'
    ? 'Pregame'
    : 'In Progress';

  return (
    <div className="min-h-screen bg-bg-deep">
      {/* Main content */}
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {/* Scoreboard */}
        <Scoreboard
          homeTeam={homeTeam}
          awayTeam={awayTeam}
          status={gameData.status}
          statusDetail={statusDetail}
        />

        {/* AI Summary */}
        <AISummary
          summary={gameData.ai_summary || null}
          isLoading={false}
        />

        {/* Advanced Stats with View Toggle */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-xl tracking-wide text-text-primary">
              Game Stats
            </h2>
            <ViewToggle
              value={viewMode}
              onChange={setViewMode}
              showIndicator={false}
            />
          </div>

          {/* Filter indicator when in competitive mode */}
          {viewMode === 'competitive' && gameData.wp_filter.enabled && (
            <p className="font-condensed text-xs text-text-muted">
              {gameData.wp_filter.description}
            </p>
          )}

          <AdvancedStats
            stats={advancedStats}
            teamMeta={gameData.team_meta}
          />
        </div>

        {/* Plays */}
        <GamePlays
          expandedDetails={expandedDetails}
          teamMeta={gameData.team_meta}
        />

        {/* Text Analysis (fallback if no AI summary) */}
        {!gameData.ai_summary && gameData.analysis && (
          <div className="bg-bg-card rounded-2xl border border-border-subtle p-5">
            <h3 className="font-display text-lg tracking-wide text-text-primary mb-3">
              Game Analysis
            </h3>
            <p className="font-body text-sm text-text-secondary whitespace-pre-wrap leading-relaxed">
              {gameData.analysis}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
