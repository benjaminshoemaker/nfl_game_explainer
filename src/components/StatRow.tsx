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
    <>
      {/* Desktop Layout (md and up) */}
      <div
        className={`
          hidden md:grid gap-3 py-5 border-b border-border-subtle last:border-b-0 relative overflow-hidden
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
            className="absolute font-display text-6xl opacity-[0.04] pointer-events-none leading-none top-1/2 -translate-y-1/2"
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
            className="font-display text-3xl leading-none"
            style={{ color: getNumberColor('away', winner) }}
          >
            {displayAway}
          </span>
        </div>

        {/* Away Advantage */}
        <div className="flex items-end justify-end relative z-[2]">
          {winner === 'away' && (
            <div className="flex items-center gap-1 cursor-help" title={tooltip}>
              <span
                className="text-xl tracking-wider"
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
            <div className="absolute left-1/2 -translate-x-1/2 -top-[6px] -bottom-[6px] w-[2px] rounded-[1px] bg-text-primary opacity-40 z-[3]" />
            <div
              className="h-full rounded-l-[5px] transition-all duration-600"
              style={{ width: `${pctAway}%`, ...getBarStyle('away', winner) }}
            />
            <div
              className="h-full rounded-r-[5px] transition-all duration-600"
              style={{ width: `${pctHome}%`, ...getBarStyle('home', winner) }}
            />
          </div>
        </div>

        {/* Home Advantage */}
        <div className="flex items-end justify-start relative z-[2]">
          {winner === 'home' && (
            <div className="flex items-center gap-1 cursor-help" title={tooltip}>
              <span
                className="text-xl tracking-wider"
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
            className="font-display text-3xl leading-none"
            style={{ color: getNumberColor('home', winner) }}
          >
            {displayHome}
          </span>
        </div>
      </div>

      {/* Mobile Layout (below md) */}
      <div
        className={`
          md:hidden grid py-4 border-b border-border-subtle last:border-b-0 relative overflow-hidden
          transition-colors duration-200 min-h-[88px]
          ${clickable ? 'cursor-pointer -mx-4 px-4 active:bg-bg-hover' : ''}
          ${selected ? 'bg-bg-hover border-l-[3px] !pl-[calc(1rem-3px)]' : ''}
        `}
        style={{
          gridTemplateColumns: '55px 1fr 55px',
          gridTemplateRows: 'auto auto auto',
          gap: '0.25rem 0.5rem',
          borderLeftColor: selected ? homeSecondary : 'transparent',
        }}
        onClick={clickable ? onClick : undefined}
        data-winner={winner}
      >
        {/* Watermark - centered on mobile */}
        {winner !== 'even' && (
          <span
            className="absolute font-display text-4xl opacity-[0.06] pointer-events-none leading-none top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
            style={{ color: winner === 'away' ? awaySecondary : homeSecondary }}
          >
            {winner === 'away' ? awayAbbr : homeAbbr}
          </span>
        )}

        {/* Away Value - Column 1, Rows 1-2 */}
        <div
          className="flex flex-col items-center justify-center relative z-[2]"
          style={{ gridColumn: 1, gridRow: '1 / 3' }}
        >
          <span
            className="font-condensed text-[0.6rem] font-semibold uppercase tracking-wider mb-0.5"
            style={{ color: awayTextColor, opacity: winner === 'away' ? 1 : 0.6 }}
          >
            {awayAbbr}
          </span>
          <span
            className="font-display text-xl leading-none"
            style={{
              color: getNumberColor('away', winner),
              textShadow: winner === 'away' ? `0 0 12px ${awaySecondary}` : 'none',
            }}
          >
            {displayAway}
          </span>
        </div>

        {/* Label - Column 2, Row 1 */}
        <div
          className="flex justify-center items-center relative z-[1]"
          style={{ gridColumn: 2, gridRow: 1 }}
        >
          <span className="font-condensed text-[0.65rem] font-semibold uppercase tracking-wider text-center">
            <span className="text-text-primary">{label}</span>
            <span className="text-text-muted ml-1.5 text-[0.6rem]">{description}</span>
          </span>
        </div>

        {/* Bar - Column 2, Row 2 */}
        <div
          className="relative flex h-[8px] bg-bg-deep rounded overflow-visible"
          style={{ gridColumn: 2, gridRow: 2 }}
        >
          <div className="absolute left-1/2 -translate-x-1/2 -top-1 -bottom-1 w-[2px] rounded-sm bg-text-primary opacity-50 z-[3]" />
          <div
            className="h-full rounded-l transition-all duration-600"
            style={{ width: `${pctAway}%`, ...getBarStyle('away', winner) }}
          />
          <div
            className="h-full rounded-r transition-all duration-600"
            style={{ width: `${pctHome}%`, ...getBarStyle('home', winner) }}
          />
        </div>

        {/* Diamonds - Column 2, Row 3 */}
        {winner !== 'even' && (
          <div
            className="flex justify-center pt-1 relative z-[1]"
            style={{ gridColumn: 2, gridRow: 3 }}
          >
            <span
              className="text-sm tracking-wider"
              style={{
                color: winner === 'away' ? awayTextColor : homeTextColor,
                textShadow: `0 0 8px ${winner === 'away' ? awayTextColor : homeTextColor}`,
              }}
            >
              {diamonds}
            </span>
          </div>
        )}

        {/* Home Value - Column 3, Rows 1-2 */}
        <div
          className="flex flex-col items-center justify-center relative z-[2]"
          style={{ gridColumn: 3, gridRow: '1 / 3' }}
        >
          <span
            className="font-condensed text-[0.6rem] font-semibold uppercase tracking-wider mb-0.5"
            style={{ color: homeTextColor, opacity: winner === 'home' ? 1 : 0.6 }}
          >
            {homeAbbr}
          </span>
          <span
            className="font-display text-xl leading-none"
            style={{
              color: getNumberColor('home', winner),
              textShadow: winner === 'home' ? `0 0 12px ${homeSecondary}` : 'none',
            }}
          >
            {displayHome}
          </span>
        </div>
      </div>
    </>
  );
}
