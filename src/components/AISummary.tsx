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
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M12 2L13.09 8.26L18 6L14.74 10.91L21 12L14.74 13.09L18 18L13.09 15.74L12 22L10.91 15.74L6 18L9.26 13.09L3 12L9.26 10.91L6 6L10.91 8.26L12 2Z" />
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
    <div className="relative bg-bg-card rounded-2xl border border-border-subtle overflow-hidden">
      {/* Animated gradient border effect */}
      <div
        className="absolute inset-0 rounded-2xl opacity-50 pointer-events-none"
        style={{
          background: 'linear-gradient(135deg, rgba(255,215,0,0.1) 0%, transparent 50%, rgba(96,165,250,0.1) 100%)',
        }}
      />

      {/* Left accent bar */}
      <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-gold via-gold/50 to-accent" />

      <div className="relative p-5 pl-6">
        {/* Header */}
        <div className="flex items-center gap-2 mb-3">
          <SparkleIcon className="w-4 h-4 text-gold" />
          <span className="font-condensed text-xs uppercase tracking-widest text-gold">
            AI Analysis
          </span>
        </div>

        {/* Content */}
        {isLoading ? (
          <LoadingSkeleton />
        ) : (
          <p className="font-body text-base leading-relaxed text-text-primary">
            {summary}
          </p>
        )}
      </div>

      {/* Subtle glow effect at bottom */}
      <div
        className="absolute bottom-0 left-0 right-0 h-px"
        style={{
          background: 'linear-gradient(90deg, transparent, rgba(255,215,0,0.3), transparent)',
        }}
      />
    </div>
  );
}
