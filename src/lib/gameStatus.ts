import type { GameStatus } from '@/types';

type EspnStatusType = { state?: string; name?: string; shortDetail?: string; completed?: boolean };

export function gameStatusFromEspn(type: EspnStatusType): GameStatus {
  const marker = `${type.name || ''} ${type.shortDetail || ''}`.toLowerCase();
  if (/cancel(?:ed|led)|abandoned/.test(marker)) return 'canceled';
  if (/postpon|reschedul/.test(marker)) return 'postponed';
  if (/delay|suspend|interrupt/.test(marker)) return 'delayed';
  if (type.state === 'post' || type.completed) return 'final';
  if (type.state === 'in') return 'in-progress';
  return 'pregame';
}

export function isTerminalGame(status: GameStatus): boolean {
  return status === 'final' || status === 'canceled';
}

export function gameStatusLabel(status: GameStatus, detail?: string | null): string {
  if (status === 'pregame') return detail ? `Pregame · ${detail}` : 'Pregame';
  if (status === 'in-progress') return detail || 'Live';
  return detail || status.charAt(0).toUpperCase() + status.slice(1);
}
