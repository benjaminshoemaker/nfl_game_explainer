import { ScoreboardResponse, SeasonType, WeekSelection } from '@/types';
import { DirectoryClient, DirectoryClientFallback } from './DirectoryClient';
import { parseWeekParam } from '@/lib/weekUtils';
import { ESPN_REQUEST_HEADERS } from '@/lib/espnRequest';
import { gameStatusFromEspn } from '@/lib/gameStatus';

// ESPN API URL for direct fetching (bypasses Python API for faster server-side render)
const ESPN_SCOREBOARD_URL = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard';

// Playoff week labels
const PLAYOFF_LABELS: Record<number, string> = {
  1: 'Wild Card',
  2: 'Divisional Round',
  3: 'Conference Championship',
  5: 'Super Bowl',
};

export const dynamic = 'force-dynamic';

interface PageProps {
  searchParams: Promise<{ week?: string }>;
}

function transformEspnGame(event: Record<string, unknown>): ScoreboardResponse['games'][0] {
  const competition = ((event.competitions as unknown[]) || [{}])[0] as Record<string, unknown>;
  const status = (event.status as Record<string, unknown>) || {};
  const statusType = (status.type as Record<string, unknown>) || {};
  const competitors = (competition.competitors as Record<string, unknown>[]) || [];

  let homeTeam = { abbr: '', name: '', score: 0, logo: '', id: '' };
  let awayTeam = { abbr: '', name: '', score: 0, logo: '', id: '' };

  for (const comp of competitors) {
    const team = (comp.team as Record<string, unknown>) || {};
    const teamData = {
      abbr: (team.abbreviation as string) || '',
      name: (team.displayName as string) || '',
      score: parseInt(String(comp.score || 0), 10) || 0,
      logo: (team.logo as string) || '',
      id: (team.id as string) || '',
    };
    if (comp.homeAway === 'home') {
      homeTeam = teamData;
    } else {
      awayTeam = teamData;
    }
  }

  const gameStatus = gameStatusFromEspn(statusType);

  return {
    gameId: (event.id as string) || '',
    status: gameStatus,
    statusDetail: (statusType.shortDetail as string) || '',
    homeTeam,
    awayTeam,
    startTime: gameStatus === 'pregame' || gameStatus === 'postponed' ? (event.date as string) : null,
    isActive: gameStatus === 'in-progress',
  };
}

function getWeekLabel(weekNumber: number, seasonType: SeasonType): string {
  if (seasonType === 3) {
    return PLAYOFF_LABELS[weekNumber] || `Playoff Week ${weekNumber}`;
  }
  return `Week ${weekNumber}`;
}

async function getScoreboard(weekSelection?: WeekSelection | null): Promise<ScoreboardResponse | null> {
  try {
    const url = new URL(ESPN_SCOREBOARD_URL);
    if (weekSelection) {
      // Note: Don't pass 'season' param - ESPN API errors with explicit season but defaults to current season
      url.searchParams.set('seasontype', String(weekSelection.seasonType));
      url.searchParams.set('week', String(weekSelection.weekNumber));
    }

    // Fetch directly from ESPN API for server-side rendering
    // This bypasses our Python API which can have issues with server-to-server calls on Vercel
    const response = await fetch(url.toString(), {
      next: { revalidate: 30 },
      headers: ESPN_REQUEST_HEADERS,
    });

    if (!response.ok) {
      const responseText = await response.text().catch(() => '');
      console.error('Failed to fetch ESPN scoreboard', {
        status: response.status,
        url: url.toString(),
        responseText: responseText.slice(0, 500),
      });
      return null;
    }

    const data = await response.json();
    const weekData = data.week || {};
    const seasonData = data.season || {};
    const events = data.events || [];

    const seasonType = (seasonData.type || 2) as SeasonType;
    const weekNumber = weekData.number || 0;

    const games = events.map(transformEspnGame);

    return {
      week: {
        number: weekNumber,
        label: getWeekLabel(weekNumber, seasonType),
        seasonType,
      },
      games,
    };
  } catch (error) {
    console.error('Error fetching scoreboard:', error);
    return null;
  }
}

export default async function Home({ searchParams }: PageProps) {
  const params = await searchParams;
  const weekSelection = parseWeekParam(params.week);
  const scoreboard = await getScoreboard(weekSelection);

  if (!scoreboard) return <DirectoryClientFallback />;
  return <DirectoryClient initialData={scoreboard} />;
}

export const metadata = {
  title: 'NFL Game Explainer | Live Game Analysis',
  description: 'Real-time NFL game analysis with advanced statistics, win probability tracking, and AI-powered game summaries.',
};
