import React, { useEffect } from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WeekProvider, useWeekContext } from '@/contexts/WeekContext';
import { GameSidebarClient } from './GameSidebarClient';
import type { WeekSelection } from '@/types';

let searchParamsString = '';

vi.mock('next/navigation', async () => {
  const actual = await vi.importActual<typeof import('next/navigation')>('next/navigation');
  return {
    ...actual,
    useSearchParams: () => new URLSearchParams(searchParamsString),
  };
});

vi.mock('./GameSidebar', () => ({
  GameSidebar: () => <div data-testid="sidebar" />,
}));

function SetWeekAfterMount({ delayMs, week }: { delayMs: number; week: WeekSelection }) {
  const { setGameWeek } = useWeekContext();

  useEffect(() => {
    const timeout = setTimeout(() => {
      setGameWeek(week);
    }, delayMs);
    return () => clearTimeout(timeout);
  }, [delayMs, setGameWeek, week]);

  return null;
}

describe('GameSidebarClient', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    searchParamsString = '';
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('fetches the scoreboard for the week in the URL', async () => {
    searchParamsString = 'week=15&seasontype=2';

    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        week: { number: 15, label: 'Week 15', seasonType: 2 },
        games: [],
      }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    render(
      <WeekProvider>
        <GameSidebarClient />
      </WeekProvider>
    );

    await vi.advanceTimersByTimeAsync(120);

    expect(fetchMock).toHaveBeenCalledWith('/api/scoreboard?seasontype=2&week=15', { cache: 'no-store' });
  });

  it('syncs to the game week from context even when polling stops', async () => {
    searchParamsString = '';

    const fetchMock = vi.fn(async (url: string) => {
      const isWeek15 = url.includes('week=15');
      return {
        ok: true,
        json: async () => ({
          week: { number: isWeek15 ? 15 : 16, label: isWeek15 ? 'Week 15' : 'Week 16', seasonType: 2 },
          games: [],
        }),
      };
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <WeekProvider>
        <SetWeekAfterMount delayMs={200} week={{ weekNumber: 15, seasonType: 2 }} />
        <GameSidebarClient />
      </WeekProvider>
    );

    await vi.advanceTimersByTimeAsync(120);
    expect(fetchMock).toHaveBeenCalledWith('/api/scoreboard', { cache: 'no-store' });

    await vi.advanceTimersByTimeAsync(120);
    expect(fetchMock).toHaveBeenCalledWith('/api/scoreboard?seasontype=2&week=15', { cache: 'no-store' });
  });

  it('keeps refreshing pregame rows so the sidebar changes at kickoff', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        week: { number: 4, label: 'Week 4', seasonType: 2 },
        games: [{ gameId: '1', status: 'pregame', isActive: false }],
      }),
    }));
    vi.stubGlobal('fetch', fetchMock);

    render(<WeekProvider><GameSidebarClient /></WeekProvider>);
    await vi.advanceTimersByTimeAsync(120);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(60000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('shows a retry state when the first scoreboard request fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline'); }));
    render(<WeekProvider><GameSidebarClient /></WeekProvider>);
    await vi.advanceTimersByTimeAsync(120);
    expect(screen.getByRole('status', { name: 'Games unavailable' })).toHaveTextContent('Games could not be loaded.');
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });
});
