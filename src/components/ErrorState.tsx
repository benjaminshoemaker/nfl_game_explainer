'use client';

import Link from 'next/link';
import styles from './StateScreens.module.css';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  showHomeLink?: boolean;
  hint?: string;
}

export function ErrorState({
  title = 'Something went wrong',
  message = 'We encountered an error loading this content. Please try again.',
  onRetry,
  showHomeLink = true,
  hint,
}: ErrorStateProps) {
  return <div className={styles.screen}>
    <header className={styles.header}>GAME<span>/</span>EXPLAINED</header>
    <main className={styles.body}>
      <div className={styles.kicker}>Data unavailable</div>
      <h1>{title}</h1>
      <p>{message}</p>
      <div className={styles.actions}>
        {onRetry && <button onClick={onRetry}>Try again</button>}
        {showHomeLink && <Link href="/">Back to games</Link>}
      </div>
      {hint && <p className={styles.hint}>{hint}</p>}
    </main>
  </div>;
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
