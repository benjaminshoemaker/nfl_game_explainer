import { Suspense } from 'react';
import { WeekProvider } from '@/contexts/WeekContext';
import { GameLayoutShell } from './GameLayoutShell';

interface LayoutProps {
  children: React.ReactNode;
}

export default function GameLayout({ children }: LayoutProps) {
  return (
    <WeekProvider>
      <Suspense fallback={<main className="min-h-screen">{children}</main>}>
        <GameLayoutShell>{children}</GameLayoutShell>
      </Suspense>
    </WeekProvider>
  );
}
