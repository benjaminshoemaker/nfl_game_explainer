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

  return (
    <div className="min-h-screen bg-bg-deep flex items-center justify-center">
      <ErrorState
        title="Unable to Load Game"
        message="We had trouble loading this game's data. This could be a temporary issue."
        onRetry={reset}
        showHomeLink={true}
      />
    </div>
  );
}
