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
  it('puts the latest play first, offers oldest first, and labels halftime', () => {
    const { container } = render(<GameExplorer game={game} scope="full" away={away} home={home} />);
    const listedIds = () => [...container.querySelectorAll('[data-play-id]')].map(node => node.getAttribute('data-play-id'));
    expect(listedIds()).toEqual(['latest', 'second', 'first']);
    expect(screen.getByLabelText('Sort')).toHaveValue('game');
    expect(screen.getByText(/Week 4 · Halftime/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Sort'), { target: { value: 'oldest' } });
    expect(listedIds()).toEqual(['first', 'second', 'latest']);
  });

  it('shows unavailable rates when no eligible offensive plays have arrived', () => {
    render(<GameExplorer game={{ ...game, plays: plays.slice(0, 1) }} scope="full" away={away} home={home} />);
    expect(screen.getByRole('tab', { name: /Success rate/ })).toHaveTextContent('— · —');
    expect(screen.getByRole('tab', { name: /Points per trip/ })).toHaveTextContent('— · —');
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
        [away.id]: { 'Offensive Plays': [{ type: 'Rush', text: 'run', yards: 5 }] },
        [home.id]: {
          'Offensive Plays': [{ type: 'Rush', text: 'run', yards: 4 }],
          'Penalty Yards': [{ type: 'Penalty', text: 'missing yards', yards: null, penalty_status: 'accepted' }],
        },
      },
    } as GameResponse;
    render(<GameExplorer game={withFactors} scope="competitive" away={away} home={home} />);
    expect(screen.getByLabelText('Factor wins')).toHaveTextContent('AWY 1 · HOM 1');
    expect(screen.getByRole('tab', { name: /Turnovers/ })).toHaveTextContent('HOM · 2 turnovers fewer');
    expect(screen.getByRole('tab', { name: /Success rate/ })).toHaveTextContent('AWY · 10.0 pp ahead');
    expect(screen.getByRole('tab', { name: /Penalty yards/ })).toHaveTextContent('58 known');
    expect(screen.getByRole('tab', { name: /Penalty yards/ })).toHaveTextContent('Undecided · penalty yards unresolved');
  });
});
