import posthog from 'posthog-js';
import { analyticsPage, type AnalyticsProperties } from './analytics';

const CONSENT = 'nfl-analytics-consent';
let started = false;
export async function startAnalytics() {
  if (started || typeof window === 'undefined') return;
  started = true;
  try {
    const config = await fetch('/analytics-config', { cache: 'no-store' }).then(r => r.json());
    if (!config.token || !config.host) return;
    if (!config.testMode && !['windelta.app', 'www.windelta.app'].includes(location.hostname)) return;
    const privacySignal = navigator.doNotTrack === '1' || (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl === true;
    const readChoice = () => { try { return localStorage.getItem(CONSENT); } catch { return null; } };
    let active = false, initialized = false, lastPath = '';
    const properties = () => ({ ...analyticsPage(new URL(location.href)), is_test: Boolean(config.testMode), schema_version: 1 });
    const capture = (event: string, values: AnalyticsProperties = {}) => {
      if (active) { try { posthog.capture(event, { ...properties(), ...values }); } catch { /* Analytics cannot break navigation. */ } }
    };
    const visit = () => {
      const page = properties();
      if (!active || page.path === lastPath) return;
      lastPath = page.path;
      capture('$pageview', { $current_url: location.origin + page.path, $pathname: page.path });
      if (['game_report', 'team', 'rankings'].includes(page.page_type)) capture('content_viewed');
    };
    const enable = () => {
      if (privacySignal) return;
      if (!initialized) {
        posthog.init(config.token, {
          api_host: '/ingest', ui_host: config.host.replace('.i.', '.'), defaults: '2026-08-30',
          autocapture: false, capture_pageview: false, capture_pageleave: false,
          capture_exceptions: false, capture_performance: false,
          save_campaign_params: false, save_referrer: false,
          disable_session_recording: true, disable_surveys: true,
          advanced_disable_flags: true, opt_out_useragent_filter: Boolean(config.testMode), person_profiles: 'identified_only',
          persistence: 'localStorage+cookie', respect_dnt: true,
          before_send: event => {
            if (!active || !event) return null;
            // Do not collect query strings, arbitrary anchors, initial URLs or referrer paths.
            for (const props of [event.properties, event.properties.$set, event.properties.$set_once]) {
              if (!props || typeof props !== 'object') continue;
              for (const key of ['$current_url', '$initial_current_url']) {
                if (typeof props[key] === 'string') {
                  const url = new URL(props[key]);
                  props[key] = url.origin + analyticsPage(url).path;
                }
              }
              for (const key of ['$referrer', '$initial_referrer']) {
                if (typeof props[key] === 'string' && props[key].startsWith('http')) props[key] = new URL(props[key]).origin;
              }
            }
            return event;
          },
        });
        initialized = true;
      }
      active = true;
      posthog.opt_in_capturing({ captureEventName: false });
      visit();
    };
    window.nflAnalytics = { capture, headers: (): Record<string, string> => active ? {
      'X-POSTHOG-DISTINCT-ID': posthog.get_distinct_id(),
      'X-POSTHOG-SESSION-ID': posthog.get_session_id(),
      'X-NFL-ANALYTICS-CONSENT': 'yes',
      'X-NFL-ANALYTICS-TEST': String(Boolean(config.testMode)),
    } : {} };
    const choose = (allow: boolean) => {
      try { localStorage.setItem(CONSENT, allow ? 'yes' : 'no'); } catch { /* Session-only choice. */ }
      if (allow) {
        try { enable(); } catch { active = false; /* A blocked SDK cannot break consent controls. */ }
      }
      else {
        active = false; lastPath = '';
        if (initialized) posthog.opt_out_capturing();
      }
      panel.remove();
    };
    const panel = document.createElement('section');
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', 'Analytics privacy');
    panel.style.cssText = 'position:fixed;z-index:10000;bottom:44px;left:16px;right:16px;max-width:420px;padding:20px;background:#fff;color:#17212a;border:1px solid #535d66;box-shadow:0 4px 20px #0002;font:14px/1.5 Arial,sans-serif';
    const copy = document.createElement('p');
    copy.textContent = privacySignal ? 'Your browser privacy preference is on. Analytics is disabled.' : 'Help improve NFL Win Delta? With your permission, we measure page visits, feature use, and whether this browser returns in later weeks. No session recordings.';
    panel.append(copy);
    const button = (label: string, action: () => void) => {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = label;
      b.style.cssText = 'padding:9px 12px;margin:4px 8px 4px 0;border:1px solid #535d66;background:#fff;color:#17212a;cursor:pointer;font:inherit'; b.onclick = action; return b;
    };
    if (!privacySignal) panel.append(button('Allow analytics', () => choose(true)), button('No thanks', () => choose(false)));
    else panel.append(button('Close', () => panel.remove()));
    const link = document.createElement('a'); link.href = '/privacy.html'; link.textContent = 'Privacy details'; link.style.color = '#9e3325'; panel.append(link);
    const settings = button('Privacy', () => { document.body.append(panel); panel.querySelector('button')?.focus(); });
    settings.style.cssText += ';position:fixed;z-index:9999;bottom:4px;left:12px;padding:4px 8px;font-size:12px';
    const mount = () => { document.body.append(settings); if (!readChoice() && !privacySignal) document.body.append(panel); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true }); else mount();
    if (readChoice() === 'yes') enable();
    for (const method of ['pushState', 'replaceState'] as const) {
      const original = history[method].bind(history);
      history[method] = (...args: Parameters<History[typeof method]>) => { original(args[0], args[1], args[2]); visit(); };
    }
    addEventListener('popstate', visit); addEventListener('hashchange', visit);
    document.addEventListener('click', event => {
      const element = event.target instanceof Element ? event.target.closest<HTMLElement>('[data-analytics-event], a[href]') : null;
      if (!element) return;
      const name = element.dataset.analyticsEvent;
      if (name) capture(name, { control: element.dataset.analyticsValue || '' });
      else if (element instanceof HTMLAnchorElement) {
        const url = new URL(element.href, location.href);
        if (url.origin === location.origin && analyticsPage(url).path !== properties().path) capture('navigation_clicked', { destination: analyticsPage(url).path });
      }
    });
    document.addEventListener('change', event => {
      const target = event.target;
      if (target instanceof HTMLSelectElement && target.dataset.analyticsEvent) capture(target.dataset.analyticsEvent, { control: target.dataset.analyticsValue || target.id, value: target.value });
    });
    document.addEventListener('toggle', event => {
      const target = event.target;
      if (target instanceof HTMLDetailsElement && target.open) capture('explanation_opened', { control: target.dataset.analyticsValue || target.querySelector('summary')?.textContent?.trim().slice(0, 80) || 'details' });
    }, true);
  } catch { /* A blocked endpoint or SDK must leave the site fully usable. */ }
}
