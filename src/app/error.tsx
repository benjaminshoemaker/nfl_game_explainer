'use client';

import { useEffect } from 'react';
import { ErrorState } from '@/components/ErrorState';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error('App error:', error);
  }, [error]);

  return (
    <div className="min-h-screen bg-bg-deep flex items-center justify-center">
      <ErrorState
        title="Something went wrong"
        message="An unexpected error occurred. Please try again."
        onRetry={reset}
        showHomeLink={false}
      />
    </div>
  );
}
