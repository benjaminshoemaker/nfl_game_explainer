'use client';

import {
  calculateStrength,
  getStrengthDiamonds,
  getStrengthLabel,
  parseStatValue,
  formatStatValue,
  type Winner,
} from '@/lib/teamColors';

interface StatRowProps {
  label: string;
  description: string;
  awayValue: number | string;
  homeValue: number | string;
  awayAbbr: string;
  homeAbbr: string;
  awayTextColor: string;
  homeTextColor: string;
  awaySecondary: string;
  homeSecondary: string;
  awayPrimary: string;
  homePrimary: string;
  invertBetter?: boolean;
  isPercentage?: boolean;
  clickable?: boolean;
  selected?: boolean;
  onClick?: () => void;
}

export function StatRow({
  label,
  description,
  awayValue,
  homeValue,
  awayAbbr,
  homeAbbr,
  awayTextColor,
  homeTextColor,
  awaySecondary,
  homeSecondary,
  awayPrimary,
  homePrimary,
  invertBetter = false,
  isPercentage = false,
  clickable = false,
  selected = false,
  onClick,
}: StatRowProps) {
  const numAway = parseStatValue(awayValue);
  const numHome = parseStatValue(homeValue);
  const total = numAway + numHome;

  const pctAway = total > 0 ? (numAway / total) * 100 : 50;
  const pctHome = total > 0 ? (numHome / total) * 100 : 50;

  const displayAway = formatStatValue(awayValue, isPercentage);
  const displayHome = formatStatValue(homeValue, isPercentage);

  const { winner, strength, pctDiff } = calculateStrength(numAway, numHome, invertBetter);
  const diamonds = getStrengthDiamonds(strength);
  const strengthLabel = getStrengthLabel(strength);

  const tooltip = winner !== 'even'
    ? `${winner === 'away' ? awayAbbr : homeAbbr} · ${strengthLabel} · ${(pctDiff * 100).toFixed(0)}% difference`
    : '';

  // Dynamic styles based on winner
  const getBarStyle = (side: 'away' | 'home', winnerSide: Winner) => {
    if (winnerSide === 'even') {
      return { background: 'rgba(255,255,255,0.18)' };
    }
    if (side === winnerSide) {
      // Winner gets team gradient
      if (side === 'away') {
        return { background: `linear-gradient(90deg, ${awayPrimary}, ${awaySecondary})` };
      }
      return { background: `linear-gradient(90deg, ${homeSecondary}, ${homePrimary})` };
    }
    // Loser is muted grey
    return { background: 'rgba(255,255,255,0.18)' };
  };

  const getNumberColor = (side: 'away' | 'home', winnerSide: Winner) => {
    if (winnerSide === 'even') return 'var(--text-muted)';
    if (side === winnerSide) {
      return side === 'away' ? awayTextColor : homeTextColor;
    }
    return 'var(--text-muted)';
  };

  return (
    <div
      className={`
        grid gap-3 py-5 border-b border-border-subtle last:border-b-0 relative overflow-hidden
        transition-colors duration-200
        ${clickable ? 'cursor-pointer -mx-6 px-6 hover:bg-bg-hover' : ''}
        ${selected ? 'bg-bg-hover border-l-[3px] !pl-[calc(1.5rem-3px)]' : ''}
      `}
      style={{
        gridTemplateColumns: '70px minmax(80px, auto) 1fr minmax(80px, auto) 70px',
        borderLeftColor: selected ? homeSecondary : 'transparent',
      }}
      onClick={clickable ? onClick : undefined}
      data-winner={winner}
    >
      {/* Watermark */}
      {winner !== 'even' && (
        <span
          className="absolute font-display text-5xl md:text-6xl opacity-[0.04] pointer-events-none leading-none top-1/2 -translate-y-1/2"
          style={{
            color: winner === 'away' ? awaySecondary : homeSecondary,
            left: winner === 'away' ? (clickable ? 'calc(70px + 1.5rem)' : '70px') : 'auto',
            right: winner === 'home' ? (clickable ? 'calc(70px + 1.5rem)' : '70px') : 'auto',
          }}
        >
          {winner === 'away' ? awayAbbr : homeAbbr}
        </span>
      )}

      {/* Away Value */}
      <div className="text-right relative z-[2]">
        <span
          className="font-display text-2xl md:text-3xl leading-none"
          style={{ color: getNumberColor('away', winner) }}
        >
          {displayAway}
        </span>
      </div>

      {/* Away Advantage */}
      <div className="flex items-end justify-end relative z-[2]">
        {winner === 'away' && (
          <div
            className="flex items-center gap-1 cursor-help"
            title={tooltip}
          >
            <span
              className="text-lg md:text-xl tracking-wider"
              style={{
                color: awayTextColor,
                textShadow: `0 0 10px ${awayTextColor}`,
              }}
            >
              {diamonds}
            </span>
          </div>
        )}
      </div>

      {/* Center - Label and Bar */}
      <div className="flex flex-col gap-2 relative z-[1]">
        <div className="flex justify-start">
          <span className="font-condensed text-xs font-semibold uppercase tracking-wider text-text-muted">
            <span className="text-text-primary">{label}</span>
            {description && <span className="text-text-muted ml-2">{description}</span>}
            {clickable && (
              <svg
                className={`inline-block ml-2 w-3 h-3 transition-opacity duration-200 ${selected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
                style={{ color: selected ? homeSecondary : 'currentColor' }}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="m9 18 6-6-6-6" />
              </svg>
            )}
          </span>
        </div>

        {/* Tug-of-war bar */}
        <div className="relative flex h-[10px] bg-bg-deep rounded-[5px] overflow-visible">
          {/* Center line */}
          <div
            className="absolute left-1/2 -translate-x-1/2 -top-[6px] -bottom-[6px] w-[2px] rounded-[1px] bg-text-primary opacity-40 z-[3]"
          />

          {/* Away bar */}
          <div
            className="h-full rounded-l-[5px] transition-all duration-600"
            style={{
              width: `${pctAway}%`,
              ...getBarStyle('away', winner),
            }}
          />

          {/* Home bar */}
          <div
            className="h-full rounded-r-[5px] transition-all duration-600"
            style={{
              width: `${pctHome}%`,
              ...getBarStyle('home', winner),
            }}
          />
        </div>
      </div>

      {/* Home Advantage */}
      <div className="flex items-end justify-start relative z-[2]">
        {winner === 'home' && (
          <div
            className="flex items-center gap-1 cursor-help"
            title={tooltip}
          >
            <span
              className="text-lg md:text-xl tracking-wider"
              style={{
                color: homeTextColor,
                textShadow: `0 0 10px ${homeTextColor}`,
              }}
            >
              {diamonds}
            </span>
          </div>
        )}
      </div>

      {/* Home Value */}
      <div className="text-left relative z-[2]">
        <span
          className="font-display text-2xl md:text-3xl leading-none"
          style={{ color: getNumberColor('home', winner) }}
        >
          {displayHome}
        </span>
      </div>
    </div>
  );
}
