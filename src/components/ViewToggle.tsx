'use client';

type ViewMode = 'competitive' | 'full';

interface ViewToggleProps {
  value: ViewMode;
  onChange: (value: ViewMode) => void;
  showIndicator?: boolean;
}

export function ViewToggle({ value, onChange, showIndicator = true }: ViewToggleProps) {
  const options: { value: ViewMode; label: string }[] = [
    { value: 'competitive', label: 'Competitive' },
    { value: 'full', label: 'Full Game' },
  ];

  return (
    <div className="flex flex-col gap-2">
      <div className="flex p-0.5 bg-bg-elevated rounded-lg">
        {options.map((option) => {
          const isActive = value === option.value;
          return (
            <button
              key={option.value}
              onClick={() => onChange(option.value)}
              className={`
                px-3 py-1.5 rounded-md
                font-condensed text-xs uppercase tracking-wider
                transition-all duration-200
                ${
                  isActive
                    ? 'bg-bg-card text-text-primary shadow-sm'
                    : 'text-text-muted hover:text-text-secondary'
                }
              `}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      {/* Filter indicator */}
      {showIndicator && value === 'competitive' && (
        <p className="font-condensed text-xs text-text-muted">
          Stats reflect competitive plays only (WP &lt; 97.5%)
        </p>
      )}
    </div>
  );
}
