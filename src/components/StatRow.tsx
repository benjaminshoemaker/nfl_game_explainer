'use client';

interface StatRowProps {
  label: string;
  sublabel?: string;
  awayValue: number | string;
  homeValue: number | string;
  awayColor: string;
  homeColor: string;
  lowerIsBetter?: boolean;
  isPercentage?: boolean;
}

function formatValue(value: number | string, isPercentage?: boolean): string {
  if (typeof value === 'string') return value;
  if (isPercentage) return `${(value * 100).toFixed(1)}%`;
  return value.toFixed(value % 1 === 0 ? 0 : 2);
}

function getNumericValue(value: number | string): number {
  if (typeof value === 'number') return value;
  // Try to parse string values like "Own 32" -> 32
  const match = value.match(/(\d+)/);
  return match ? parseFloat(match[1]) : 0;
}

function calculateStrength(awayNum: number, homeNum: number): { diamonds: string; glowColor: string; winner: 'away' | 'home' | 'tie' } {
  const total = Math.abs(awayNum) + Math.abs(homeNum);
  if (total === 0) return { diamonds: '·', glowColor: '', winner: 'tie' };

  const diff = Math.abs(awayNum - homeNum);
  const percentDiff = diff / (total / 2);

  let diamonds: string;
  if (percentDiff > 0.30) diamonds = '◆◆◆';
  else if (percentDiff > 0.15) diamonds = '◆◆';
  else if (percentDiff > 0.05) diamonds = '◆';
  else diamonds = '·';

  const winner = awayNum > homeNum ? 'away' : homeNum > awayNum ? 'home' : 'tie';

  return { diamonds, glowColor: '', winner };
}

export function StatRow({
  label,
  sublabel,
  awayValue,
  homeValue,
  awayColor,
  homeColor,
  lowerIsBetter = false,
  isPercentage = false,
}: StatRowProps) {
  const awayNum = getNumericValue(awayValue);
  const homeNum = getNumericValue(homeValue);

  // Determine winner (accounting for lowerIsBetter)
  let awayIsWinner: boolean;
  let homeIsWinner: boolean;

  if (lowerIsBetter) {
    awayIsWinner = awayNum < homeNum;
    homeIsWinner = homeNum < awayNum;
  } else {
    awayIsWinner = awayNum > homeNum;
    homeIsWinner = homeNum > awayNum;
  }

  const { diamonds, winner } = calculateStrength(
    lowerIsBetter ? -awayNum : awayNum,
    lowerIsBetter ? -homeNum : homeNum
  );

  // Calculate bar widths (proportional to values)
  const maxVal = Math.max(awayNum, homeNum, 1);
  const awayWidth = (awayNum / maxVal) * 50;
  const homeWidth = (homeNum / maxVal) * 50;

  const glowColor = awayIsWinner ? awayColor : homeIsWinner ? homeColor : '';

  return (
    <div className="py-3 border-b border-border-subtle last:border-b-0">
      {/* Label row */}
      <div className="flex items-center justify-between mb-2">
        <span
          className={`font-body text-sm ${awayIsWinner ? 'text-text-primary font-semibold' : 'text-text-muted'}`}
        >
          {formatValue(awayValue, isPercentage)}
        </span>

        <div className="flex items-center gap-2">
          <span className="font-condensed text-xs text-text-secondary uppercase tracking-wider">
            {label}
          </span>
          {sublabel && (
            <span className="font-condensed text-xs text-text-muted">
              ({sublabel})
            </span>
          )}
        </div>

        <span
          className={`font-body text-sm ${homeIsWinner ? 'text-text-primary font-semibold' : 'text-text-muted'}`}
        >
          {formatValue(homeValue, isPercentage)}
        </span>
      </div>

      {/* Tug-of-war bar */}
      <div className="relative h-2 bg-bg-elevated rounded-full overflow-hidden">
        {/* Center line */}
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-border-medium -translate-x-1/2 z-10" />

        {/* Away bar (grows from center to left) */}
        <div
          className="absolute right-1/2 top-0 bottom-0 rounded-l-full transition-all duration-300"
          style={{
            width: `${awayWidth}%`,
            backgroundColor: awayIsWinner ? awayColor : `${awayColor}40`,
          }}
        />

        {/* Home bar (grows from center to right) */}
        <div
          className="absolute left-1/2 top-0 bottom-0 rounded-r-full transition-all duration-300"
          style={{
            width: `${homeWidth}%`,
            backgroundColor: homeIsWinner ? homeColor : `${homeColor}40`,
          }}
        />
      </div>

      {/* Strength indicator */}
      <div className="flex justify-end mt-1">
        <span
          className="text-xs tracking-wider"
          style={{
            color: glowColor || 'var(--text-muted)',
            textShadow: glowColor ? `0 0 8px ${glowColor}` : 'none',
          }}
        >
          {diamonds}
        </span>
      </div>
    </div>
  );
}
