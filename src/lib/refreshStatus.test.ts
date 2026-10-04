import { describe, expect, it } from 'vitest';
import { formatCheckAge, latestPlayLabel, playFeedKey } from './refreshStatus';
import type { CanonicalPlay } from '@/types';

const play = { id: 'p1', quarter: 3, clock: '8:42' } as CanonicalPlay;

describe('refresh status', () => {
  it('uses elapsed wall time and game clock as different labels', () => {
    expect(formatCheckAge(3)).toBe('just now');
    expect(formatCheckAge(68)).toBe('1m ago');
    expect(latestPlayLabel(play)).toBe('Latest play: Q3 8:42');
    expect(latestPlayLabel({ ...play, quarter: 5 })).toBe('Latest play: OT 8:42');
  });

  it('detects a newly appended play without counting a repeated response as new', () => {
    expect(playFeedKey([play])).toBe(playFeedKey([{ ...play }]));
    expect(playFeedKey([play, { ...play, id: 'p2' }])).not.toBe(playFeedKey([play]));
  });
});
