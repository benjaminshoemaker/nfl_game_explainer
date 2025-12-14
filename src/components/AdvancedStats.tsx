'use client';

import { AdvancedStats as AdvancedStatsType, TeamMeta } from '@/types';
import { StatRow } from './StatRow';
import { getTeamColorVars, parseStatValue, calculateStrength } from '@/lib/teamColors';

interface AdvancedStatsProps {
  stats: AdvancedStatsType[];
  teamMeta: TeamMeta[];
  onStatClick?: (category: string) => void;
  selectedCategory?: string;
}

interface StatConfig {
  key: keyof AdvancedStatsType;
  label: string;
  description: string;
  invertBetter?: boolean;
  isPercentage?: boolean;
  clickable?: boolean;
  dataCategory?: string;
}

const STAT_CONFIGS: StatConfig[] = [
  { key: 'Turnovers', label: 'Turnovers', description: 'Margin', invertBetter: true, clickable: true },
  { key: 'Success Rate', label: 'Success Rate', description: 'Play Success %', isPercentage: true },
  { key: 'Explosive Play Rate', label: 'Explosive Play Rate', description: 'Explosiveness', isPercentage: true, clickable: true, dataCategory: 'Explosive Plays' },
  { key: 'Points Per Trip (Inside 40)', label: 'Points Per Trip', description: 'Finishing Drives', clickable: true },
  { key: 'Ave Start Field Pos', label: 'Ave Start Field Pos', description: 'Field Position' },
  { key: 'Penalty Yards', label: 'Penalty Yards', description: 'Play Clean', invertBetter: true, clickable: true },
  { key: 'Non-Offensive Points', label: 'Non-Offensive Points', description: 'D/ST Points', clickable: true },
];

function FactorPie({ awayCounts, evenCounts, homeCounts, awayColor, homeColor }: {
  awayCounts: number;
  evenCounts: number;
  homeCounts: number;
  awayColor: string;
  homeColor: string;
}) {
  const total = awayCounts + evenCounts + homeCounts;
  if (total === 0) return null;

  const circumference = 2 * Math.PI * 14; // r=14
  const awayPct = (awayCounts / total) * 100;
  const evenPct = (evenCounts / total) * 100;
  const homePct = (homeCounts / total) * 100;

  const awayDash = (awayPct / 100) * circumference;
  const evenDash = (evenPct / 100) * circumference;
  const homeDash = (homePct / 100) * circumference;

  const evenOffset = -awayDash;
  const homeOffset = -(awayDash + evenDash);

  return (
    <svg
      className="w-[70px] h-[70px] flex-shrink-0"
      viewBox="0 0 36 36"
      style={{ transform: 'rotate(-90deg)' }}
    >
      <circle
        r="14"
        cx="18"
        cy="18"
        fill="none"
        stroke={awayColor}
        strokeWidth="8"
        strokeDasharray={`${awayDash} ${circumference}`}
        strokeDashoffset="0"
        className="transition-all duration-600"
      />
      <circle
        r="14"
        cx="18"
        cy="18"
        fill="none"
        stroke="var(--text-muted)"
        strokeWidth="8"
        strokeDasharray={`${evenDash} ${circumference}`}
        strokeDashoffset={evenOffset}
        className="transition-all duration-600"
      />
      <circle
        r="14"
        cx="18"
        cy="18"
        fill="none"
        stroke={homeColor}
        strokeWidth="8"
        strokeDasharray={`${homeDash} ${circumference}`}
        strokeDashoffset={homeOffset}
        className="transition-all duration-600"
      />
    </svg>
  );
}

