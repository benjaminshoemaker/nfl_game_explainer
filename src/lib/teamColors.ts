export interface TeamColors {
  primary: string;
  secondary: string;
  logo: string;
}

export const TEAM_DATA: Record<string, TeamColors> = {
  ARI: { primary: '#97233F', secondary: '#FFB612', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/ari.png' },
  ATL: { primary: '#A71930', secondary: '#A5ACAF', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/atl.png' },
  BAL: { primary: '#241773', secondary: '#9E7C0C', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/bal.png' },
  BUF: { primary: '#00338D', secondary: '#C60C30', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/buf.png' },
  CAR: { primary: '#0085CA', secondary: '#BFC0BF', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/car.png' },
  CHI: { primary: '#0B162A', secondary: '#C83803', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/chi.png' },
  CIN: { primary: '#FB4F14', secondary: '#000000', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/cin.png' },
  CLE: { primary: '#311D00', secondary: '#FF3C00', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/cle.png' },
  DAL: { primary: '#003594', secondary: '#869397', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/dal.png' },
  DEN: { primary: '#FB4F14', secondary: '#002244', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/den.png' },
  DET: { primary: '#0076B6', secondary: '#B0B7BC', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/det.png' },
  GB: { primary: '#203731', secondary: '#FFB612', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/gb.png' },
  HOU: { primary: '#03202F', secondary: '#A71930', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/hou.png' },
  IND: { primary: '#002C5F', secondary: '#A2AAAD', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/ind.png' },
  JAX: { primary: '#006778', secondary: '#D7A22A', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/jax.png' },
  KC: { primary: '#E31837', secondary: '#FFB81C', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/kc.png' },
  LAC: { primary: '#0080C6', secondary: '#FFC20E', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/lac.png' },
  LAR: { primary: '#003594', secondary: '#FFA300', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/lar.png' },
  LV: { primary: '#000000', secondary: '#A5ACAF', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/lv.png' },
  MIA: { primary: '#008E97', secondary: '#FC4C02', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/mia.png' },
  MIN: { primary: '#4F2683', secondary: '#FFC62F', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/min.png' },
  NE: { primary: '#002244', secondary: '#C60C30', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/ne.png' },
  NO: { primary: '#D3BC8D', secondary: '#101820', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/no.png' },
  NYG: { primary: '#0B2265', secondary: '#A71930', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png' },
  NYJ: { primary: '#125740', secondary: '#000000', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png' },
  PHI: { primary: '#004C54', secondary: '#A5ACAF', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/phi.png' },
  PIT: { primary: '#FFB612', secondary: '#101820', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/pit.png' },
  SEA: { primary: '#002244', secondary: '#4DC3FF', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/sea.png' },
  SF: { primary: '#AA0000', secondary: '#B3995D', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/sf.png' },
  TB: { primary: '#D50A0A', secondary: '#FF7900', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/tb.png' },
  TEN: { primary: '#0C2340', secondary: '#4B92DB', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/ten.png' },
  WAS: { primary: '#5A1414', secondary: '#FFB612', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png' },
  WSH: { primary: '#5A1414', secondary: '#FFB612', logo: 'https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png' },
  default: { primary: '#1a232d', secondary: '#60a5fa', logo: '' }
};

export function getTeamColors(abbr: string): TeamColors {
  return TEAM_DATA[abbr] || TEAM_DATA.default;
}

export function getTeamLogo(abbr: string): string {
  const team = TEAM_DATA[abbr];
  return team?.logo || `https://a.espncdn.com/i/teamlogos/nfl/500/${abbr.toLowerCase()}.png`;
}

/**
 * Calculate relative luminance for WCAG contrast calculations
 */
function getLuminance(hex: string): number {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;

  const toLinear = (c: number) => c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);

  return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
}

/**
 * Calculate contrast ratio between two colors
 */
function getContrastRatio(hex1: string, hex2: string): number {
  const lum1 = getLuminance(hex1);
  const lum2 = getLuminance(hex2);
  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);
  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Lighten a hex color by a percentage
 */
function lightenColor(hex: string, percent: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);

  const newR = Math.min(255, Math.round(r + (255 - r) * percent));
  const newG = Math.min(255, Math.round(g + (255 - g) * percent));
  const newB = Math.min(255, Math.round(b + (255 - b) * percent));

  return `#${newR.toString(16).padStart(2, '0')}${newG.toString(16).padStart(2, '0')}${newB.toString(16).padStart(2, '0')}`;
}

/**
 * Get the best text color for a team against a dark background.
 * Ensures high visibility by enforcing strong contrast requirements.
 */
export function getTeamTextColor(abbr: string, bgColor = '#12121a'): string {
  const teamData = getTeamColors(abbr);

  // High contrast threshold for excellent readability on dark backgrounds
  const minContrast = 5.5;

  const primaryContrast = getContrastRatio(teamData.primary, bgColor);
  const secondaryContrast = getContrastRatio(teamData.secondary, bgColor);

  // Prefer primary color if it meets threshold
  if (primaryContrast >= minContrast) {
    return teamData.primary;
  }

  // Fall back to secondary if it meets threshold
  if (secondaryContrast >= minContrast) {
    return teamData.secondary;
  }

  // If neither meets threshold, aggressively lighten the better-contrasting color
  const bestColor = secondaryContrast > primaryContrast ? teamData.secondary : teamData.primary;

  // Aggressively lighten until we meet the threshold
  for (let i = 1; i <= 8; i++) {
    const lightened = lightenColor(bestColor, i * 0.12);
    if (getContrastRatio(lightened, bgColor) >= minContrast) {
      return lightened;
    }
  }

  // Ultimate fallback: bright white-ish color
  return '#f3f4f6';
}

/**
 * Check if color is too close to green/red (positive/negative indicators)
 */
function isProblematicColor(hex: string): boolean {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  if (g > 150 && g > r * 1.3 && g > b * 1.3) return true;
  if (r > 180 && r > g * 1.5 && r > b * 1.5) return true;
  return false;
}

/**
 * Get safe secondary color (fallback if too close to indicator colors)
 */
export function getSafeSecondary(abbr: string): string {
  const teamData = getTeamColors(abbr);
  if (isProblematicColor(teamData.secondary)) {
    return '#60a5fa';
  }
  return teamData.secondary;
}

/**
 * Get all team color variants for CSS variables
 */
export function getTeamColorVars(abbr: string) {
  const teamData = getTeamColors(abbr);
  return {
    primary: teamData.primary,
    secondary: getSafeSecondary(abbr),
    text: getTeamTextColor(abbr),
    logo: teamData.logo || `https://a.espncdn.com/i/teamlogos/nfl/500/${abbr.toLowerCase()}.png`,
  };
}

// Strength calculation for stat comparisons
export type StrengthLevel = 'dominant' | 'strong' | 'slight' | 'minimal';
export type Winner = 'home' | 'away' | 'even';

export interface StrengthResult {
  winner: Winner;
  strength: StrengthLevel;
  pctDiff: number;
}

export function calculateStrength(numAway: number, numHome: number, invertBetter: boolean): StrengthResult {
  if (numAway === numHome) return { winner: 'even', strength: 'minimal', pctDiff: 0 };

  const avg = (Math.abs(numAway) + Math.abs(numHome)) / 2;
  const pctDiff = avg > 0 ? Math.abs(numAway - numHome) / avg : 0;

  let winner: Winner;
  if (invertBetter) {
    winner = numAway < numHome ? 'away' : 'home';
  } else {
    winner = numAway > numHome ? 'away' : 'home';
  }

  let strength: StrengthLevel;
  if (pctDiff > 0.3) strength = 'dominant';
  else if (pctDiff > 0.15) strength = 'strong';
  else if (pctDiff > 0.05) strength = 'slight';
  else strength = 'minimal';

  return { winner, strength, pctDiff };
}

export function getStrengthDiamonds(strength: StrengthLevel): string {
  switch (strength) {
    case 'dominant': return '◆◆◆';
    case 'strong': return '◆◆';
    case 'slight': return '◆';
    default: return '·';
  }
}

export function getStrengthLabel(strength: StrengthLevel): string {
  switch (strength) {
    case 'dominant': return 'Dominant advantage';
    case 'strong': return 'Strong advantage';
    case 'slight': return 'Slight advantage';
    default: return 'Minimal advantage';
  }
}

/**
 * Parse field position value (e.g., "Own 28" -> 28)
 */
export function parseStatValue(val: string | number): number {
  if (typeof val === 'string' && val.includes('Own')) {
    return parseInt(val.replace('Own', '').trim());
  }
  return parseFloat(String(val));
}

/**
 * Format stat value (percentage handling)
 */
export function formatStatValue(val: string | number, isPercentage: boolean): string {
  if (!isPercentage) return String(val);
  const num = parseFloat(String(val));
  if (isNaN(num)) return String(val);
  return (num * 100).toFixed(1) + '%';
}
