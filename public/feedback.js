/** Build context at activation time so navigation and session changes stay current. */
export function feedbackUrl(page) {
  const url = new URL(page.location.href);
  const gameId = url.pathname.match(/^\/game\/([^/]+)/)?.[1];
  const lines = ['What would you like us to know?', '', '', '---',
    `Page: ${page.document.title}`, `URL: ${url.href}`];
  if (gameId) lines.push(`Game ID: ${gameId}`);
  const season = page.document.querySelector('#season')?.value;
  if (season) lines.push(`Season: ${season}`);
  lines.push(`Time: ${new Date().toISOString()}`);
  // The site's analytics bridge returns IDs only while consent is active.
  // Analytics must never prevent someone from sending feedback.
  try {
    const context = page.nflAnalytics?.headers() || {};
    if (context['X-NFL-ANALYTICS-CONSENT'] === 'yes') {
      const id = context['X-POSTHOG-DISTINCT-ID'];
      const session = context['X-POSTHOG-SESSION-ID'];
      if (typeof id === 'string' && id) lines.push(`PostHog visitor ID: ${id}`);
      if (typeof session === 'string' && session) lines.push(`PostHog session ID: ${session}`);
      const replay = page.nflAnalytics?.replayUrl?.();
      if (typeof replay === 'string' && /^https:\/\//.test(replay)) {
        lines.push(`Session recording (if available): ${replay}`);
      }
    }
  } catch { /* Feedback still works when analytics is blocked or unavailable. */ }
  return `mailto:ben.shoemaker.xyz@gmail.com?subject=${encodeURIComponent('NFL Win Delta feedback' + (gameId ? ` — Game ${gameId}` : ''))}&body=${encodeURIComponent(lines.join('\n'))}`;
}
