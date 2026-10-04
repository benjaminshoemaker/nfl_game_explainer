'use client';

import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { GameSidebarClient } from '@/components/GameSidebarClient';
import styles from './GameLayoutShell.module.css';

export function GameLayoutShell({ children }: { children: React.ReactNode }) {
  const debugMode = useSearchParams().get('debug') === 'true';

  return (
    <div className={styles.shell}>
      {!debugMode && (
        <aside className={styles.sidebar}>
          <GameSidebarClient />
        </aside>
      )}
      <main className={styles.main}>
        {!debugMode && (
          <div className={styles.mobileHeader}>
            <Link href="/">← All games</Link>
            <span>GAME<span>/</span>EXPLAINED</span>
          </div>
        )}
        {children}
      </main>
    </div>
  );
}
