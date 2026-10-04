import { describe, expect, it } from 'vitest';
import { gameStatusFromEspn, isTerminalGame } from './gameStatus';

describe('ESPN game status mapping', () => {
  it('keeps interruption and cancellation distinct from final', () => {
    expect(gameStatusFromEspn({ state: 'in', name: 'STATUS_DELAYED', shortDetail: 'Weather Delay' })).toBe('delayed');
    expect(gameStatusFromEspn({ state: 'post', name: 'STATUS_POSTPONED', shortDetail: 'Postponed' })).toBe('postponed');
    expect(gameStatusFromEspn({ state: 'post', name: 'STATUS_CANCELED', shortDetail: 'Canceled' })).toBe('canceled');
    expect(isTerminalGame('postponed')).toBe(false);
    expect(isTerminalGame('canceled')).toBe(true);
  });

  it('keeps halftime live and a completed overtime game final', () => {
    expect(gameStatusFromEspn({ state: 'in', name: 'STATUS_HALFTIME', shortDetail: 'Halftime' })).toBe('in-progress');
    expect(gameStatusFromEspn({ state: 'post', name: 'STATUS_FINAL', shortDetail: 'Final/OT', completed: true })).toBe('final');
  });
});
