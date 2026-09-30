'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { buildScoreboardUrl } from '@/lib/scoreboardUrl';
import type { GameWeek, ScoreboardGame, ScoreboardResponse } from '@/types';

export function DebugGamePicker({ gameId, label, week }: {
  gameId: string;
  label: string;
  week?: GameWeek;
}) {
  const router = useRouter();
  const [games, setGames] = useState<ScoreboardGame[]>([]);
  const weekNumber = week?.number;
  const seasonType = week?.seasonType;

  useEffect(() => {
    const controller = new AbortController();
    const selection = weekNumber !== undefined && seasonType !== undefined
      ? { weekNumber, seasonType }
      : null;
    fetch(buildScoreboardUrl(selection), { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Scoreboard unavailable');
        return response.json() as Promise<ScoreboardResponse>;
      })
      .then((data) => setGames(data.games))
      .catch(() => { /* The current game remains available if the scoreboard cannot load. */ });
    return () => controller.abort();
  }, [weekNumber, seasonType]);

  function selectGame(nextGameId: string) {
    if (nextGameId === gameId) return;
    const params = new URLSearchParams({ debug: 'true' });
    if (week && week.number > 0) {
      params.set('week', String(week.number));
      params.set('seasontype', String(week.seasonType));
    }
    router.push(`/game/${nextGameId}?${params}`);
  }

  return (
    <label className="flex min-w-0 items-center gap-2 text-xs">
      <span className="shrink-0">Game</span>
      <select
        aria-label="Game"
        className="min-w-0 max-w-72 rounded-sm border border-slate-400 bg-white px-2 py-1 text-xs text-slate-900 focus-visible:outline-2 focus-visible:outline-blue-600"
        value={gameId}
        onChange={(event) => selectGame(event.target.value)}
      >
        {!games.some((game) => game.gameId === gameId) && <option value={gameId}>{label}</option>}
        {games.map((game) => (
          <option key={game.gameId} value={game.gameId}>
            {game.awayTeam.abbr} @ {game.homeTeam.abbr}
          </option>
        ))}
      </select>
    </label>
  );
}
