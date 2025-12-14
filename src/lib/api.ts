import { ScoreboardResponse, GameResponse } from '@/types';

const API_BASE = '/api';

export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public statusText: string
  ) {
    super(message);
    this.name = 'APIError';
  }
}

async function fetchWithError<T>(url: string): Promise<T> {
  const response = await fetch(url);

  if (!response.ok) {
    throw new APIError(
      `API request failed: ${response.statusText}`,
      response.status,
      response.statusText
    );
  }

  return response.json();
}

/**
 * Fetch the current NFL scoreboard with all games
 */
export async function fetchScoreboard(): Promise<ScoreboardResponse> {
  return fetchWithError<ScoreboardResponse>(`${API_BASE}/scoreboard`);
}

/**
 * Fetch full game analysis for a specific game
 */
export async function fetchGame(gameId: string): Promise<GameResponse> {
  return fetchWithError<GameResponse>(`${API_BASE}/game/${gameId}`);
}

/**
 * Get the team abbreviation for away team from game response
 */
export function getAwayTeam(game: GameResponse) {
  return game.team_meta.find((t) => t.homeAway === 'away');
}

/**
 * Get the team abbreviation for home team from game response
 */
export function getHomeTeam(game: GameResponse) {
  return game.team_meta.find((t) => t.homeAway === 'home');
}

/**
 * Get stats for a specific team from the stats table
 */
export function getTeamStats<T extends { Team: string }>(
  stats: T[],
  teamAbbr: string
): T | undefined {
  return stats.find((s) => s.Team === teamAbbr);
}
