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
  probability?: {
    homeWinPercentage: number;
    awayWinPercentage: number;
    homeDelta: number;
    awayDelta: number;
  };
}

// Full game response
export interface GameResponse {
  gameId: string;
  label: string;
  status: 'pregame' | 'in-progress' | 'final';
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
