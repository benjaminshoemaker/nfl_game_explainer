import { ScoreboardResponse } from '@/types';
import { GameSidebar } from '@/components/GameSidebar';

async function getScoreboard(): Promise<ScoreboardResponse | null> {
  try {
    const baseUrl = process.env.VERCEL_URL
      ? `https://${process.env.VERCEL_URL}`
      : process.env.NODE_ENV === 'development'
      ? 'http://localhost:8000'  // Local Python API server
      : '';

    const response = await fetch(`${baseUrl}/api/scoreboard`, {
      next: { revalidate: 60 },
    });

    if (!response.ok) {
      return null;
    }

    return await response.json();
  } catch {
    return null;
  }
}

interface LayoutProps {
  children: React.ReactNode;
}

export default async function GameLayout({ children }: LayoutProps) {
  const scoreboard = await getScoreboard();

  return (
    <div className="flex min-h-screen">
      {/* Sidebar - hidden on mobile, visible on lg+ */}
      <aside className="hidden lg:block w-64 flex-shrink-0 sticky top-0 h-screen">
        {scoreboard ? (
          <GameSidebar
            games={scoreboard.games}
            weekLabel={scoreboard.week.label}
          />
        ) : (
          <div className="h-full bg-bg-card border-r border-border-subtle flex items-center justify-center p-4">
            <p className="font-condensed text-xs text-text-muted text-center uppercase tracking-wider">
              Unable to load games
            </p>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0">
        {/* Mobile header with back button */}
        <div className="lg:hidden sticky top-0 z-10 bg-bg-deep/95 backdrop-blur border-b border-border-subtle">
          <div className="flex items-center gap-3 px-4 py-3">
            <a
              href="/"
              className="flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              <span className="font-condensed text-sm uppercase tracking-wider">All Games</span>
            </a>
          </div>
        </div>

        {children}
      </main>
    </div>
  );
}
