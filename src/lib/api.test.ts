import { describe, expect, it } from 'vitest';
import { getAwayTeam, getHomeTeam, getTeamStats } from './api';
import type { GameResponse } from '@/types';

describe('src/lib/api helpers', () => {
  const game: GameResponse = {
    gameId: '401',
    label: 'AWY_at_HOM_401',
    status: 'in-progress',
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
  };

  it('returns home and away teams', () => {
    expect(getAwayTeam(game)?.abbr).toBe('AWY');
    expect(getHomeTeam(game)?.abbr).toBe('HOM');
  });

  it('finds stats for a team by abbreviation', () => {
    const stats = [
      { Team: 'AWY', Score: 7 },
      { Team: 'HOM', Score: 3 },
    ];
    expect(getTeamStats(stats, 'HOM')).toEqual({ Team: 'HOM', Score: 3 });
    expect(getTeamStats(stats, 'XXX')).toBeUndefined();
  });
});

