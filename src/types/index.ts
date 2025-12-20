// Season type: 1=preseason, 2=regular, 3=postseason
export type SeasonType = 1 | 2 | 3;

// Week selection for picker
export interface WeekSelection {
  weekNumber: number;
  seasonType: SeasonType;
}

// Week option for dropdown
export interface WeekOption {
  weekNumber: number;
  seasonType: SeasonType;
  label: string;       // e.g., "Week 5" or "Wild Card"
  shortLabel: string;  // e.g., "Wk 5" or "WC"
  value: string;       // URL-safe value: "5" or "wildcard"
}

// Team info for scoreboard
export interface Team {
  abbr: string;
  name: string;
  score: number;
  logo: string;
  id?: string;
}

// Scoreboard game (from /api/scoreboard)
export interface ScoreboardGame {
  gameId: string;
  status: 'pregame' | 'in-progress' | 'final';
  statusDetail: string;
  homeTeam: Team;
  awayTeam: Team;
  startTime: string | null;
  isActive: boolean;
}

export interface ScoreboardResponse {
  week: {
    number: number;
    label: string;
    seasonType: SeasonType;
  };
  games: ScoreboardGame[];
}

// Team meta for game detail
export interface TeamMeta {
  id: string;
  abbr: string;
  name: string;
  homeAway: 'home' | 'away';
}

// Stats row
export interface SummaryStats {
  Team: string;
  Score: number;
  'Total Yards': number;
  Drives: number;
}

export interface AdvancedStats {
  Team: string;
  Score: number;
  Turnovers: number;
  'Total Yards': number;
  'Yards Per Play': number;
  'Success Rate': number;
  'Explosive Plays': number;
  'Explosive Play Rate': number;
  'Points Per Trip (Inside 40)': number;
  'Ave Start Field Pos': string;
  'Penalty Yards': number;
  'Non-Offensive Points': number;
}

// Play detail
export interface PlayDetail {
  type: string;
  text: string;
  yards?: number;
  points?: number;
  quarter?: number;
  clock?: string;
  start_pos?: string;
  end_pos?: string;
  probability?: {
    homeWinPercentage: number;
    awayWinPercentage: number;
    homeDelta: number;
    awayDelta: number;
  };
}

// Game clock info for live games
export interface GameClock {
  quarter: number;
  clock: string;
  displayValue: string;
}

// Game week info
export interface GameWeek {
  number: number;
  seasonType: SeasonType;
}

// Full game response
export interface GameResponse {
  gameId: string;
  label: string;
  status: 'pregame' | 'in-progress' | 'final';
  gameClock?: GameClock | null;
  lastPlayTime?: string | null;
  week?: GameWeek;
  team_meta: TeamMeta[];
  summary_table: SummaryStats[];
  summary_table_full: SummaryStats[];
  advanced_table: AdvancedStats[];
  advanced_table_full: AdvancedStats[];
  expanded_details: Record<string, Record<string, PlayDetail[]>>;
  expanded_details_full: Record<string, Record<string, PlayDetail[]>>;
  wp_filter: {
    enabled: boolean;
    threshold: number;
    description: string;
  };
  analysis: string;
  ai_summary?: string | null;
}

// Component prop types
export interface ScoreboardProps {
  homeTeam: Team;
  awayTeam: Team;
  status: 'pregame' | 'in-progress' | 'final';
  statusDetail: string;
}

export interface StatRowProps {
  label: string;
  awayValue: number | string;
  homeValue: number | string;
  awayTeam: string;
  homeTeam: string;
  format?: 'number' | 'percent' | 'string';
  higherIsBetter?: boolean;
}

export interface PlayListProps {
  plays: PlayDetail[];
  category: string;
  awayAbbr?: string;
  homeAbbr?: string;
}

export interface ViewToggleProps {
  showFiltered: boolean;
  onToggle: (filtered: boolean) => void;
}
