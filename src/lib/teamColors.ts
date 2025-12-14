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
 * Get the best text color for a team against a dark background
 */
export function getTeamTextColor(abbr: string, bgColor = '#12121a'): string {
  const teamData = getTeamColors(abbr);
  const primaryContrast = getContrastRatio(teamData.primary, bgColor);

  // For team brand colors, use a lower threshold (2.5:1) to preserve team identity
  const minContrast = 2.5;

  if (primaryContrast >= minContrast) {
    return teamData.primary;
  }
  return teamData.secondary;
}
