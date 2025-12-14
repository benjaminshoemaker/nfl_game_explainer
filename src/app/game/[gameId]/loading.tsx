import {
  ScoreboardSkeleton,
  AdvancedStatsSkeleton,
  PlayListSkeleton,
  AISummarySkeleton,
} from '@/components/LoadingStates';

export default function GameLoading() {
  return (
    <div className="min-h-screen bg-bg-deep">
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        <ScoreboardSkeleton />
        <AISummarySkeleton />
        <AdvancedStatsSkeleton />
        <PlayListSkeleton />
      </div>
    </div>
  );
}
