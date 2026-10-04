import { describe, expect, it } from 'vitest';
import { isScoreboardResponse } from './scoreboardResponse';

describe('scoreboard response validation', () => {
  it('accepts an empty but valid week and rejects upstream error payloads', () => {
    expect(isScoreboardResponse({ week: { number: 4, label: 'Week 4', seasonType: 2 }, games: [] })).toBe(true);
    expect(isScoreboardResponse({ week: { number: 0, label: 'Unknown', seasonType: 2 }, games: [], error: 'offline' })).toBe(false);
    expect(isScoreboardResponse({ week: { number: 4, label: 'Week 4', seasonType: 2 } })).toBe(false);
  });
});
