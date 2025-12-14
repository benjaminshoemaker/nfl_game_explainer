'use client';

export function ScoreboardSkeleton() {
  return (
    <div className="relative w-full overflow-hidden rounded-2xl bg-bg-card animate-pulse">
      <div className="px-4 py-8 md:px-8 md:py-12">
        <div className="flex items-center justify-between">
          {/* Away Team */}
          <div className="flex flex-col items-center gap-3 flex-1">
            <div className="w-16 h-16 md:w-24 md:h-24 rounded-full bg-bg-elevated" />
            <div className="w-12 h-5 rounded bg-bg-elevated" />
          </div>

          {/* Score */}
          <div className="flex flex-col items-center gap-2 flex-shrink-0 px-4">
            <div className="flex items-center gap-4 md:gap-8">
              <div className="w-16 h-12 md:w-20 md:h-16 rounded bg-bg-elevated" />
              <div className="w-6 h-8 rounded bg-bg-elevated" />
              <div className="w-16 h-12 md:w-20 md:h-16 rounded bg-bg-elevated" />
            </div>
            <div className="w-20 h-4 rounded bg-bg-elevated mt-2" />
          </div>

          {/* Home Team */}
          <div className="flex flex-col items-center gap-3 flex-1">
            <div className="w-16 h-16 md:w-24 md:h-24 rounded-full bg-bg-elevated" />
            <div className="w-12 h-5 rounded bg-bg-elevated" />
          </div>
        </div>
      </div>
    </div>
  );
}

export function StatRowSkeleton() {
  return (
    <div className="py-3 border-b border-border-subtle last:border-b-0 animate-pulse">
      <div className="flex items-center justify-between mb-2">
        <div className="w-12 h-4 rounded bg-bg-elevated" />
        <div className="w-24 h-4 rounded bg-bg-elevated" />
        <div className="w-12 h-4 rounded bg-bg-elevated" />
      </div>
      <div className="h-2 rounded-full bg-bg-elevated" />
    </div>
  );
}

export function AdvancedStatsSkeleton() {
  return (
    <div className="bg-bg-card rounded-2xl border border-border-subtle overflow-hidden">
      <div className="px-4 py-3 bg-bg-elevated border-b border-border-subtle">
        <div className="w-32 h-5 rounded bg-bg-card" />
        <div className="w-40 h-3 rounded bg-bg-card mt-2" />
      </div>
      <div className="px-4 py-2">
        {[...Array(8)].map((_, i) => (
          <StatRowSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}

export function PlayListSkeleton() {
  return (
    <div className="bg-bg-card rounded-2xl border border-border-subtle overflow-hidden animate-pulse">
      <div className="px-4 py-3 bg-bg-elevated border-b border-border-subtle">
        <div className="w-24 h-5 rounded bg-bg-card" />
        <div className="w-32 h-3 rounded bg-bg-card mt-2" />
      </div>
      <div className="p-3 border-b border-border-subtle">
        <div className="flex gap-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="w-24 h-8 rounded-lg bg-bg-elevated" />
          ))}
        </div>
      </div>
      <div className="p-4 space-y-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="w-16 h-4 rounded bg-bg-elevated" />
            <div className="w-16 h-5 rounded bg-bg-elevated" />
            <div className="flex-1 h-4 rounded bg-bg-elevated" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function GameCardSkeleton() {
  return (
    <div className="bg-bg-card rounded-xl border border-border-subtle overflow-hidden animate-pulse">
      <div className="p-4">
        <div className="flex items-center gap-3 py-2">
          <div className="w-8 h-8 rounded-full bg-bg-elevated" />
          <div className="flex-1 h-4 rounded bg-bg-elevated" />
          <div className="w-8 h-6 rounded bg-bg-elevated" />
        </div>
        <div className="flex items-center gap-3 py-2">
          <div className="w-8 h-8 rounded-full bg-bg-elevated" />
          <div className="flex-1 h-4 rounded bg-bg-elevated" />
          <div className="w-8 h-6 rounded bg-bg-elevated" />
        </div>
      </div>
      <div className="px-4 py-2 border-t border-border-subtle bg-bg-elevated">
        <div className="w-20 h-3 rounded bg-bg-card" />
      </div>
    </div>
  );
}

export function AISummarySkeleton() {
  return (
    <div className="bg-bg-card rounded-2xl border border-border-subtle overflow-hidden animate-pulse">
      <div className="p-5 pl-6">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-4 h-4 rounded bg-bg-elevated" />
          <div className="w-20 h-3 rounded bg-bg-elevated" />
        </div>
        <div className="space-y-2">
          <div className="h-4 rounded bg-bg-elevated w-full" />
          <div className="h-4 rounded bg-bg-elevated w-11/12" />
          <div className="h-4 rounded bg-bg-elevated w-4/5" />
        </div>
      </div>
    </div>
  );
}

export function FullPageLoading() {
  return (
    <div className="min-h-screen bg-bg-deep flex items-center justify-center">
      <div className="text-center space-y-4">
        <div className="w-12 h-12 border-4 border-gold border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="font-condensed text-sm uppercase tracking-wider text-text-muted">
          Loading...
        </p>
      </div>
    </div>
  );
}
