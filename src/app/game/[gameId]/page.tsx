import { GamePageClient } from './GamePageClient';
import { GameResponse } from '@/types';
import { headers } from 'next/headers';
import { ErrorState } from '@/components/ErrorState';

interface PageProps {
  params: Promise<{
    gameId: string;
  }>;
  searchParams: Promise<{ debug?: string | string[] }>;
}

function isLocalhost(host: string | null): boolean {
  if (!host) return false;
  const hostname = host.split(':')[0]?.toLowerCase();
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';
}

async function getRequestOrigin(): Promise<string> {
  const h = await headers();
  const forwardedProto = h.get('x-forwarded-proto');
  const forwardedHost = h.get('x-forwarded-host');
  const host = forwardedHost ?? h.get('host') ?? process.env.VERCEL_URL ?? 'localhost:3000';
  const proto =
    forwardedProto ??
    (process.env.NODE_ENV === 'development' || isLocalhost(host) ? 'http' : 'https');
  return `${proto}://${host}`;
}

async function getGameData(gameId: string, debug: boolean): Promise<GameResponse | null> {
  const requestId =
    (globalThis.crypto && 'randomUUID' in globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function')
      ? globalThis.crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  try {
    // Prefer the request host over `VERCEL_URL` so we don't accidentally call a protected deployment URL.
    const origin = await getRequestOrigin();
    const url = new URL(`/api/game/${gameId}`, origin);
    if (debug) url.searchParams.set('debug', 'true');

    const response = await fetch(url, {
      // Revalidate every 30 seconds for live games
      ...(debug ? { cache: 'no-store' as const } : { next: { revalidate: 30 } }),
      headers: {
        'x-nfl-request-id': requestId,
      },
    });

    if (!response.ok) {
      const responseText = await response.text().catch(() => '');
      const requestHeaders = await headers();
      console.error('Failed to fetch game data', {
        gameId,
        status: response.status,
        url: url.toString(),
        requestId,
        vercelUrl: process.env.VERCEL_URL,
        host: requestHeaders.get('host'),
        forwardedHost: requestHeaders.get('x-forwarded-host'),
        forwardedProto: requestHeaders.get('x-forwarded-proto'),
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

export default async function GamePage({ params, searchParams }: PageProps) {
  const { gameId } = await params;
  const debug = (await searchParams).debug === 'true';
  const gameData = await getGameData(gameId, debug);

  if (!gameData) {
    const host = (await headers()).get('host');
    const showLocalHint = process.env.NODE_ENV === 'development' || isLocalhost(host);
    return <ErrorState title="Unable to load game" message={`Game data for ID ${gameId} is unavailable. Please try again shortly.`} hint={showLocalHint ? 'Local development requires the Python API on port 8000 alongside Next.js.' : undefined} />;
  }

  return <GamePageClient initialGameData={gameData} debugMode={debug} />;
}

// Generate metadata for the page
export async function generateMetadata({ params }: PageProps) {
  const { gameId } = await params;

  return {
    title: `Game ${gameId} | NFL Game Explainer`,
    description: 'Live NFL game analysis with advanced stats and play-by-play breakdowns',
  };
}
