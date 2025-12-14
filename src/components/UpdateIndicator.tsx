'use client';

interface UpdateIndicatorProps {
  isLive: boolean;
  isRefreshing: boolean;
  secondsSinceUpdate: number;
}

function formatSecondsAgo(seconds: number): string {
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 120) return '1 min ago';
  return `${Math.floor(seconds / 60)} mins ago`;
}

export function UpdateIndicator({
  isLive,
  isRefreshing,
  secondsSinceUpdate,
}: UpdateIndicatorProps) {
  if (!isLive) {
    return null;
  }

  return (
    <div className="flex items-center justify-center gap-4 py-2 px-4 bg-positive/10 rounded-lg border border-positive/20">
      {/* Live badge */}
      <div className="flex items-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-positive opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-positive" />
        </span>
        <span className="font-condensed text-xs uppercase tracking-wider text-positive font-semibold">
          Live
        </span>
      </div>

      {/* Divider */}
      <div className="w-px h-4 bg-positive/30" />

      {/* Update status */}
      <div className="flex items-center gap-2 text-text-muted">
        {isRefreshing ? (
          <>
            <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <span className="font-condensed text-xs uppercase tracking-wider">
              Updating...
            </span>
          </>
        ) : (
          <>
            <span className="font-condensed text-xs uppercase tracking-wider">
              Updated {formatSecondsAgo(secondsSinceUpdate)}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