export function AdvancedStats({ stats, teamMeta, onStatClick, selectedCategory }: AdvancedStatsProps) {
  const away = teamMeta.find((t) => t.homeAway === 'away');
  const home = teamMeta.find((t) => t.homeAway === 'home');

  if (!away || !home) return null;

  const awayStats = stats.find((s) => s.Team === away.abbr);
  const homeStats = stats.find((s) => s.Team === home.abbr);

  if (!awayStats || !homeStats) return null;

  const awayColors = getTeamColorVars(away.abbr);
  const homeColors = getTeamColorVars(home.abbr);

  // Calculate factor counts
  let awayCounts = 0;
  let homeCounts = 0;
  let evenCounts = 0;

  STAT_CONFIGS.forEach((config) => {
    const awayVal = parseStatValue(awayStats[config.key] as number | string);
    const homeVal = parseStatValue(homeStats[config.key] as number | string);
    const { winner } = calculateStrength(awayVal, homeVal, config.invertBetter || false);

    if (winner === 'away') awayCounts++;
    else if (winner === 'home') homeCounts++;
    else evenCounts++;
  });

  return (
    <div className="bg-bg-card rounded-2xl border border-border-subtle overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 bg-bg-elevated border-b border-border-subtle flex items-center justify-between">
        <div className="flex items-center gap-3">
          <svg
            className="w-5 h-5 text-text-muted"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m3 17 6-6 4 4 8-8" />
            <path d="m17 7 4 0 0 4" />
          </svg>
          <h3 className="font-display text-lg tracking-wider text-text-primary">
            ADVANCED ANALYTICS
          </h3>
        </div>
        <span className="font-condensed text-xs text-text-muted uppercase tracking-wider">
          Click to explore plays
        </span>
      </div>

      {/* Stats */}
      <div className="px-6 py-2">
        {STAT_CONFIGS.map((config) => (
          <StatRow
            key={config.key}
            label={config.label}
            description={config.description}
            awayValue={awayStats[config.key] as number | string}
            homeValue={homeStats[config.key] as number | string}
            awayAbbr={away.abbr}
            homeAbbr={home.abbr}
            awayTextColor={awayColors.text}
            homeTextColor={homeColors.text}
            awaySecondary={awayColors.secondary}
            homeSecondary={homeColors.secondary}
            awayPrimary={awayColors.primary}
            homePrimary={homeColors.primary}
            invertBetter={config.invertBetter}
            isPercentage={config.isPercentage}
            clickable={config.clickable}
            selected={selectedCategory === (config.dataCategory || config.key)}
            onClick={config.clickable && onStatClick ? () => onStatClick(config.dataCategory || config.key) : undefined}
          />
        ))}
      </div>

      {/* Factor Summary */}
      <div className="px-6 py-4 bg-bg-elevated border-t border-border-subtle">
        <div className="flex justify-center items-center gap-8">
          <FactorPie
            awayCounts={awayCounts}
            evenCounts={evenCounts}
            homeCounts={homeCounts}
            awayColor={awayColors.text}
            homeColor={homeColors.text}
          />

          <div className="flex gap-8">
            <div className="text-center">
              <span
                className="font-display text-4xl leading-none block"
                style={{ color: awayColors.text }}
              >
                {awayCounts}
              </span>
              <div className="font-condensed text-xs font-semibold uppercase tracking-wider text-text-muted mt-1">
                <span style={{ color: awayColors.text }}>{away.abbr}</span> Factors
              </div>
            </div>

            <div className="text-center">
              <span className="font-display text-4xl leading-none block text-text-muted">
                {evenCounts}
              </span>
              <div className="font-condensed text-xs font-semibold uppercase tracking-wider text-text-muted mt-1">
                Even
              </div>
            </div>

            <div className="text-center">
              <span
                className="font-display text-4xl leading-none block"
                style={{ color: homeColors.text }}
              >
                {homeCounts}
              </span>
              <div className="font-condensed text-xs font-semibold uppercase tracking-wider text-text-muted mt-1">
                <span style={{ color: homeColors.text }}>{home.abbr}</span> Factors
              </div>
            </div>
          </div>
        </div>

        {/* Strength legend */}
        <div className="flex justify-center gap-8 mt-4 font-condensed text-xs font-medium text-text-muted tracking-wider">
          <span>◆◆◆ Dominant</span>
          <span>◆◆ Strong</span>
          <span>◆ Slight</span>
          <span>· Minimal</span>
        </div>
      </div>
    </div>
  );
}
