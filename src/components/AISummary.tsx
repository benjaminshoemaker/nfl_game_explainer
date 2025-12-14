'use client';

interface AISummaryProps {
  summary: string | null;
  isLoading?: boolean;
}

function SparkleIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
    </svg>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-2 animate-pulse">
      <div className="h-4 bg-bg-elevated rounded w-full" />
      <div className="h-4 bg-bg-elevated rounded w-11/12" />
      <div className="h-4 bg-bg-elevated rounded w-4/5" />
    </div>
  );
}

export function AISummary({ summary, isLoading = false }: AISummaryProps) {
  // Don't render if no summary and not loading
  if (!summary && !isLoading) {
    return null;
  }

  return (
    <div
      className="relative overflow-hidden rounded-2xl bg-bg-card border border-border-subtle"
    >
      {/* Top accent bar */}
      <div
        className="absolute top-0 left-0 right-0 h-[2px]"
        style={{
          background: 'linear-gradient(90deg, var(--away-secondary, #FFC62F), var(--gold), var(--home-secondary, #69BE28))',
        }}
      />

      <div className="relative px-6 py-5">
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <div
            className="w-8 h-8 flex items-center justify-center rounded-lg"
            style={{
              background: 'linear-gradient(135deg, var(--gold) 0%, #f59e0b 100%)',
              boxShadow: '0 4px 12px rgba(251, 191, 36, 0.25)',
            }}
          >
            <SparkleIcon className="w-4 h-4 text-bg-deep" />
          </div>
          <span className="font-condensed text-xs font-semibold uppercase tracking-wider text-gold">
            AI Game Summary
          </span>
        </div>

        {/* Content */}
        {isLoading ? (
          <LoadingSkeleton />
        ) : (
          <p className="font-body text-sm md:text-base leading-relaxed text-text-secondary">
            {summary}
          </p>
        )}
      </div>
    </div>
  );
}
