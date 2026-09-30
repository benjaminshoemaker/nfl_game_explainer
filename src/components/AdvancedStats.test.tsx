import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AdvancedStats } from './AdvancedStats';
import type { AdvancedStats as AdvancedStatsType, TeamMeta } from '@/types';

const teams: TeamMeta[] = [
  { id: '1', abbr: 'CHI', name: 'Bears', homeAway: 'away' },
  { id: '2', abbr: 'CIN', name: 'Bengals', homeAway: 'home' },
];

const stats: AdvancedStatsType[] = teams.map((team) => ({
  Team: team.abbr,
  Score: 0,
  Turnovers: 0,
  'Total Yards': 0,
  'Adjusted Yards Per Play': team.abbr === 'CHI' ? 5.42 : 6.13,
  'Success Rate': 0,
  'Explosive Plays': 0,
  'Explosive Play Rate': 0,
  'Points Per Trip (Inside 40)': 0,
  'Ave Start Field Pos': '0',
  'Penalty Yards': 0,
  'Non-Offensive Points': 0,
}));

describe('AdvancedStats', () => {
  it('shows adjusted yards per play and explains turnovers in both layouts', () => {
    render(<AdvancedStats stats={stats} teamMeta={teams} />);

    expect(screen.getAllByText('Turnovers')).toHaveLength(2);
    expect(screen.queryByText('Margin')).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'includes onside kick recoveries' })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: 'includes onside kick recoveries' })[0])
      .toHaveAttribute('title', 'includes onside kick recoveries');
    expect(screen.getAllByRole('tooltip', { hidden: true })).toHaveLength(4);
    expect(screen.getAllByText('Adjusted Yards / Play')).toHaveLength(2);
    expect(screen.getAllByText('5.42')).toHaveLength(2);
    expect(screen.getAllByText('6.13')).toHaveLength(2);
    expect(document.querySelectorAll('[data-winner]')).toHaveLength(16);
  });

  it('shows every inside-40 trip beside the points-per-trip comparison', () => {
    const expandedDetails = {
      '1': { 'Points Per Trip (Inside 40)': [7, 3, 7, 3, 7, 0].map((points) => ({ type: 'Drive', text: '', points })) },
      '2': { 'Points Per Trip (Inside 40)': [7, 7, 3, 0, 7, 3, 3].map((points) => ({ type: 'Drive', text: '', points })) },
    };

    const { rerender } = render(
      <AdvancedStats stats={stats} teamMeta={teams} expandedDetails={expandedDetails} />
    );

    expect(screen.getByText('Trips reaching opponent 40')).toBeInTheDocument();
    expect(screen.getByText('6 trips · 27 pts')).toBeInTheDocument();
    expect(screen.getByText('7 trips · 30 pts')).toBeInTheDocument();
    expect(within(screen.getByRole('list', { name: 'CHI trips reaching opponent 40' })).getAllByRole('listitem'))
      .toHaveLength(6);
    expect(within(screen.getByRole('list', { name: 'CIN trips reaching opponent 40' })).getAllByRole('listitem'))
      .toHaveLength(7);

    rerender(<AdvancedStats stats={stats} teamMeta={teams} expandedDetails={{
      '1': { 'Points Per Trip (Inside 40)': [] },
      '2': { 'Points Per Trip (Inside 40)': [{ type: 'Drive', text: '', points: 3 }] },
    }} />);
    expect(screen.getByText('No trips')).toBeInTheDocument();
    expect(screen.getByText('1 trip · 3 pts')).toBeInTheDocument();
    expect(screen.queryByText('6 trips · 27 pts')).not.toBeInTheDocument();
  });
});
