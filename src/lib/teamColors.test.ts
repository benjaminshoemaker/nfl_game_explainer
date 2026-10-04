import { describe, expect, it } from 'vitest';

import { parseStatValue } from './teamColors';

describe('parseStatValue field position', () => {
  it('compares positions on both sides of midfield in the offense’s direction', () => {
    expect(parseStatValue('Own 49')).toBe(49);
    expect(parseStatValue('Own 50')).toBe(50);
    expect(parseStatValue('Opp 32')).toBe(68);
    expect(parseStatValue('Opp 0')).toBe(100);
  });
});
