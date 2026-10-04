import type { ScoreboardGame } from '@/types';

const priority: Record<ScoreboardGame['status'], number> = {
  'in-progress': 0,
  delayed: 1,
  pregame: 2,
  postponed: 3,
  final: 4,
  canceled: 5,
};

export function sortScoreboardGames(games: ScoreboardGame[]): ScoreboardGame[] {
  return [...games].sort((a, b) => {
    const order = priority[a.status] - priority[b.status];
    if (order) return order;
    if (a.status === 'pregame' || a.status === 'postponed') {
      return (a.startTime || '').localeCompare(b.startTime || '');
    }
    return 0;
  });
}
