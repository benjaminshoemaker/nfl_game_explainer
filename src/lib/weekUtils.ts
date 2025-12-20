import { SeasonType, WeekOption, WeekSelection } from '@/types';

// Regular season weeks (1-18)
const REGULAR_SEASON_WEEKS: WeekOption[] = Array.from({ length: 18 }, (_, i) => ({
  weekNumber: i + 1,
  seasonType: 2 as SeasonType,
  label: `Week ${i + 1}`,
  shortLabel: `Wk ${i + 1}`,
  value: String(i + 1),
}));

// Playoff weeks with named rounds
const PLAYOFF_WEEKS: WeekOption[] = [
  { weekNumber: 1, seasonType: 3, label: 'Wild Card', shortLabel: 'WC', value: 'wildcard' },
  { weekNumber: 2, seasonType: 3, label: 'Divisional Round', shortLabel: 'DIV', value: 'divisional' },
  { weekNumber: 3, seasonType: 3, label: 'Conference Championship', shortLabel: 'CONF', value: 'conference' },
  // Note: Week 4 is Pro Bowl, skip it
  { weekNumber: 5, seasonType: 3, label: 'Super Bowl', shortLabel: 'SB', value: 'superbowl' },
];

// All week options for the picker
export const WEEK_OPTIONS: WeekOption[] = [...REGULAR_SEASON_WEEKS, ...PLAYOFF_WEEKS];

// Map URL param values to week selections
const URL_PARAM_MAP: Record<string, WeekSelection> = {
  wildcard: { weekNumber: 1, seasonType: 3 },
  divisional: { weekNumber: 2, seasonType: 3 },
  conference: { weekNumber: 3, seasonType: 3 },
  superbowl: { weekNumber: 5, seasonType: 3 },
};

// Add regular season weeks to the map
for (let i = 1; i <= 18; i++) {
  URL_PARAM_MAP[String(i)] = { weekNumber: i, seasonType: 2 };
}

/**
 * Parse URL week parameter to WeekSelection
 * Returns null if param is invalid
 */
export function parseWeekParam(param: string | null | undefined): WeekSelection | null {
  if (!param) return null;

  const normalized = param.toLowerCase().trim();
  return URL_PARAM_MAP[normalized] || null;
}

/**
 * Convert WeekSelection to URL parameter value
 */
export function weekToUrlParam(week: WeekSelection): string {
  if (week.seasonType === 3) {
    // Playoff - use named value
    const option = PLAYOFF_WEEKS.find(
      (w) => w.weekNumber === week.weekNumber && w.seasonType === week.seasonType
    );
    return option?.value || String(week.weekNumber);
  }
  // Regular season - just the number
  return String(week.weekNumber);
}

/**
 * Get display label for a week selection
 */
export function getWeekLabel(week: WeekSelection): string {
  const option = WEEK_OPTIONS.find(
    (w) => w.weekNumber === week.weekNumber && w.seasonType === week.seasonType
  );
  return option?.label || `Week ${week.weekNumber}`;
}

/**
 * Get short label for a week selection
 */
export function getWeekShortLabel(week: WeekSelection): string {
  const option = WEEK_OPTIONS.find(
    (w) => w.weekNumber === week.weekNumber && w.seasonType === week.seasonType
  );
  return option?.shortLabel || `Wk ${week.weekNumber}`;
}

/**
 * Find the WeekOption for a given selection
 */
export function findWeekOption(week: WeekSelection): WeekOption | undefined {
  return WEEK_OPTIONS.find(
    (w) => w.weekNumber === week.weekNumber && w.seasonType === week.seasonType
  );
}

/**
 * Check if two week selections are equal
 */
export function weekSelectionsEqual(a: WeekSelection, b: WeekSelection): boolean {
  return a.weekNumber === b.weekNumber && a.seasonType === b.seasonType;
}

/**
 * Get regular season options only
 */
export function getRegularSeasonOptions(): WeekOption[] {
  return REGULAR_SEASON_WEEKS;
}

/**
 * Get playoff options only
 */
export function getPlayoffOptions(): WeekOption[] {
  return PLAYOFF_WEEKS;
}
