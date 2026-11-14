import { describe, expect, it } from 'vitest';
import { analyticsPage } from './analytics';

describe('analytics route identity', () => {
  it('ignores query strings and report section anchors', () => {
    expect(analyticsPage(new URL('https://windelta.app/game/401?token=private#drivers'))).toEqual({ path: '/game/401', page_type: 'game_report' });
  });
  it('recognizes team navigation in both URL formats', () => {
    for (const route of ['/teams/SEA', '/team-seasons.html#team/SEA']) {
      expect(analyticsPage(new URL(route, 'https://windelta.app'))).toEqual({ path: '/teams/SEA', page_type: 'team' });
    }
    expect(analyticsPage(new URL('https://windelta.app/teams#power')).page_type).toBe('rankings');
  });
});
