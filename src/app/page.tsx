import { ScoreboardResponse } from '@/types';
import { DirectoryClient } from './DirectoryClient';

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

  return <DirectoryClient initialData={scoreboard} />;
}

export const metadata = {
  title: 'NFL Game Explainer | Live Game Analysis',
  description: 'Real-time NFL game analysis with advanced statistics, win probability tracking, and AI-powered game summaries.',
};
