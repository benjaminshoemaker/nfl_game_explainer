export type AnalyticsProperties = Record<string, string | number | boolean>;
declare global {
  interface Window {
    nflAnalytics?: {
      capture: (event: string, properties?: AnalyticsProperties) => void;
      headers: () => Record<string, string>;
    };
  }
}
export function analyticsHeaders(): Record<string, string> {
  return typeof window === 'undefined' ? {} : window.nflAnalytics?.headers() || {};
}
export function track(event: string, properties: AnalyticsProperties = {}) {
  if (typeof window !== 'undefined') window.nflAnalytics?.capture(event, properties);
}

// Only standalone team routes use hashes as pages. Game section anchors are not visits.
export function analyticsPage(url: URL) {
  let path = url.pathname.replace(/\/$/, '') || '/';
  if (/^\/(teams|power-rankings|team-methodology|prediction-results|team-seasons\.html)(\/|$)/.test(path)) {
    const hash = url.hash.slice(1);
    if (/^team\/[A-Z0-9]{2,4}$/i.test(hash)) path = '/teams/' + hash.slice(5).toUpperCase();
    else if (hash === 'teams') path = '/teams';
    else if (hash === 'power') path = '/power-rankings';
    else if (hash === 'results') path = '/power-rankings/prediction-results';
    else if (hash === 'method') path = '/team-methodology';
  }
  const page_type = /^\/game\/\d+$/.test(path) ? 'game_report'
    : /^\/teams\/[A-Z0-9]+$/i.test(path) ? 'team'
      : path === '/power-rankings' ? 'rankings'
        : path.includes('prediction-results') ? 'prediction_results'
          : path === '/teams' ? 'team_directory' : path === '/' ? 'game_directory' : 'other';
  return { path, page_type };
}
