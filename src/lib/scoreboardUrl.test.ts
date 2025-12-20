import { describe, expect, it } from 'vitest';
import { buildScoreboardUrl } from './scoreboardUrl';

describe('src/lib/scoreboardUrl', () => {
  it('returns base URL when week is missing', () => {
    expect(buildScoreboardUrl()).toBe('/api/scoreboard');
    expect(buildScoreboardUrl(null)).toBe('/api/scoreboard');
  });

  it('includes seasontype and week when week number is valid', () => {
    expect(buildScoreboardUrl({ weekNumber: 5, seasonType: 2 })).toBe('/api/scoreboard?seasontype=2&week=5');
  });

  it('omits week when week number is 0', () => {
    expect(buildScoreboardUrl({ weekNumber: 0, seasonType: 2 })).toBe('/api/scoreboard?seasontype=2');
  });
});

