import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GameLayoutShell } from './GameLayoutShell';

const searchParamValue = vi.hoisted(() => ({ debug: null as string | null }));

vi.mock('next/navigation', () => ({
  useSearchParams: () => ({ get: (key: string) => key === 'debug' ? searchParamValue.debug : null }),
}));
vi.mock('@/components/GameSidebarClient', () => ({
  GameSidebarClient: () => <div data-testid="game-sidebar" />,
}));

describe('GameLayoutShell', () => {
  it('removes the sidebar and mobile navigation in debug mode', () => {
    searchParamValue.debug = 'true';
    render(<GameLayoutShell><div>Debug content</div></GameLayoutShell>);
    expect(screen.getByText('Debug content')).toBeInTheDocument();
    expect(screen.queryByTestId('game-sidebar')).toBeNull();
    expect(screen.queryByText('All Games')).toBeNull();
  });

  it('keeps the sidebar for the normal game view', () => {
    searchParamValue.debug = null;
    render(<GameLayoutShell><div>Game content</div></GameLayoutShell>);
    expect(screen.getByTestId('game-sidebar')).toBeInTheDocument();
  });
});
