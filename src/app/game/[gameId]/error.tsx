'use client';

import { useEffect } from 'react';
import { ErrorState } from '@/components/ErrorState';

export default function GameError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Game page error:', error);
  }, [error]);

  return <ErrorState title="Unable to load game" message="We had trouble loading this game's data. This could be temporary." onRetry={reset} />;
}
