import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
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
    expect(screen.getByText('54.4%')).toBeInTheDocument();
    expect([...container.querySelectorAll('i')].some(dot => dot.style.left === '0%')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'LV on offense' }));
    expect(screen.getByText('42.5%')).toBeInTheDocument();
    expect(screen.getAllByRole('img')).toHaveLength(10);
    expect(screen.getByText('SEA +4.03')).toBeInTheDocument();
    expect(screen.getByText('LV +2.08')).toBeInTheDocument();
    expect(screen.queryByText('Things to watch')).not.toBeInTheDocument();
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
