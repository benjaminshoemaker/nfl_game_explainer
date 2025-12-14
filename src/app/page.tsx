import { ScoreboardResponse, ScoreboardGame } from '@/types';
import { GameCard } from '@/components/GameCard';

async function getScoreboard(): Promise<ScoreboardResponse | null> {
  try {
    const baseUrl = process.env.VERCEL_URL
      ? `https://${process.env.VERCEL_URL}`
      : process.env.NODE_ENV === 'development'
      ? 'http://localhost:3000'
      : '';

    const response = await fetch(`${baseUrl}/api/scoreboard`, {
      next: { revalidate: 60 }, // Revalidate every minute
    });

    if (!response.ok) {
      console.error(`Failed to fetch scoreboard: ${response.status}`);
      return null;
    }

    return await response.json();
  } catch (error) {
    console.error('Error fetching scoreboard:', error);
    return null;
  }
}

function sortGames(games: ScoreboardGame[]): ScoreboardGame[] {
  return [...games].sort((a, b) => {
    // In-progress games first
    if (a.isActive && !b.isActive) return -1;
    if (!a.isActive && b.isActive) return 1;

    // Then pregame by start time
    if (a.status === 'pregame' && b.status === 'pregame') {
      const aTime = a.startTime ? new Date(a.startTime).getTime() : 0;
      const bTime = b.startTime ? new Date(b.startTime).getTime() : 0;
      return aTime - bTime;
    }
    if (a.status === 'pregame') return -1;
    if (b.status === 'pregame') return 1;

    // Final games last
    return 0;
  });
}

function LoadingState() {
  return (
    <div className="container mx-auto px-6 py-12">
      <div className="text-center mb-12">
        <h1 className="font-display text-5xl tracking-wide text-text-primary mb-2">
          NFL Games
        </h1>
        <p className="font-condensed text-lg text-text-secondary uppercase tracking-wider">
          Loading games...
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="bg-bg-card rounded-xl border border-border-subtle p-4 animate-pulse">
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-bg-elevated rounded-full" />
                <div className="h-4 bg-bg-elevated rounded flex-1" />
                <div className="w-8 h-6 bg-bg-elevated rounded" />
              </div>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-bg-elevated rounded-full" />
                <div className="h-4 bg-bg-elevated rounded flex-1" />
                <div className="w-8 h-6 bg-bg-elevated rounded" />
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-border-subtle">
              <div className="h-3 bg-bg-elevated rounded w-20" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="container mx-auto px-6 py-12">
      <div className="text-center">
        <h1 className="font-display text-5xl tracking-wide text-text-primary mb-4">
          NFL Game Explainer
        </h1>
        <p className="font-condensed text-xl text-text-secondary uppercase tracking-wider mb-8">
          Live Game Analysis Dashboard
        </p>
      </div>

      <div className="max-w-md mx-auto">
        <div className="bg-bg-card border border-border-subtle rounded-2xl p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-gold/20 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="font-display text-2xl tracking-wide text-text-primary mb-3">
            No Games Today
          </h2>
          <p className="font-body text-text-secondary leading-relaxed">
            Check back during game days for live analysis, advanced statistics, and AI-powered game summaries.
          </p>
        </div>
      </div>
    </div>
  );
}

export default async function Home() {
  const scoreboard = await getScoreboard();

  if (!scoreboard || scoreboard.games.length === 0) {
    return <EmptyState />;
  }

  const sortedGames = sortGames(scoreboard.games);
  const activeCount = sortedGames.filter((g) => g.isActive).length;

  return (
    <div className="container mx-auto px-6 py-8">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="font-display text-4xl md:text-5xl tracking-wide text-text-primary mb-2">
          NFL {scoreboard.week.label}
        </h1>
        <p className="font-condensed text-lg text-text-secondary uppercase tracking-wider">
          {sortedGames.length} Games
          {activeCount > 0 && (
            <span className="ml-2 text-positive">
              • {activeCount} Live
            </span>
          )}
        </p>
      </div>

      {/* Games grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {sortedGames.map((game) => (
          <GameCard key={game.gameId} game={game} />
        ))}
      </div>

      {/* Footer */}
      <div className="mt-12 text-center">
        <p className="font-condensed text-xs text-text-muted uppercase tracking-wider">
          Data from ESPN • Click any game for detailed analysis
        </p>
      </div>
    </div>
  );
}

export const metadata = {
  title: 'NFL Game Explainer | Live Game Analysis',
  description: 'Real-time NFL game analysis with advanced statistics, win probability tracking, and AI-powered game summaries.',
};
