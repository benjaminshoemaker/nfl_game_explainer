import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PregameReport } from './PregameReport';
import data from '../../api/lib/data/pregame.json';
import type { PregamePreview } from '@/types';

function preview(): PregamePreview {
  const game = Object.values(data.games).find(g => g.away === 'SEA')!;
  return { ...data, ...game, narrative: null,
    teams: data.teams.filter(t => [game.home, game.away].includes(t.id)),
    power: data.power.filter(t => [game.home, game.away].includes(t.id)),
  } as PregamePreview;
}
describe('PregameReport', () => {
  it('shows both matchup directions, visible last-place dots, and all rating drivers without AI', () => {
    const { container } = render(<PregameReport preview={preview()} />);
    expect(within(screen.getByRole('region', { name: 'When they have the ball' })).getByText('54.4%')).toBeInTheDocument();
    expect([...container.querySelectorAll('i')].some(dot => dot.style.left === '0%')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'LV on offense' }));
    expect(within(screen.getByRole('region', { name: 'When they have the ball' })).getByText('42.5%')).toBeInTheDocument();
    expect(screen.getAllByRole('img')).toHaveLength(10);
    expect(screen.getByText('SEA +4.03')).toBeInTheDocument();
    expect(screen.getByText('LV +2.08')).toBeInTheDocument();
    expect(screen.queryByText('Things to watch')).not.toBeInTheDocument();
  });
  it('separates raw team values from the model edge and explains it only once', () => {
    const { container } = render(<PregameReport preview={preview()} />);
    const row = screen.getByRole('group', { name: 'Adjusted yards / play comparison' });
    const sea = within(row.querySelector('[aria-label="SEA season values"]') as HTMLElement);
    const lv = within(row.querySelector('[aria-label="LV season values"]') as HTMLElement);
    expect(sea.getByText('+1.11')).toBeInTheDocument();
    expect(lv.getByText('−0.75')).toBeInTheDocument();
    expect(sea.queryByText('5.31')).not.toBeInTheDocument();
    const turnovers = within(screen.getByRole('group', { name: 'Turnovers comparison' }));
    expect(turnovers.getByText('−0.11')).toBeInTheDocument();
    expect(turnovers.getByText('+0.11')).toBeInTheDocument();
    expect(within(row).getByText('SEA +2.61')).toBeInTheDocument();
    expect(within(row).getByText('+1.86')).toBeInTheDocument();
    const scoring = within(screen.getByRole('group', { name: 'Scoring margin comparison' }));
    for (const value of ['+4.44', '−3.33', '+7.78']) expect(scoring.getByText(value)).toBeInTheDocument();
    const columns = Array.from(row.children);
    expect(columns[3]).toHaveAttribute('aria-label', 'Net difference');
    expect(columns[4]).toHaveTextContent('13.2%');
    expect(columns[5]).toHaveTextContent('SEA +2.61');
    expect(row.querySelector('details')).toBeNull();
    expect(screen.getAllByText('How model edge works')).toHaveLength(1);
    fireEvent.click(screen.getByText('How model edge works'));
    expect(container.querySelector('summary')?.closest('details')).toHaveAttribute('open');
  });
  it('renders generated copy and exact supporting evidence', () => {
    const p = preview();
    p.narrative = { headline: 'A test for Seattle', summary: 'A grounded preview.',
      watchPoints: [{ title: 'Can Seattle move the ball?', body: 'Watch the matchup.', factIds: ['SEA.success_rate.own'] }] };
    render(<PregameReport preview={p} />);
    expect(screen.getByRole('heading', { name: 'A test for Seattle' })).toBeInTheDocument();
    expect(screen.getByText('SEA Success rate: 45.6% (#21)')).toBeInTheDocument();
    fireEvent.click(screen.getByText('What goes into this? ↓'));
    expect(document.querySelector('#pregame-model')).toHaveAttribute('open');
  });
});
