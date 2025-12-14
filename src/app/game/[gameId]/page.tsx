import { GamePageClient } from './GamePageClient';
import { GameResponse } from '@/types';

interface PageProps {
  params: Promise<{
    gameId: string;
  }>;
}

async function getGameData(gameId: string): Promise<GameResponse | null> {
  try {
    // In development, use localhost; in production, use relative URL
    const baseUrl = process.env.VERCEL_URL
      ? `https://${process.env.VERCEL_URL}`
      : process.env.NODE_ENV === 'development'
      ? 'http://localhost:8000'  // Local Python API server
      : '';

    const response = await fetch(`${baseUrl}/api/game/${gameId}`, {
      // Revalidate every 30 seconds for live games
      next: { revalidate: 30 },
    });

    if (!response.ok) {
      console.error(`Failed to fetch game ${gameId}: ${response.status}`);
      return null;
    }

    return await response.json();
  } catch (error) {
    console.error(`Error fetching game ${gameId}:`, error);
    return null;
  }
}

function LoadingState() {
  return (
    <div className="min-h-screen bg-bg-deep flex items-center justify-center">
      <div className="text-center space-y-4">
        <div className="w-12 h-12 border-4 border-gold border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="font-condensed text-sm uppercase tracking-wider text-text-muted">
          Loading game data...
        </p>
      </div>
    </div>
  );
}

function ErrorState({ gameId }: { gameId: string }) {
  return (
    <div className="min-h-screen bg-bg-deep flex items-center justify-center">
      <div className="text-center space-y-4 max-w-md px-4">
        <div className="w-16 h-16 rounded-full bg-negative/20 flex items-center justify-center mx-auto">
          <svg className="w-8 h-8 text-negative" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h1 className="font-display text-2xl text-text-primary">
          Game Not Found
        </h1>
        <p className="font-body text-text-secondary">
          Unable to load game data for ID: {gameId}
        </p>
        <a
          href="/"
          className="inline-block px-6 py-2 bg-gold text-bg-deep font-condensed uppercase tracking-wider rounded-lg hover:bg-gold/90 transition-colors"
        >
          Back to Games
        </a>
      </div>
    </div>
  );
}

export default async function GamePage({ params }: PageProps) {
  const { gameId } = await params;
  const gameData = await getGameData(gameId);

  if (!gameData) {
    return <ErrorState gameId={gameId} />;
  }

  return <GamePageClient initialGameData={gameData} />;
}

// Generate metadata for the page
export async function generateMetadata({ params }: PageProps) {
  const { gameId } = await params;

  return {
    title: `Game ${gameId} | NFL Game Explainer`,
    description: 'Live NFL game analysis with advanced stats and play-by-play breakdowns',
  };
}
