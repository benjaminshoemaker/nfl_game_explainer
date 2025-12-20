import type { WeekSelection } from '@/types';

export function buildScoreboardUrl(week?: WeekSelection | null): string {
  const baseUrl = '/api/scoreboard';
  if (!week) return baseUrl;

  const params = new URLSearchParams();
  params.set('seasontype', String(week.seasonType));

  // ESPN doesn't accept week=0; treat it as "unspecified".
  if (Number.isFinite(week.weekNumber) && week.weekNumber > 0) {
    params.set('week', String(week.weekNumber));
  }

  const queryString = params.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
}

