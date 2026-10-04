import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { WeekProvider } from '@/contexts/WeekContext';
import { GamePageClient } from './GamePageClient';
import type { CanonicalPlay, GameResponse } from '@/types';

const { refreshOptions, refreshState } = vi.hoisted(() => ({ refreshOptions: vi.fn(), refreshState: { error: null as Error | null, hasSuccessfulRefresh: false } }));
vi.mock('@/hooks/useAutoRefresh', () => ({
  useAutoRefresh: (options: unknown) => {
    refreshOptions(options);
    return { isRefreshing: false, secondsSinceUpdate: 0, hasSuccessfulRefresh: refreshState.hasSuccessfulRefresh, error: refreshState.error, refresh: vi.fn() };
  },
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
  beforeEach(() => { refreshOptions.mockClear(); refreshState.error = null; refreshState.hasSuccessfulRefresh = false; });

  it('shows the new game after client navigation', () => {
    const first = buildGame({ gameId: 'one' });
    const second = buildGame({ gameId: 'two', team_meta: [
      { id: '3', abbr: 'NEW', name: 'New Away', homeAway: 'away' },
      { id: '4', abbr: 'OPP', name: 'New Home', homeAway: 'home' },
    ] });
    const { rerender } = render(<WeekProvider><GamePageClient initialGameData={first} /></WeekProvider>);
    rerender(<WeekProvider><GamePageClient initialGameData={second} /></WeekProvider>);
    expect(screen.getByRole('heading', { name: 'New Away at New Home' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Away at Home' })).toBeNull();
  });

  it('marks a failed refresh as stale without clearing the game', () => {
    refreshState.error = new Error('network offline');
    render(<WeekProvider><GamePageClient initialGameData={buildGame({ status: 'in-progress' })} /></WeekProvider>);
    expect(screen.getByRole('status')).toHaveTextContent('Could not refresh this game. Showing the last loaded report and retrying automatically.');
    expect(screen.getByRole('heading', { name: 'Away at Home' })).toBeInTheDocument();
  });

  it.each([
    ['delayed', 'Weather Delay', 'ESPN reports a delay'],
    ['postponed', 'Postponed', 'ESPN reports that this game has been postponed'],
    ['canceled', 'Canceled', 'ESPN reports that this game has been canceled'],
  ] as const)('explains %s games without plays', (status, statusDetail, message) => {
    render(<WeekProvider><GamePageClient initialGameData={buildGame({ status, statusDetail })} /></WeekProvider>);
    expect(screen.getByText(new RegExp(message))).toBeInTheDocument();
    expect(screen.queryByText('Explore all eight factors')).toBeNull();
  });

  it('calls halftime by its ESPN status detail', () => {
    render(<WeekProvider><GamePageClient initialGameData={buildGame({ status: 'in-progress', statusDetail: 'Halftime' })} /></WeekProvider>);
    expect(screen.getAllByText(/Halftime/).length).toBeGreaterThan(0);
  });

  it('separates check age from the latest play and notes an unchanged poll', () => {
    const play: CanonicalPlay = {
      id: 'first', sourceTeamId: '1', sourceTeam: 'AWY', quarter: 3, clock: '8:42',
      type: 'Rush', text: 'Rush for four yards.', down: 1, distance: 10,
      ballBefore: 'AWY 25', scoreBefore: { home: 0, away: 0 }, scoreAfter: { home: 0, away: 0 },
      homeWpBefore: .5, homeWpAfter: .51, homeWpDelta: .01, epa: null,
      penalty: null, scoreChange: null,
    };
    const initial = buildGame({ status: 'in-progress', statusDetail: 'Halftime', plays: [play] });
    render(<WeekProvider><GamePageClient initialGameData={initial} /></WeekProvider>);
    expect(screen.getByText(/Checking for updates/)).toBeInTheDocument();
    expect(screen.getByText('Latest play: Q3 8:42')).toBeInTheDocument();
    act(() => { refreshOptions.mock.lastCall?.[0].onSuccess(initial); });
    expect(screen.getByText('No new plays since last check')).toBeInTheDocument();
    act(() => { refreshOptions.mock.lastCall?.[0].onSuccess({ ...initial, plays: [...initial.plays!, { ...play, id: 'next', clock: '8:20' }] }); });
    expect(screen.getByText('Latest play: Q3 8:20')).toBeInTheDocument();
    expect(screen.queryByText('No new plays since last check')).toBeNull();
  });

  it('moves from pregame to early live play to final without a reload', () => {
    const play = {
      id: 'kickoff', sourceTeamId: '1', sourceTeam: 'AWY', quarter: 1, clock: '15:00',
      type: 'Kickoff', text: 'Opening kickoff.', down: null, distance: null,
      ballBefore: 'AWY 35', scoreBefore: { home: 0, away: 0 }, scoreAfter: { home: 0, away: 0 },
      homeWpBefore: null, homeWpAfter: null, homeWpDelta: null, epa: null,
      penalty: null, scoreChange: null,
    };
    render(<WeekProvider><GamePageClient initialGameData={buildGame({ status: 'pregame' })} /></WeekProvider>);
    expect(screen.getByText('Upcoming game')).toBeInTheDocument();
    act(() => {
      refreshOptions.mock.lastCall?.[0].onSuccess(buildGame({ status: 'in-progress', statusDetail: 'Q1 15:00', plays: [play] }));
    });
    expect(screen.getByText(/Early game: 1 classified play available/)).toBeInTheDocument();
    expect(document.querySelector('[data-play-id="kickoff"]')).toBeInTheDocument();
    act(() => {
      refreshOptions.mock.lastCall?.[0].onSuccess(buildGame({ status: 'final', statusDetail: 'Final', plays: [play] }));
    });
    expect(refreshOptions).toHaveBeenLastCalledWith(expect.objectContaining({ enabled: false }));
    expect(screen.getByText('Final')).toBeInTheDocument();
  });

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
    expect(screen.getByText(/Analysis and play-by-play will appear/)).toBeInTheDocument();
    expect(screen.queryByText('Explore all eight factors')).toBeNull();
    expect(refreshOptions).toHaveBeenLastCalledWith(expect.objectContaining({ enabled: true }));
  });

  it('shows a waiting state when ESPN marks a game live before publishing plays', () => {
    render(<WeekProvider><GamePageClient initialGameData={buildGame({
      status: 'in-progress', ai_summary: 'A late defensive score changed the game.',
    })} /></WeekProvider>);
    expect(screen.getByText(/ESPN marks the game as live, but no plays are available yet/)).toBeInTheDocument();
    expect(screen.queryByText('Explore all eight factors')).toBeNull();
  });

  it('uses the same source card in factor evidence and all plays', () => {
    const play = {
      id: 'p1', sourceTeamId: '1', sourceTeam: 'AWY', quarter: 4, clock: '3:57',
      type: 'Interception', text: 'Pass intercepted and returned for a touchdown.',
      down: 3, distance: 8, ballBefore: 'AWY 40',
      scoreBefore: { home: 10, away: 17 }, scoreAfter: { home: 16, away: 17 },
      homeWpBefore: .31, homeWpAfter: .57, homeWpDelta: .26, epa: null,
      penalty: null, scoreChange: { team: 'HOM', points: 6, non_offensive: true },
    };
    const game = buildGame({ status: 'final', plays: [play],
      expanded_details: { '1': { Turnovers: [{ source_play_id: 'p1', type: 'Interception', text: play.text }] } },
    });
    render(<WeekProvider><GamePageClient initialGameData={game} /></WeekProvider>);
    fireEvent.click(within(screen.getByRole('region', { name: 'All game factors' })).getByRole('button', { name: /Turnovers/ }));
    const cards = document.querySelectorAll('[data-play-id="p1"]');
    expect(cards).toHaveLength(2);
    expect(cards[0].textContent).toBe(cards[1].textContent);
    expect(cards[0]).toHaveTextContent('3rd and 8 from the AWY 40');
    expect(cards[0]).toHaveTextContent('Score AWY 17 · HOM 10');
    expect(cards[0]).toHaveTextContent('Defensive pointsHOM +6');
    expect(cards[0]).toHaveTextContent('HOM +26.0 pp');
    expect(cards[0]).toHaveTextContent('31.0% → 57.0%');
  });

  it('keeps small WP changes visible without before-and-after percentages', () => {
    const game = buildGame({ plays: [{
      id: 'small', sourceTeamId: '1', sourceTeam: 'AWY', quarter: 1, clock: '10:00',
      type: 'Rush', text: 'Runner gained 4 yards.', down: 1, distance: 10,
      ballBefore: 'AWY 25', scoreBefore: { home: 0, away: 0 }, scoreAfter: { home: 0, away: 0 },
      homeWpBefore: .775, homeWpAfter: .786, homeWpDelta: .011, epa: null,
      penalty: null, scoreChange: null,
    }] });
    render(<WeekProvider><GamePageClient initialGameData={game} /></WeekProvider>);
    const card = document.querySelector('[data-play-id="small"]');
    expect(card).toHaveTextContent('HOM +1.1 pp');
    expect(card).not.toHaveTextContent('77.5% → 78.6%');
  });

  it('renders an impactful event identically in the impact list and all plays', () => {
    const plays = Array.from({ length: 20 }, (_, index) => ({
      id: `play-${index}`, sourceTeamId: '1', sourceTeam: 'AWY', quarter: 1, clock: '10:00',
      type: 'Rush', text: `Runner gained ${index} yards.`, down: 1, distance: 10,
      ballBefore: 'AWY 25', scoreBefore: { home: 0, away: 0 }, scoreAfter: { home: 0, away: 0 },
      homeWpBefore: .5, homeWpAfter: index === 0 ? .75 : index < 3 ? .56 : .51,
      homeWpDelta: index === 0 ? .25 : index < 3 ? .06 : .01,
      epa: null, penalty: null, scoreChange: null,
    }));
    render(<WeekProvider><GamePageClient initialGameData={buildGame({ plays })} /></WeekProvider>);
    const copies = document.querySelectorAll('[data-play-id="play-0"]');
    expect(copies).toHaveLength(2);
    expect(copies[0].textContent).toBe(copies[1].textContent);
  });

  it('explains a delayed ESPN WP update and leaves it out of the impact ranking', () => {
    const uncertain: CanonicalPlay = {
      id: 'kickoff', sourceTeamId: '1', sourceTeam: 'AWY', quarter: 4, clock: '1:42',
      type: 'Kickoff', text: 'Kickoff following a score.', down: null, distance: null,
      ballBefore: 'AWY 35', scoreBefore: { home: 24, away: 24 }, scoreAfter: { home: 24, away: 24 },
      homeWpBefore: .78, homeWpAfter: .6, homeWpDelta: -.18, wpAttributionUncertain: true,
      epa: null, penalty: null, scoreChange: null,
    };
    render(<WeekProvider><GamePageClient initialGameData={buildGame({ status: 'final', plays: [uncertain] })} /></WeekProvider>);
    expect(screen.getByText(/this change may include that update/)).toBeInTheDocument();
    expect(document.querySelectorAll('[data-play-id="kickoff"]')).toHaveLength(1);
  });

  it('does not offer a competitive view when win probabilities are unavailable', () => {
    render(
      <WeekProvider>
        <GamePageClient initialGameData={buildGame({
          status: 'final',
          wp_filter: {
            enabled: false,
            threshold: 0.975,
            description: 'Win probability unavailable; showing full-game totals',
          },
        })} />
      </WeekProvider>
    );
    expect(screen.queryByRole('group', { name: 'Stat scope' })).toBeNull();
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
    expect(screen.queryByText('Explore all eight factors')).toBeNull();
  });
});
