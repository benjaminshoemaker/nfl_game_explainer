import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DebugGamePicker } from './DebugGamePicker';

const push = vi.hoisted(() => vi.fn());
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));

afterEach(() => {
  vi.unstubAllGlobals();
  push.mockClear();
});

describe('DebugGamePicker', () => {
  it('lists same-week games and keeps debug mode when switching games', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        week: { number: 13, seasonType: 2, label: 'Week 13' },
        games: [
          { gameId: '401', awayTeam: { abbr: 'AWY' }, homeTeam: { abbr: 'HOM' } },
          { gameId: '402', awayTeam: { abbr: 'GB' }, homeTeam: { abbr: 'DET' } },
        ],
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<DebugGamePicker gameId="401" label="AWY_at_HOM_401" week={{ number: 13, seasonType: 2 }} />);

    const picker = screen.getByRole('combobox', { name: 'Game' });
    await waitFor(() => expect(screen.getByRole('option', { name: 'GB @ DET' })).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith('/api/scoreboard?seasontype=2&week=13', expect.objectContaining({ signal: expect.any(AbortSignal) }));
    fireEvent.change(picker, { target: { value: '402' } });
    expect(push).toHaveBeenCalledWith('/game/402?debug=true&week=13&seasontype=2');
  });
});
