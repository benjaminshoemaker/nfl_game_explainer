import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, test } from 'vitest';
import { FeedbackLink } from './FeedbackLink';
import { feedbackUrl } from '../../public/feedback.js';

afterEach(() => window.history.replaceState({}, '', '/'));

test('uses the current game URL after client navigation and encodes email context', () => {
  render(<FeedbackLink />);
  window.history.replaceState({}, '', '/game/401?week=9&season=2026#plays');
  document.title = 'Seattle & San Francisco';
  const link = screen.getByRole('link', { name: 'Send feedback' });
  fireEvent.focus(link);
  const mail = new URL(link.getAttribute('href')!);
  expect(mail.pathname).toBe('ben.shoemaker.xyz@gmail.com');
  expect(mail.searchParams.get('body')).toContain(window.location.href);
  expect(mail.searchParams.get('body')).toContain('Game ID: 401');
  expect(mail.searchParams.get('body')).toContain('Seattle & San Francisco');
  window.history.replaceState({}, '', '/game/402');
  fireEvent.mouseEnter(link);
  expect(new URL(link.getAttribute('href')!).searchParams.get('body')).toContain('Game ID: 402');
});

test('includes available PostHog context but respects opt-out and tolerates unavailable analytics', () => {
  const page = { location: { href: 'https://example.test/teams/SEA#team/SF' },
    document: { title: 'San Francisco', querySelector: () => ({ value: '2026' }) },
    nflAnalytics: { replayUrl: () => 'https://us.posthog.com/project/736759/replay/session-456?t=30', headers: (): Record<string, string> => ({
      'X-NFL-ANALYTICS-CONSENT': 'yes', 'X-POSTHOG-DISTINCT-ID': 'visitor-123',
      'X-POSTHOG-SESSION-ID': 'session-456' }) } };
  const body = () => new URL(feedbackUrl(page)).searchParams.get('body');
  expect(body()).toContain('PostHog visitor ID: visitor-123');
  expect(body()).toContain('PostHog session ID: session-456');
  expect(body()).toContain('Session recording (if available): https://us.posthog.com/project/736759/replay/session-456?t=30');
  expect(body()).toContain('Season: 2026');
  expect(body()).toContain('#team/SF');
  page.nflAnalytics.headers = () => ({});
  expect(body()).not.toContain('PostHog');
  expect(body()).not.toContain('Session recording');
  page.nflAnalytics.headers = () => { throw new Error('Blocked'); };
  expect(body()).toContain('Page: San Francisco');
});
