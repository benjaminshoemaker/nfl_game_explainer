import { ScoreboardResponse, SeasonType, WeekSelection } from '@/types';
import { DirectoryClient } from './DirectoryClient';
import { parseWeekParam } from '@/lib/weekUtils';

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

const ESPN_REQUEST_HEADERS = {
  // ESPN frequently blocks/behaves differently for non-browser UAs.
  'user-agent':
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  accept: 'application/json, text/plain, */*',
  'accept-language': 'en-US,en;q=0.9',
  referer: 'https://www.espn.com/',
  origin: 'https://www.espn.com',
};

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

  const state = (statusType.state as string) || 'pre';
  let gameStatus: 'in-progress' | 'final' | 'pregame' = 'pregame';
  if (state === 'in') gameStatus = 'in-progress';
  else if (state === 'post') gameStatus = 'final';

  return {
    gameId: (event.id as string) || '',
    status: gameStatus,
    statusDetail: (statusType.shortDetail as string) || '',
    homeTeam,
    awayTeam,
    startTime: gameStatus === 'pregame' ? (event.date as string) : null,
    isActive: state === 'in',
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

    // Sort: in-progress first, then pregame by time, then final
    games.sort((a: ScoreboardResponse['games'][0], b: ScoreboardResponse['games'][0]) => {
      if (a.status === 'in-progress' && b.status !== 'in-progress') return -1;
      if (a.status !== 'in-progress' && b.status === 'in-progress') return 1;
      if (a.status === 'pregame' && b.status === 'pregame') {
        return (a.startTime || '').localeCompare(b.startTime || '');
      }
      if (a.status === 'pregame') return -1;
      if (b.status === 'pregame') return 1;
      return 0;
    });

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

function EmptyState() {
  return (
    <div className="container mx-auto px-6 py-12">
      <div className="text-center">
        <h1 className="font-display text-5xl tracking-wide text-text-primary mb-4">
          NFL Game Explainer
        </h1>
        <p className="font-condensed text-xl text-text-secondary uppercase tracking-wider mb-8">
          Live Game Analysis Dashboard
        </p>
      </div>

      <div className="max-w-md mx-auto">
        <div className="bg-bg-card border border-border-subtle rounded-2xl p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-gold/20 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="font-display text-2xl tracking-wide text-text-primary mb-3">
            No Games Today
          </h2>
          <p className="font-body text-text-secondary leading-relaxed">
            Check back during game days for live analysis, advanced statistics, and AI-powered game summaries.
          </p>
        </div>
      </div>
    </div>
  );
}

export default async function Home({ searchParams }: PageProps) {
  const params = await searchParams;
  const weekSelection = parseWeekParam(params.week);
  const scoreboard = await getScoreboard(weekSelection);

  if (!scoreboard || scoreboard.games.length === 0) {
    return <EmptyState />;
  }

  return <DirectoryClient initialData={scoreboard} />;
}

export const metadata = {
  title: 'NFL Game Explainer | Live Game Analysis',
  description: 'Real-time NFL game analysis with advanced statistics, win probability tracking, and AI-powered game summaries.',
};
