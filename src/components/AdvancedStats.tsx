'use client';

import { AdvancedStats as AdvancedStatsType, TeamMeta } from '@/types';
import { StatRow } from './StatRow';
import { getTeamColors } from '@/lib/teamColors';

interface AdvancedStatsProps {
  stats: AdvancedStatsType[];
  teamMeta: TeamMeta[];
}

interface StatConfig {
  key: keyof AdvancedStatsType;
  label: string;
  sublabel?: string;
  lowerIsBetter?: boolean;
  isPercentage?: boolean;
}

const STAT_CONFIGS: StatConfig[] = [
  { key: 'Turnovers', label: 'Turnovers', sublabel: 'Giveaways', lowerIsBetter: true },
  { key: 'Success Rate', label: 'Success Rate', isPercentage: true },
  { key: 'Explosive Plays', label: 'Explosive Plays', sublabel: '10+ run / 20+ pass' },
  { key: 'Yards Per Play', label: 'Yards Per Play' },
  { key: 'Points Per Trip (Inside 40)', label: 'Points Per Trip', sublabel: 'Inside 40' },
  { key: 'Non-Offensive Points', label: 'Non-Off Points', sublabel: 'D/ST scores' },
  { key: 'Penalty Yards', label: 'Penalty Yards', lowerIsBetter: true },
  { key: 'Total Yards', label: 'Total Yards' },
];

export function AdvancedStats({ stats, teamMeta }: AdvancedStatsProps) {
  const away = teamMeta.find((t) => t.homeAway === 'away');
  const home = teamMeta.find((t) => t.homeAway === 'home');

  if (!away || !home) return null;

  const awayStats = stats.find((s) => s.Team === away.abbr);
  const homeStats = stats.find((s) => s.Team === home.abbr);

  if (!awayStats || !homeStats) return null;

  const awayColors = getTeamColors(away.abbr);
  const homeColors = getTeamColors(home.abbr);

  return (
    <div className="bg-bg-card rounded-2xl border border-border-subtle overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-bg-elevated border-b border-border-subtle">
        <h3 className="font-display text-lg tracking-wide text-text-primary">
          Advanced Stats
        </h3>
        <p className="font-condensed text-xs text-text-muted uppercase tracking-wider mt-1">
          Competitive plays only
        </p>
      </div>

      {/* Stats */}
      <div className="px-4 py-2">
        {STAT_CONFIGS.map((config) => (
          <StatRow
            key={config.key}
            label={config.label}
            sublabel={config.sublabel}
            awayValue={awayStats[config.key] as number | string}
            homeValue={homeStats[config.key] as number | string}
            awayColor={awayColors.primary}
            homeColor={homeColors.primary}
            lowerIsBetter={config.lowerIsBetter}
            isPercentage={config.isPercentage}
          />
        ))}
      </div>

      {/* Team legend */}
      <div className="px-4 py-3 bg-bg-elevated border-t border-border-subtle flex justify-between">
        <div className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: awayColors.primary }}
          />
          <span className="font-condensed text-sm text-text-secondary">{away.abbr}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-condensed text-sm text-text-secondary">{home.abbr}</span>
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: homeColors.primary }}
          />
        </div>
      </div>
    </div>
  );
}
