import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { CanonicalPlay, GameResponse, TeamMeta } from '@/types';
import { GameExplorer } from './GameExplorer';

const away: TeamMeta = { id: '1', abbr: 'AWY', name: 'Away', homeAway: 'away' };
const home: TeamMeta = { id: '2', abbr: 'HOM', name: 'Home', homeAway: 'home' };
const plays: CanonicalPlay[] = ['first', 'second', 'latest'].map((id, index) => ({
  id, sourceTeamId: away.id, sourceTeam: away.abbr, quarter: 1, clock: `${15 - index}:00`,
  type: 'Rush', text: `${id} play`, down: 1, distance: 10, ballBefore: 'AWY 25',
  scoreBefore: { home: 0, away: 0 }, scoreAfter: { home: 0, away: 0 },
  homeWpBefore: .5, homeWpAfter: .5, homeWpDelta: 0, epa: null,
  penalty: null, scoreChange: null,
}));
const game = {
  gameId: '401', label: 'AWY_at_HOM_401', status: 'in-progress', statusDetail: 'Halftime',
  week: { number: 4, seasonType: 2 }, team_meta: [away, home],
  summary_table: [], summary_table_full: [], advanced_table: [], advanced_table_full: [],
  expanded_details: {}, expanded_details_full: {}, plays,
  wp_filter: { enabled: false, threshold: .975, description: 'Win probability unavailable' },
  analysis: '',
} as GameResponse;

