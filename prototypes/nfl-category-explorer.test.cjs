const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const { JSDOM } = require('jsdom');

const directory = __dirname;
const html = readFileSync(path.join(directory, 'nfl-category-explorer.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(script, 'prototype has an inline script');

const fixture = JSON.parse(readFileSync(path.join(directory, 'nfl-category-prototype-data.json'), 'utf8'));
const context = vm.createContext({ fetch: () => new Promise(() => {}), fixture });
vm.runInContext(script, context);
vm.runInContext('data = fixture', context);
const { tapeBeneficiary, tapeTypeGroup, tapeOutcomeMatch, tapeSorted, tapeFacts, renderSuccessStrip, penaltyCategory } =
  vm.runInContext('({ tapeBeneficiary, tapeTypeGroup, tapeOutcomeMatch, tapeSorted, tapeFacts, renderSuccessStrip, penaltyCategory })', context);
const plays = fixture.all_plays;
const find = id => plays.find(play => play.play_id === id);

test('beneficiary follows the sign of the unrounded home WP change', () => {
  assert.equal(tapeBeneficiary({ home_wp_delta: 0.001 }), 'WSH');
  assert.equal(tapeBeneficiary({ home_wp_delta: -0.001 }), 'SEA');
  assert.equal(tapeBeneficiary({ home_wp_delta: 0 }), 'none');
  assert.equal(tapeBeneficiary({ home_wp_delta: null }), 'unavailable');
});

test('turnover and play-type filters include the relevant plays', () => {
  vm.runInContext("tapeOutcome = 'turnover'", context);
  const turnovers = plays.filter(play => tapeOutcomeMatch(play));
  assert.equal(turnovers.length, 3);
  assert.ok(turnovers.every(play => tapeBeneficiary(play) === 'WSH'));
  assert.equal(tapeTypeGroup(find('401872955315')), 'rush');
  assert.equal(tapeTypeGroup(find('4018729554262')), 'pass');
  assert.equal(tapeTypeGroup(plays.find(play => play.type === 'Fumble Recovery (Own)')), 'pass');
});

test('fourth-down filter excludes timeout rows', () => {
  vm.runInContext("tapeOutcome = 'fourth'", context);
  const fourthDowns = plays.filter(play => tapeOutcomeMatch(play));
  assert.equal(fourthDowns.length, 17);
  assert.ok(fourthDowns.every(play => !/Timeout/.test(play.type)));
});

test('WP sorting keeps the largest swing first', () => {
  vm.runInContext("tapeSort = 'wp'", context);
  assert.equal(tapeSorted(plays)[0].play_id, '4018729554262');
});

test('league context appears only for a top-ten weekly rank', () => {
  assert.equal(fixture.week_wp_context.ranks['4018729554262'], 7);
  assert.equal(fixture.week_wp_context.ranks['4018729554575'], 18);
  const hasLeagueRank = play => tapeFacts(play, true).some(([label]) => label === 'League week WP rank');
  assert.equal(hasLeagueRank(find('4018729554262')), true);
  assert.equal(hasLeagueRank(find('4018729554575')), false);
  assert.equal(hasLeagueRank(find('4018729553976')), false);
});

test('success sequence shows the percentage on each team quarter line', () => {
  const markup = renderSuccessStrip();
  for (const [team, quarter, count, percentage] of [
    ['SEA', 1, '6/14', '42.9%'],
    ['WSH', 1, '5/14', '35.7%'],
    ['SEA', 4, '11/13', '84.6%'],
    ['WSH', 4, '5/17', '29.4%'],
  ]) {
    assert.match(markup, new RegExp(`${team} Q${quarter}: [^\"]+${percentage.slice(0, -1)} percent`));
    assert.ok(markup.includes(`${count} · ${percentage}`));
  }
  assert.ok(!html.includes('renderTurnoverStrip'), 'turnover visualization was removed');
});

test('penalty categories partition charged yards and retain zero-yard placement fouls', () => {
  for (const [team, expected] of [
    ['SEA', { 'Setup / procedure': 24, 'Coverage / contact': 14, 'Personal / conduct': 15, 'Kick placement': 0 }],
    ['WSH', { 'Setup / procedure': 20, 'Coverage / contact': 7, 'Personal / conduct': 30, 'Kick placement': 0 }],
  ]) {
    const events = fixture.events['Penalty Yards'].filter(event => event.team === team);
    const totals = Object.fromEntries(Object.keys(expected).map(category => [category, 0]));
    for (const event of events) totals[penaltyCategory(event)] += Math.abs(event.yards);
    assert.deepEqual(totals, expected);
    assert.equal(events.filter(event => penaltyCategory(event) === 'Kick placement').length, 1);
  }
});

test('chart toggle stays beside its chart and remembers each factor across split changes', () => {
  const dom = new JSDOM(html, { runScripts: 'outside-only' });
  const { window } = dom;
  window.fetch = () => new Promise(() => {});
  window.fixture = fixture;
  window.eval(`${script}\ndata = window.fixture; renderRail(); renderDetail();`);
  const detail = window.document.querySelector('#detail');
  const toggle = () => detail.querySelector('.viz-toggle');
  const select = factor => window.document.querySelector(`[data-category="${factor}"]`).click();

  assert.ok(detail.classList.contains('has-chart'));
  assert.ok(toggle().closest('.factorvizhead'));
  assert.equal(toggle().getAttribute('aria-expanded'), 'true');
  toggle().click();
  assert.ok(detail.classList.contains('chart-collapsed'));
  assert.equal(detail.querySelector('.viz-content').hidden, true);
  assert.equal(toggle().textContent, 'Show chart');

  detail.querySelector('[data-tab="down"]').click();
  assert.ok(detail.classList.contains('chart-collapsed'));
  select('Points Per Trip (Inside 40)');
  assert.ok(toggle().closest('.tripstriphead'));
  assert.equal(toggle().getAttribute('aria-expanded'), 'true');
  select('Ave Start Field Pos');
  assert.ok(toggle().closest('.fieldstriphead'));
  select('Success Rate');
  assert.equal(toggle().getAttribute('aria-expanded'), 'false');
  toggle().click();
  assert.equal(detail.querySelector('.viz-content').hidden, false);
  assert.equal(toggle().textContent, 'Hide chart');

  select('Penalty Yards');
  assert.equal(toggle(), null);
  assert.equal(detail.classList.contains('has-chart'), false);
  dom.window.close();
});
