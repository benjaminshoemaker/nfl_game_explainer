'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ScoreboardGame, WeekSelection } from '@/types';
import { getTeamTextColor } from '@/lib/teamColors';

interface GameSidebarProps {
  games: ScoreboardGame[];
  weekLabel: string;
  week?: WeekSelection | null;
}

function buildGameHref(gameId: string, week?: WeekSelection | null): string {
  if (!week || week.weekNumber <= 0) return `/game/${gameId}`;
  const params = new URLSearchParams();
  params.set('week', String(week.weekNumber));
  params.set('seasontype', String(week.seasonType));
  return `/game/${gameId}?${params.toString()}`;
}

function GameRow({ game, isActive: isCurrent, week }: { game: ScoreboardGame; isActive: boolean; week?: WeekSelection | null }) {
  const { homeTeam, awayTeam, status, statusDetail, gameId, isActive } = game;

  const isPregame = status === 'pregame';
  const isFinal = status === 'final';
  const isHomeWinning = homeTeam.score > awayTeam.score;
  const isAwayWinning = awayTeam.score > homeTeam.score;

  return (
    <Link
      href={buildGameHref(gameId, week)}
      className={`
        block px-3 py-2 rounded-lg transition-all duration-200
        ${isCurrent
          ? 'bg-gold/20 border border-gold/30'
          : 'hover:bg-bg-elevated border border-transparent'
        }
      `}
    >
      <div className="flex items-center justify-between">
        {/* Teams */}
        <div className="flex flex-col gap-0.5 flex-1 min-w-0">
          {/* Away team */}
          <div className="flex items-center gap-2">
            <span
              className={`font-condensed text-xs uppercase tracking-wide ${
                isAwayWinning && isFinal ? 'font-bold' : ''
              }`}
              style={{ color: getTeamTextColor(awayTeam.abbr) }}
            >
              {awayTeam.abbr}
            </span>
            <span className="text-text-muted text-xs">@</span>
            <span
              className={`font-condensed text-xs uppercase tracking-wide ${
                isHomeWinning && isFinal ? 'font-bold' : ''
              }`}
              style={{ color: getTeamTextColor(homeTeam.abbr) }}
            >
              {homeTeam.abbr}
            </span>
          </div>
        </div>

        {/* Score or status */}
        <div className="flex items-center gap-2">
          {isPregame ? (
            <span className="font-condensed text-xs text-text-muted">
              {statusDetail}
            </span>
          ) : (
            <div className="flex items-center gap-1">
              <span className={`font-display text-sm ${isAwayWinning && isFinal ? 'text-gold' : 'text-text-primary'}`}>
                {awayTeam.score}
              </span>
              <span className="text-text-muted text-xs">-</span>
              <span className={`font-display text-sm ${isHomeWinning && isFinal ? 'text-gold' : 'text-text-primary'}`}>
                {homeTeam.score}
              </span>
            </div>
          )}

          {/* Live indicator */}
          {isActive && (
            <span className="flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-positive opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-positive" />
            </span>
          )}
        </div>
      </div>

      {/* Status detail for non-pregame */}
      {!isPregame && (
        <div className="mt-1">
          <span
            className={`font-condensed text-xs uppercase tracking-wider ${
              isActive ? 'text-positive' : 'text-text-muted'
            }`}
          >
            {statusDetail}
          </span>
        </div>
      )}
    </Link>
  );
}

export function GameSidebar({ games, weekLabel, week }: GameSidebarProps) {
  const pathname = usePathname();
  const currentGameId = pathname?.split('/').pop();

  // Sort games: in-progress first, then pregame, then final
  const sortedGames = [...games].sort((a, b) => {
    if (a.isActive && !b.isActive) return -1;
    if (!a.isActive && b.isActive) return 1;
    if (a.status === 'pregame' && b.status !== 'pregame') return -1;
    if (a.status !== 'pregame' && b.status === 'pregame') return 1;
    return 0;
  });

  return (
    <div className="h-full flex flex-col bg-bg-card border-r border-border-subtle">
      {/* Header */}
      <div className="p-4 border-b border-border-subtle">
        <Link href="/" className="block hover:opacity-80 transition-opacity">
          <h2 className="font-display text-lg tracking-wider text-text-primary">
            NFL GAMES
          </h2>
          <p className="font-condensed text-xs font-medium text-text-muted uppercase tracking-wider">
            {weekLabel}
          </p>
        </Link>
      </div>

      {/* Games list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {sortedGames.map((game) => (
          <GameRow
            key={game.gameId}
            game={game}
            isActive={game.gameId === currentGameId}
            week={week}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-border-subtle">
        <p className="font-condensed text-xs text-text-muted text-center uppercase tracking-wider">
          {games.filter((g) => g.isActive).length > 0
            ? `${games.filter((g) => g.isActive).length} live`
            : 'No live games'}
        </p>
      </div>
    </div>
  );
}
