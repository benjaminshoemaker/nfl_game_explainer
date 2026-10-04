import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DirectoryClient } from './DirectoryClient';
import type { ScoreboardResponse } from '@/types';

const { refreshOptions, refreshState } = vi.hoisted(() => ({ refreshOptions: vi.fn(), refreshState: { error: null as Error | null, hasSuccessfulRefresh: false, secondsSinceUpdate: 0 } }));
vi.mock('@/hooks/useAutoRefresh', () => ({
  useAutoRefresh: (options: unknown) => {
    refreshOptions(options);
    return { isRefreshing: false, secondsSinceUpdate: refreshState.secondsSinceUpdate, hasSuccessfulRefresh: refreshState.hasSuccessfulRefresh, error: refreshState.error, refresh: vi.fn() };
  },
}));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
vi.mock('@/components/GameCard', () => ({ GameCard: () => <div>Game row</div> }));

const scoreboard: ScoreboardResponse = {
  week: { number: 4, label: 'Week 4', seasonType: 2 },
  games: [{
    gameId: 'game-1', status: 'pregame', statusDetail: 'Tomorrow', startTime: '2026-10-04T17:00Z', isActive: false,
    awayTeam: { id: '1', abbr: 'AWY', name: 'Away', logo: '', score: 0 },
    homeTeam: { id: '2', abbr: 'HOM', name: 'Home', logo: '', score: 0 },
  }],
};

describe('DirectoryClient refresh', () => {
  beforeEach(() => { refreshOptions.mockClear(); refreshState.error = null; refreshState.hasSuccessfulRefresh = false; refreshState.secondsSinceUpdate = 0; });

  it('identifies stale scores after a refresh error', () => {
    refreshState.error = new Error('offline');
    render(<DirectoryClient initialData={scoreboard} />);
    expect(screen.getByRole('status')).toHaveTextContent('Could not refresh scores. Showing the last loaded results and retrying automatically.');
    expect(screen.getByText('Game row')).toBeInTheDocument();
  });

  it('checks for kickoff while every game is still pregame', () => {
    render(<DirectoryClient initialData={scoreboard} />);
    expect(screen.getByText(/Scores checked automatically · Checking scores/)).toBeInTheDocument();
    expect(refreshOptions).toHaveBeenLastCalledWith(expect.objectContaining({ enabled: true, interval: 60000 }));
  });

  it('shows the last successful check time during a later outage', () => {
    refreshState.error = new Error('offline');
    refreshState.hasSuccessfulRefresh = true;
    refreshState.secondsSinceUpdate = 125;
    render(<DirectoryClient initialData={scoreboard} />);
    expect(screen.getByText(/Updates interrupted · last successful check 2m ago/)).toBeInTheDocument();
  });

  it('stops polling when all games are final', () => {
    render(<DirectoryClient initialData={{ ...scoreboard, games: [{ ...scoreboard.games[0], status: 'final' }] }} />);
    expect(refreshOptions).toHaveBeenLastCalledWith(expect.objectContaining({ enabled: false }));
  });

  it('keeps week selection available when no games are listed', () => {
    render(<DirectoryClient initialData={{ ...scoreboard, games: [] }} />);
    expect(screen.getByLabelText('Choose week')).toBeInTheDocument();
    expect(screen.getByText('No games are listed for this week. Choose another week above.')).toBeInTheDocument();
  });
});
