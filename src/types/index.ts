// Season type: 1=preseason, 2=regular, 3=postseason
export type SeasonType = 1 | 2 | 3;
export type GameStatus = 'pregame' | 'in-progress' | 'delayed' | 'postponed' | 'canceled' | 'final';

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
  status: GameStatus;
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
  'Official Yards Per Play (Full Game)'?: number | null;
  'Adjusted Yards Per Play': number;
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
  source_play_id?: string | null;
  success?: boolean;
  penalty_type?: string | null;
  penalty_status?: string | null;
  type: string;
  text: string;
  yards?: number | null;
  yardage_note?: string | null;
  team_attribution_note?: string | null;
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

export interface CanonicalPlay {
  id: string;
  sourceTeamId: string;
  sourceTeam: string | null;
  quarter: number | null;
  clock: string | null;
  type: string;
  text: string;
  down: number | null;
  distance: number | null;
  ballBefore: string | null;
  scoreBefore: { home: number; away: number } | null;
  scoreAfter: { home: number; away: number } | null;
  homeWpBefore: number | null;
  homeWpAfter: number | null;
  homeWpDelta: number | null;
  wpAttributionUncertain?: boolean;
  epa: number | null;
  penalty: { team: string | null; type: string; status: string; yards: number | null; note: string | null } | null;
  scoreChange: { team: string | null; points: number; non_offensive: boolean } | null;
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
  status: GameStatus;
  statusDetail?: string;
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
  plays?: CanonicalPlay[];
  wp_filter: {
    enabled: boolean;
    threshold: number;
    description: string;
  };
  analysis: string;
  ai_summary?: string | null;
  season?: number;
  pregame_preview?: PregamePreview | null;
  source_gaps?: Array<{ team: string; yards_gap: number; turnovers_gap: number; plays_gap?: number }>;
  debug?: GameDebugData;
}

export interface DebugPlayRow {
  kind: 'play' | 'drive_end';
  drive: number;
  playId?: string | number | null;
  team: string;
  quarter?: number | null;
  clock?: string | null;
  type?: string | null;
  text?: string | null;
  down?: number | null;
  distance?: number | null;
  sourceYards?: number | null;
  classification?: string;
  competitive?: boolean;
  excludedReason?: string | null;
  startHomeWP?: number | null;
  endHomeWP?: number | null;
  statDeltas: Record<string, Record<string, number>>;
  raw: Record<string, unknown>;
}

export interface GameDebugData {
  statsCompetitive: Record<string, string | number | null>[];
  statsFull: Record<string, string | number | null>[];
  plays: DebugPlayRow[];
  sources: {
    espnSummary: Record<string, unknown>;
    playProbabilities: Record<string, unknown>;
    pregameProbabilities: { home: number; away: number };
  };
}

// Component prop types
export interface ScoreboardProps {
  homeTeam: Team;
  awayTeam: Team;
  status: GameStatus;
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


export interface PreviewMetric {
  value: number | null; rank: number | null; rankPool: number;
  percentile: number | null; complete: boolean; tied?: boolean;
}
export interface PreviewTeam {
  id: string; abbr: string; name: string;
  record: { wins: number; losses: number; ties: number };
  gamesAvailable: number;
  factors: Record<string, { own: PreviewMetric; opponent: PreviewMetric; net: PreviewMetric }>;
}
export interface PregamePreview {
  season: number; throughWeek: number; publishedAt: string; kickoff: string;
  home: string; away: string; week: number; model: number;
  factors: Array<{ id: string; label: string; unit: string }>;
  teams: PreviewTeam[];
  power: Array<{ id: string; rank: number; rating: number; contributions: Record<string, number> }>;
  weights: Record<string, number>;
  narrative: { headline: string; summary: string;
    watchPoints: Array<{ title: string; body: string; factIds: string[] }> } | null;
}
