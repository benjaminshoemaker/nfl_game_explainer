import { afterEach, expect, it, vi } from 'vitest';
import posthog from 'posthog-js';

vi.mock('posthog-js', () => ({ default: {
  init: vi.fn(), capture: vi.fn(), opt_in_capturing: vi.fn(), opt_out_capturing: vi.fn(),
  startSessionRecording: vi.fn(), stopSessionRecording: vi.fn(),
  sessionRecordingStarted: vi.fn(() => true),
  get_session_replay_url: vi.fn(() => 'https://us.posthog.com/project/736759/replay/session-id?t=10'),
  get_distinct_id: () => 'browser-id', get_session_id: () => 'session-id',
} }));
const originalPush = history.pushState;
const originalReplace = history.replaceState;
afterEach(() => {
  history.pushState = originalPush; history.replaceState = originalReplace;
  localStorage.clear(); document.body.innerHTML = ''; delete window.nflAnalytics;
  vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.clearAllMocks();
});
async function start() {
  vi.resetModules();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => ({ token: 'test', host: 'https://us.i.posthog.com', testMode: true }) }));
  await (await import('./analytics-browser')).startAnalytics();
  document.dispatchEvent(new Event('DOMContentLoaded'));
}
function click(text: string) {
  const button = [...document.querySelectorAll('button')].find(b => b.textContent === text);
  expect(button).toBeDefined(); button!.click();
}
it('waits for consent, deduplicates refreshes, and stops immediately when revoked', async () => {
  history.replaceState(null, '', '/game/401');
  await start();
  expect(posthog.init).not.toHaveBeenCalled(); expect(posthog.capture).not.toHaveBeenCalled();
  expect(window.nflAnalytics?.headers()).toEqual({});
  expect(window.nflAnalytics?.replayUrl?.()).toBeUndefined();
  expect(posthog.startSessionRecording).not.toHaveBeenCalled();
  click('Allow analytics');
  expect(posthog.init).toHaveBeenCalledTimes(1);
  expect(posthog.init).toHaveBeenCalledWith('test', expect.objectContaining({
    disable_session_recording: false, session_recording: expect.objectContaining({ maskAllInputs: true })
  }));
  expect(window.nflAnalytics?.replayUrl?.()).toContain('/replay/session-id');
  expect(posthog.get_session_replay_url).toHaveBeenCalledWith({ withTimestamp: true, timestampLookBack: 30 });
  expect(posthog.capture).toHaveBeenCalledWith('content_viewed', expect.objectContaining({ page_type: 'game_report', is_test: true }));
  expect(window.nflAnalytics?.headers()['X-NFL-ANALYTICS-CONSENT']).toBe('yes');
  const count = vi.mocked(posthog.capture).mock.calls.length;
  history.replaceState(null, '', '/game/401#drivers');
  expect(posthog.capture).toHaveBeenCalledTimes(count);
  history.pushState(null, '', '/teams/SEA');
  expect(posthog.capture).toHaveBeenCalledTimes(count + 2);
  click('Privacy'); click('No thanks');
  expect(posthog.opt_out_capturing).toHaveBeenCalledTimes(1);
  expect(posthog.stopSessionRecording).toHaveBeenCalledTimes(1);
  expect(window.nflAnalytics?.replayUrl?.()).toBeUndefined();
  expect(window.nflAnalytics?.headers()).toEqual({});
  const stoppedCount = vi.mocked(posthog.capture).mock.calls.length;
  history.pushState(null, '', '/power-rankings');
  expect(posthog.capture).toHaveBeenCalledTimes(stoppedCount);
  click('Privacy'); click('Allow analytics');
  expect(posthog.opt_in_capturing).toHaveBeenCalledTimes(2);
  expect(posthog.startSessionRecording).toHaveBeenCalledTimes(2);
});
it('honors an existing decline without initializing the SDK', async () => {
  localStorage.setItem('nfl-analytics-consent', 'no'); await start();
  expect(document.querySelector('[role=dialog]')).toBeNull();
  expect(posthog.init).not.toHaveBeenCalled();
});
it('honors browser privacy signals even with a previous acceptance', async () => {
  vi.stubGlobal('navigator', { doNotTrack: '1' });
  localStorage.setItem('nfl-analytics-consent', 'yes'); await start();
  expect(posthog.init).not.toHaveBeenCalled();
  expect(window.nflAnalytics?.headers()).toEqual({});
});
it('keeps privacy controls usable if the SDK cannot initialize', async () => {
  vi.mocked(posthog.init).mockImplementationOnce(() => { throw new Error('blocked'); });
  await start(); click('Allow analytics');
  expect(window.nflAnalytics?.headers()).toEqual({});
  click('Privacy'); click('No thanks');
  expect(localStorage.getItem('nfl-analytics-consent')).toBe('no');
});

it('asks prior analytics-only visitors for recording consent', async () => {
  localStorage.setItem('nfl-analytics-consent', 'yes'); await start();
  expect(posthog.init).not.toHaveBeenCalled();
  expect(document.querySelector('[role=dialog]')?.textContent).toContain('recordings');
  click('Allow analytics');
  expect(localStorage.getItem('nfl-analytics-consent')).toBe('yes-with-replay-v1');
});
it('resumes recording only with the updated consent and omits unavailable replays', async () => {
  localStorage.setItem('nfl-analytics-consent', 'yes-with-replay-v1'); await start();
  expect(posthog.startSessionRecording).toHaveBeenCalledTimes(1);
  vi.mocked(posthog.sessionRecordingStarted).mockReturnValueOnce(false);
  expect(window.nflAnalytics?.replayUrl?.()).toBeUndefined();
});

it('marks internal traffic without enabling analytics and reads changes from other tabs', async () => {
  localStorage.setItem('nfl-analytics-internal', 'true');
  await start();
  expect(posthog.init).not.toHaveBeenCalled();
  expect(posthog.capture).not.toHaveBeenCalled();
  click('Allow analytics');
  expect(posthog.capture).toHaveBeenCalledWith('$pageview', expect.objectContaining({ is_internal: true }));
  localStorage.removeItem('nfl-analytics-internal');
  window.nflAnalytics?.capture('navigation_clicked');
  expect(posthog.capture).toHaveBeenLastCalledWith('navigation_clicked', expect.objectContaining({ is_internal: false }));
});
