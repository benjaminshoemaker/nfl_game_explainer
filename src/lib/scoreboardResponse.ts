import type { ScoreboardResponse } from '@/types';

export function isScoreboardResponse(value: unknown): value is ScoreboardResponse {
  if (!value || typeof value !== 'object') return false;
  const data = value as Partial<ScoreboardResponse> & { error?: unknown };
  return !data.error && Array.isArray(data.games)
    && !!data.week && typeof data.week.number === 'number'
    && typeof data.week.label === 'string'
    && [1, 2, 3].includes(data.week.seasonType);
}
