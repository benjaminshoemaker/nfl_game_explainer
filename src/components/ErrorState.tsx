'use client';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  showHomeLink?: boolean;
}

export function ErrorState({
  title = 'Something went wrong',
  message = 'We encountered an error loading this content. Please try again.',
  onRetry,
  showHomeLink = true,
}: ErrorStateProps) {
  return (
    <div className="flex items-center justify-center min-h-[400px] p-6">
      <div className="text-center space-y-4 max-w-md">
        <div className="w-16 h-16 rounded-full bg-negative/20 flex items-center justify-center mx-auto">
          <svg
            className="w-8 h-8 text-negative"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        <h2 className="font-display text-2xl tracking-wide text-text-primary">
          {title}
        </h2>

        <p className="font-body text-text-secondary leading-relaxed">
          {message}
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
          {onRetry && (
            <button
              onClick={onRetry}
              className="px-6 py-2 bg-gold text-bg-deep font-condensed uppercase tracking-wider rounded-lg hover:bg-gold/90 transition-colors"
            >
              Try Again
            </button>
          )}
          {showHomeLink && (
            <a
              href="/"
              className="px-6 py-2 border border-border-medium text-text-secondary font-condensed uppercase tracking-wider rounded-lg hover:border-border-strong hover:text-text-primary transition-colors"
            >
              Back to Games
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

export function NetworkError({ onRetry }: { onRetry?: () => void }) {
  return (
    <ErrorState
      title="Connection Error"
      message="Unable to connect to the server. Please check your internet connection and try again."
      onRetry={onRetry}
    />
  );
}

export function NotFoundError({ gameId }: { gameId?: string }) {
  return (
    <ErrorState
      title="Game Not Found"
      message={
        gameId
          ? `We couldn't find a game with ID: ${gameId}. It may have been removed or the ID might be incorrect.`
          : "We couldn't find the game you're looking for."
      }
      showHomeLink={true}
    />
  );
}

export function APIError({ onRetry }: { onRetry?: () => void }) {
  return (
    <ErrorState
      title="Data Unavailable"
      message="We're having trouble loading game data right now. This is usually temporary. Please try again in a moment."
      onRetry={onRetry}
    />
  );
}
