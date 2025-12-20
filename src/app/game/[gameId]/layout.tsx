import { GameSidebarClient } from '@/components/GameSidebarClient';
import { WeekProvider } from '@/contexts/WeekContext';

interface LayoutProps {
  children: React.ReactNode;
}

export default function GameLayout({ children }: LayoutProps) {
  return (
    <WeekProvider>
      <div className="flex min-h-screen">
        {/* Sidebar - hidden on mobile, visible on lg+ */}
        <aside className="hidden lg:block w-64 flex-shrink-0 sticky top-0 h-screen">
          <GameSidebarClient />
        </aside>

        {/* Main content */}
        <main className="flex-1 min-w-0">
          {/* Mobile header with back button */}
          <div className="lg:hidden sticky top-0 z-10 bg-bg-deep/95 backdrop-blur border-b border-border-subtle">
            <div className="flex items-center gap-3 px-4 py-3">
              <a
                href="/"
                className="flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                <span className="font-condensed text-sm uppercase tracking-wider">All Games</span>
              </a>
            </div>
          </div>

          {children}
        </main>
      </div>
    </WeekProvider>
  );
}
