import { readFileSync } from 'node:fs';
import { afterEach, expect, it } from 'vitest';

const html = readFileSync('public/internal-traffic.html', 'utf8');
const script = readFileSync('public/internal-traffic.js', 'utf8');
afterEach(() => { localStorage.clear(); document.body.innerHTML = ''; });
function mount() {
  document.body.innerHTML = html;
  window.eval(script);
}
it('persists the browser exclusion without changing consent or loading analytics', () => {
  localStorage.setItem('nfl-analytics-consent', 'no');
  mount();
  document.getElementById('mark-internal')!.click();
  expect(localStorage.getItem('nfl-analytics-internal')).toBe('true');
  expect(localStorage.getItem('nfl-analytics-consent')).toBe('no');
  mount();
  expect(document.getElementById('status')).toHaveTextContent('This browser is internal');
  expect(document.querySelector('script[src="/analytics.js"]')).toBeNull();
  document.getElementById('clear-internal')!.click();
  expect(localStorage.getItem('nfl-analytics-internal')).toBeNull();
  expect(document.getElementById('status')).toHaveTextContent('not marked as internal');
});
