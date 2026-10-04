import type { CanonicalPlay } from '@/types';

export function formatCheckAge(seconds: number): string {
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function latestPlayLabel(play: CanonicalPlay | undefined): string | null {
  if (!play) return null;
  const period = play.quarter == null ? 'period unknown' : play.quarter <= 4 ? `Q${play.quarter}`
    : play.quarter === 5 ? 'OT' : `OT${play.quarter - 4}`;
  return `Latest play: ${period}${play.clock ? ` ${play.clock}` : ''}`;
}

export function playFeedKey(plays: CanonicalPlay[] | undefined): string {
  const last = plays?.[plays.length - 1];
  return `${plays?.length ?? 0}:${last?.id ?? ''}`;
}
