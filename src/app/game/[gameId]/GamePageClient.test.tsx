import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
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
vi.mock('@/components/DebugGamePicker', () => ({ DebugGamePicker: () => <select aria-label="Game" /> }));

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
  it('warns when final-game totals or offensive-play counts differ', () => {
    render(
      <WeekProvider>
        <GamePageClient initialGameData={buildGame({
          status: 'final',
          source_gaps: [
            { team: 'AWY', yards_gap: 34, turnovers_gap: 0 },
            { team: 'HOM', yards_gap: 0, turnovers_gap: 0, plays_gap: 5 },
          ],
        })} />
      </WeekProvider>
    );
    expect(screen.getByRole('status')).toHaveTextContent('ESPN box-score totals or offensive-play counts differ from available play-by-play for AWY, HOM');
  });

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

  it('does not offer a competitive view when win probabilities are unavailable', () => {
    render(
      <WeekProvider>
        <GamePageClient initialGameData={buildGame({
          wp_filter: {
            enabled: false,
            threshold: 0.975,
            description: 'Win probability unavailable; showing full-game totals',
          },
        })} />
      </WeekProvider>
    );
    expect(screen.queryByTestId('view-toggle')).toBeNull();
    expect(screen.getByText('Win probability unavailable; showing full-game totals')).toBeInTheDocument();
  });

  it('shows calculated tables, play contributions, and source data in debug mode', () => {
    const game = buildGame({
      advanced_table: [{ Team: 'AWY', Score: 0, Turnovers: 0, 'Total Yards': 5,
        'Adjusted Yards Per Play': 5, 'Success Rate': 1, 'Explosive Plays': 0,
        'Explosive Play Rate': 0, 'Points Per Trip (Inside 40)': 0,
        'Ave Start Field Pos': 'Own 25', 'Penalty Yards': 0, 'Non-Offensive Points': 0 }],
      debug: {
        statsCompetitive: [{ Team: 'AWY', 'Success Rate': 1 }],
        statsFull: [{ Team: 'AWY', 'Success Rate': 1 }],
        plays: [{ kind: 'play', drive: 1, playId: '10', team: 'AWY',
          quarter: 1, clock: '14:51', down: 1, distance: 10, sourceYards: 5,
          startHomeWP: 0.5413, endHomeWP: 0.5326,
          text: 'Run up the middle', classification: 'run', competitive: true,
          statDeltas: { AWY: { 'Offensive Yards': 5, 'Successful Plays': 1, 'Explosive Plays': 1 } },
          raw: { id: '10', start: { possessionText: 'GB 17' }, end: { possessionText: 'GB 22' } } }],
        sources: { espnSummary: { header: { id: '401' } }, playProbabilities: {},
          pregameProbabilities: { home: 0.5, away: 0.5 } },
      },
    });

    render(
      <WeekProvider>
        <GamePageClient initialGameData={game} debugMode />
      </WeekProvider>
    );

    expect(screen.getByText('Calculated stats — competitive plays')).toBeInTheDocument();
    expect(screen.getByText('Calculated stats — full game')).toBeInTheDocument();
    expect(screen.getByText('Full ESPN game payload')).toBeInTheDocument();
    const statsTable = screen.getByRole('table', { name: 'Calculated stats — competitive plays' });
    expect(within(statsTable).getAllByRole('columnheader')).toHaveLength(2);
    expect(within(statsTable).getByRole('row', { name: 'Success Rate 1' })).toBeInTheDocument();
    const playsTable = screen.getByRole('table', { name: 'Source plays and calculated contributions' });
    expect(playsTable).toHaveTextContent('AWY Offensive Yards: +5');
    expect(within(playsTable).getAllByRole('columnheader')).toHaveLength(14);
    expect(within(playsTable).getByText('1 & 10')).toBeInTheDocument();
    expect(within(playsTable).getByText('GB 17')).toBeInTheDocument();
    expect(within(playsTable).getByText('GB 22')).toBeInTheDocument();
    expect(within(playsTable).getByText('54.13%')).toBeInTheDocument();
    expect(within(playsTable).getByText('53.26%')).toBeInTheDocument();
    expect(within(playsTable).getByText('-0.87 pp')).toBeInTheDocument();
    expect(within(playsTable).getAllByText('Yes')).toHaveLength(2);
    expect(screen.queryByTestId('advanced-stats')).toBeNull();
  });
});
