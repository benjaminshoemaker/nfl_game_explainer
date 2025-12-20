import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WeekProvider } from '@/contexts/WeekContext';
import { GamePageClient } from './GamePageClient';
import type { GameResponse } from '@/types';

vi.mock('@/hooks/useAutoRefresh', () => ({
  useAutoRefresh: () => ({ isRefreshing: false, secondsSinceUpdate: 0 }),
}));

vi.mock('@/components/Scoreboard', () => ({ Scoreboard: () => <div data-testid="scoreboard" /> }));
vi.mock('@/components/AdvancedStats', () => ({ AdvancedStats: () => <div data-testid="advanced-stats" /> }));
vi.mock('@/components/GamePlays', () => ({ GamePlays: () => <div data-testid="game-plays" /> }));
vi.mock('@/components/ViewToggle', () => ({ ViewToggle: () => <div data-testid="view-toggle" /> }));
vi.mock('@/components/UpdateIndicator', () => ({ UpdateIndicator: () => <div data-testid="update-indicator" /> }));
vi.mock('@/components/AISummary', () => ({ AISummary: () => <div data-testid="ai-summary" /> }));

function buildGame(overrides: Partial<GameResponse>): GameResponse {
  return {
    gameId: '401',
    label: 'AWY_at_HOM_401',
    status: 'pregame',
    team_meta: [
      { id: '1', abbr: 'AWY', name: 'Away', homeAway: 'away' },
      { id: '2', abbr: 'HOM', name: 'Home', homeAway: 'home' },
    ],
    summary_table: [
      { Team: 'AWY', Score: 0, 'Total Yards': 0, Drives: 0 },
      { Team: 'HOM', Score: 0, 'Total Yards': 0, Drives: 0 },
    ],
    summary_table_full: [
      { Team: 'AWY', Score: 0, 'Total Yards': 0, Drives: 0 },
      { Team: 'HOM', Score: 0, 'Total Yards': 0, Drives: 0 },
    ],
    advanced_table: [],
    advanced_table_full: [],
    expanded_details: {},
    expanded_details_full: {},
    wp_filter: { enabled: true, threshold: 0.975, description: 'x' },
    analysis: '',
    ...overrides,
  };
}

describe('GamePageClient', () => {
  it('hides AI summary before the game begins', () => {
    render(
      <WeekProvider>
        <GamePageClient initialGameData={buildGame({ status: 'pregame' })} />
      </WeekProvider>
    );
    expect(screen.queryByTestId('ai-summary')).toBeNull();
  });

  it('shows AI summary after kickoff', () => {
    render(
      <WeekProvider>
        <GamePageClient initialGameData={buildGame({ status: 'in-progress' })} />
      </WeekProvider>
    );
    expect(screen.getByTestId('ai-summary')).toBeInTheDocument();
  });
});
