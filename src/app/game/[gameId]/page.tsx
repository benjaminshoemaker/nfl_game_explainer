import { GamePageClient } from './GamePageClient';
import { GameResponse } from '@/types';
import { headers } from 'next/headers';

interface PageProps {
  params: Promise<{
    gameId: string;
  }>;
}

function isLocalhost(host: string | null): boolean {
  if (!host) return false;
  const hostname = host.split(':')[0]?.toLowerCase();
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';
}

function getRequestOrigin(): string {
  const h = headers();
  const forwardedProto = h.get('x-forwarded-proto');
  const forwardedHost = h.get('x-forwarded-host');
  const host = forwardedHost ?? h.get('host') ?? process.env.VERCEL_URL ?? 'localhost:3000';
  const proto =
    forwardedProto ??
    (process.env.NODE_ENV === 'development' || isLocalhost(host) ? 'http' : 'https');
  return `${proto}://${host}`;
}

async function getGameData(gameId: string): Promise<GameResponse | null> {
  const requestId =
    (globalThis.crypto && 'randomUUID' in globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function')
      ? globalThis.crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  try {
    // Prefer the request host over `VERCEL_URL` so we don't accidentally call a protected deployment URL.
    const origin = getRequestOrigin();
    const url = new URL(`/api/game/${gameId}`, origin);

    const response = await fetch(url, {
      // Revalidate every 30 seconds for live games
      next: { revalidate: 30 },
      headers: {
        'x-nfl-request-id': requestId,
      },
    });

    if (!response.ok) {
      const responseText = await response.text().catch(() => '');
      console.error('Failed to fetch game data', {
        gameId,
        status: response.status,
        url: url.toString(),
        requestId,
        vercelUrl: process.env.VERCEL_URL,
        host: headers().get('host'),
        forwardedHost: headers().get('x-forwarded-host'),
        forwardedProto: headers().get('x-forwarded-proto'),
        responseText: responseText.slice(0, 500),
      });
      return null;
    }

    return await response.json();
  } catch (error) {
    console.error('Error fetching game data', { gameId, requestId, error });
    return null;
  }
}

function ErrorState({ gameId, showLocalHint }: { gameId: string; showLocalHint: boolean }) {
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
        {showLocalHint && (
          <p className="font-body text-text-muted text-sm">
            Local dev tip: this page needs the Python API. Run <code>python local_server.py</code> (port 8000) alongside{' '}
            <code>npm run dev</code>, or use <code>vercel dev</code>.
          </p>
        )}
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
    const host = headers().get('host');
    const showLocalHint = process.env.NODE_ENV === 'development' || isLocalhost(host);
    return <ErrorState gameId={gameId} showLocalHint={showLocalHint} />;
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