describe('live game play order', () => {
  it('puts the latest play first and offers oldest first', () => {
    const { container } = render(<GameExplorer game={game} scope="full" away={away} home={home} />);
    const listedIds = () => [...container.querySelectorAll('[data-play-id]')].map(node => node.getAttribute('data-play-id'));
    expect(listedIds()).toEqual(['latest', 'second', 'first']);
    expect(screen.getByLabelText('Sort')).toHaveValue('game');
    expect(screen.getByText('Week 4')).toBeInTheDocument();
    expect(screen.getAllByText('May appear after the next play.')).toHaveLength(1);
    fireEvent.change(screen.getByLabelText('Sort'), { target: { value: 'oldest' } });
    expect(listedIds()).toEqual(['first', 'second', 'latest']);
  });

  it('shows unavailable rates when no eligible offensive plays have arrived', () => {
    render(<GameExplorer game={{ ...game, plays: plays.slice(0, 1) }} scope="full" away={away} home={home} />);
    expect([...screen.getByRole('tab', { name: /Success rate/ }).querySelectorAll('b')].map(node => node.textContent)).toEqual(['—', '—']);
    expect([...screen.getByRole('tab', { name: /Points per trip/ }).querySelectorAll('b')].map(node => node.textContent)).toEqual(['—', '—']);
    expect(screen.getByText(/Factor comparisons are preliminary/)).toBeInTheDocument();
  });

  it('shows factor leaders and known penalty yards without declaring an unresolved category won', () => {
    const withFactors = {
      ...game,
      advanced_table: [
        { Team: away.abbr, Score: 0, Turnovers: 2, 'Total Yards': 0,
          'Adjusted Yards Per Play': 4, 'Success Rate': .5, 'Explosive Plays': 0,
          'Explosive Play Rate': 0, 'Points Per Trip (Inside 40)': 0,
          'Ave Start Field Pos': 'Own 25', 'Penalty Yards': 100, 'Non-Offensive Points': 0 },
        { Team: home.abbr, Score: 0, Turnovers: 0, 'Total Yards': 0,
          'Adjusted Yards Per Play': 4, 'Success Rate': .4, 'Explosive Plays': 0,
          'Explosive Play Rate': 0, 'Points Per Trip (Inside 40)': 0,
          'Ave Start Field Pos': 'Own 25', 'Penalty Yards': 58, 'Non-Offensive Points': 0 },
      ],
      expanded_details: {
        [away.id]: { 'Offensive Plays': Array.from({ length: 20 }, () => ({ type: 'Rush', text: 'run', yards: 5 })) },
        [home.id]: {
          'Offensive Plays': Array.from({ length: 20 }, () => ({ type: 'Rush', text: 'run', yards: 4 })),
          'Penalty Yards': [{ type: 'Penalty', text: 'missing yards', yards: null, penalty_status: 'accepted' }],
        },
      },
    } as GameResponse;
    const { rerender } = render(<GameExplorer game={withFactors} scope="competitive" away={away} home={home} />);
    expect(screen.getByLabelText('Factor wins')).toHaveTextContent('AWY 1 · HOM 1');
    expect(screen.getByRole('tab', { name: /Turnovers/ })).toHaveTextContent('HOM · 2 turnovers fewer');
    expect(screen.getByRole('tab', { name: /Success rate/ })).toHaveTextContent('AWY · 10.0 pp ahead');
    expect(screen.getByRole('tab', { name: /Turnovers/ }).querySelector('span[style*="width"]')).toHaveStyle({ width: '67%' });
    expect(screen.getByRole('tab', { name: /Success rate/ }).querySelector('span[style*="width"]')).toHaveStyle({ width: '50%' });
    expect(screen.getByRole('tab', { name: /Penalty yards/ })).toHaveTextContent('58 known');
    expect(screen.getByRole('tab', { name: /Penalty yards/ })).toHaveTextContent('Undecided · penalty yards unresolved');
    expect(screen.getByRole('tab', { name: /Penalty yards/ }).querySelector('span[style*="width"]')).toBeNull();
    const scaleDisclosure = screen.getByText('About bar scale').closest('details');
    expect(scaleDisclosure).not.toHaveAttribute('open');
    fireEvent.click(screen.getByText('About bar scale'));
    expect(scaleDisclosure).toHaveAttribute('open');
    expect(screen.getByText(/10.0 pp ÷ 20 pp = 50% of the completed-game reference/)).toBeInTheDocument();
    expect(screen.getByText(/Live bars use completed games as a reference/)).toBeInTheDocument();

    const resolved = { ...withFactors, expanded_details: { ...withFactors.expanded_details,
      [home.id]: { 'Offensive Plays': Array.from({ length: 20 }, () => ({ type: 'Rush', text: 'run', yards: 4 })), 'Penalty Yards': [] },
    } } as GameResponse;
    rerender(<GameExplorer game={resolved} scope="competitive" away={away} home={home} />);
    expect(screen.getByRole('tab', { name: /Penalty yards/ }).querySelector('span[style*="width"]')).toHaveStyle({ width: '76%' });

    const unknownTeam = { ...resolved, expanded_details: { ...resolved.expanded_details,
      [home.id]: { 'Offensive Plays': [{ type: 'Rush', text: 'run', yards: 4 }],
        'Penalty Yards': [{ type: 'Penalty', text: 'unknown team', yards: -10,
          penalty_status: 'accepted', team_attribution_note: 'Committing team unavailable' }] },
    } } as GameResponse;
    rerender(<GameExplorer game={unknownTeam} scope="competitive" away={away} home={home} />);
    expect(screen.getByRole('tab', { name: /Penalty yards/ })).toHaveTextContent('Undecided · penalty yards unresolved');
    expect(screen.getByRole('tab', { name: /Penalty yards/ }).querySelector('span[style*="width"]')).toBeNull();

    const finalGame = { ...resolved, status: 'final',
      advanced_table_full: resolved.advanced_table.map((row, index) => ({ ...row, 'Non-Offensive Points': index === 0 ? 7 : 0 })),
      expanded_details_full: resolved.expanded_details,
    } as GameResponse;
    rerender(<GameExplorer game={finalGame} scope="full" away={away} home={home} />);
    expect(screen.getByRole('tab', { name: /Success rate/ }).querySelector('span[style*="width"]')).toHaveStyle({ width: '53%' });
    expect(screen.getByRole('tab', { name: /Non-offensive points/ }).querySelector('span[style*="width"]')).toHaveStyle({ width: '50%' });
    expect(screen.getByText(/A full bar marks a large historical gap/)).toBeInTheDocument();

    const capped = { ...finalGame, advanced_table_full: finalGame.advanced_table_full.map((row, index) => ({
      ...row, 'Non-Offensive Points': index === 0 ? 21 : 0,
    })) } as GameResponse;
    rerender(<GameExplorer game={capped} scope="full" away={away} home={home} />);
    fireEvent.click(screen.getByRole('tab', { name: /Non-offensive points/ }));
    expect(screen.getByRole('tab', { name: /Non-offensive points/ }).querySelector('span[style*="width"]')).toHaveStyle({ width: '100%' });
    expect(screen.getByText(/21 pts meets or exceeds the 14 pts historical final-game reference; bar capped at 100%/)).toBeInTheDocument();

    const lowSample = { ...finalGame, expanded_details_full: {
      [away.id]: { 'Offensive Plays': [{ type: 'Rush', text: 'run', yards: 5 }] },
      [home.id]: { 'Offensive Plays': [{ type: 'Rush', text: 'run', yards: 4 }] },
    } } as GameResponse;
    rerender(<GameExplorer game={lowSample} scope="full" away={away} home={home} />);
    fireEvent.click(screen.getByRole('tab', { name: /Success rate/ }));
    expect(screen.getByRole('tab', { name: /Success rate/ }).querySelector('span[style*="width"]')).toBeNull();
    expect(screen.getByText(/Bar appears after each team has 20 eligible offensive plays/)).toBeInTheDocument();
  });
});
