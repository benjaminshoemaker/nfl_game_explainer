'use client';

interface Tab {
  id: string;
  label: string;
  count?: number;
}

interface PlayTabsProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
}

export function PlayTabs({ tabs, activeTab, onTabChange }: PlayTabsProps) {
  return (
    <div className="flex gap-1 p-1 bg-bg-elevated rounded-lg overflow-x-auto">
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-md
              font-condensed text-sm uppercase tracking-wider
              transition-all duration-200
              whitespace-nowrap
              ${
                isActive
                  ? 'bg-bg-card text-text-primary shadow-md'
                  : 'text-text-muted hover:text-text-secondary hover:bg-bg-card/50'
              }
            `}
          >
            <span>{tab.label}</span>
            {tab.count !== undefined && (
              <span
                className={`
                  px-1.5 py-0.5 rounded text-xs
                  ${isActive ? 'bg-gold/20 text-gold' : 'bg-border-subtle text-text-muted'}
                `}
              >
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
