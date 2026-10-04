/* eslint-disable @typescript-eslint/no-require-imports -- This standalone Node test uses CommonJS. */
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
const playContextFixture = JSON.parse(readFileSync(path.join(directory, 'play-card-context.json'), 'utf8'));
const context = vm.createContext({ fetch: () => new Promise(() => {}), fixture, playContextFixture });
vm.runInContext(script, context);
vm.runInContext('setPrototypeData(fixture, playContextFixture)', context);
const { tapeBeneficiary, tapeTypeGroup, tapeOutcomeMatch, tapeSorted, playCard, renderSuccessStrip, penaltyCategory } =
  vm.runInContext('({ tapeBeneficiary, tapeTypeGroup, tapeOutcomeMatch, tapeSorted, playCard, renderSuccessStrip, penaltyCategory })', context);
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

test('one source play renders the same card in factors and both play lists', () => {
  const dom = new JSDOM(html, { runScripts: 'outside-only' });
  const { window } = dom;
  window.fetch = () => new Promise(() => {});
  window.Element.prototype.scrollIntoView = () => {};
  window.fixture = fixture;
  window.playContextFixture = playContextFixture;
  window.eval(`${script}\nsetPrototypeData(window.fixture, window.playContextFixture); renderRail(); renderDetail(); renderTape();`);

  window.document.querySelector('[data-tape-scope="full"]').click();
  window.document.querySelector('[data-category="Non-Offensive Points"]').click();
  const id = '4018729554262';
  window.document.querySelector(`#impact-panel [data-impact-id="${id}"]`).click();
  const factorCard = window.document.querySelector(`#detail .play-card[data-play-id="${id}"]`);
  const impactCard = window.document.querySelector(`#impact-panel .play-card[data-play-id="${id}"]`);
  const tapeCard = window.document.querySelector(`#all-plays-panel .play-card[data-play-id="${id}"]`);
  assert.ok(factorCard && impactCard && tapeCard);
  assert.equal(factorCard.outerHTML, impactCard.outerHTML);
  assert.equal(impactCard.outerHTML, tapeCard.outerHTML);
  assert.match(factorCard.textContent, /Score SEA 24 · WSH 27/);
  assert.match(factorCard.textContent, /2nd and 15 from the WSH 49/);
  assert.match(factorCard.textContent, /WSH \+34\.1 pp/);
  assert.ok(!impactCard.querySelector('.taperank'), 'list rank sits outside the card');
  assert.ok(!factorCard.querySelector('.context-rank'), 'unverified league rank is withheld');
  dom.window.close();
});

test('drive, trip, and penalty facts surround the canonical source card', () => {
  const dom = new JSDOM(html, { runScripts: 'outside-only' });
  const { window } = dom;
  window.fetch = () => new Promise(() => {});
  window.fixture = fixture;
  window.playContextFixture = playContextFixture;
  window.eval(`${script}\nsetPrototypeData(window.fixture, window.playContextFixture); renderRail(); renderDetail();`);

  window.document.querySelector('[data-category="Ave Start Field Pos"]').click();
  window.document.querySelector('#toggleMode').click();
  let entry = window.document.querySelector('#detail .play-entry');
  assert.match(entry.querySelector('.entry-context').textContent, /SEA.*SEA 37/);
  assert.equal(entry.querySelector('.play-card .team').textContent, 'WSH');
  assert.ok(!entry.querySelector('.play-card').textContent.includes('Drive start'));

  window.document.querySelector('[data-category="Penalty Yards"]').click();
  window.document.querySelector('#toggleMode').click();
  const penaltyEntry = [...window.document.querySelectorAll('#detail .play-entry')]
    .find(row => row.textContent.includes('Defensive Pass Interference'));
  assert.equal(penaltyEntry.querySelector('.play-card .team').textContent, 'WSH');
  assert.match(penaltyEntry.querySelector('.play-card').textContent, /Defensive Pass Interference on SEA — 14-yard penalty; no play/);

  window.document.querySelector('[data-category="Points Per Trip (Inside 40)"]').click();
  window.document.querySelector('#toggleMode').click();
  entry = window.document.querySelector('#detail .play-entry');
  assert.match(entry.querySelector('.entry-context').textContent, /Trip result/);
  assert.ok(!entry.querySelector('.play-card').textContent.includes('Trip result'));
  dom.window.close();
});

test('every factor event resolves to a source-play card', () => {
  const dom = new JSDOM(html, { runScripts: 'outside-only' });
  const { window } = dom;
  window.fetch = () => new Promise(() => {});
  window.fixture = fixture;
  window.playContextFixture = playContextFixture;
  window.eval(`${script}\nsetPrototypeData(window.fixture, window.playContextFixture); renderRail(); renderDetail();`);
  for (const category of ['Turnovers', 'Success Rate', 'Adjusted Yards Per Play', 'Explosive Play Rate', 'Points Per Trip (Inside 40)', 'Ave Start Field Pos', 'Penalty Yards', 'Non-Offensive Points']) {
    window.document.querySelector(`[data-category="${category}"]`).click();
    if (window.document.querySelector('#toggleMode')) window.document.querySelector('#toggleMode').click();
    while (window.document.querySelector('#loadmore')) window.document.querySelector('#loadmore').click();
    const expected = category === 'Success Rate' || category === 'Adjusted Yards Per Play'
      ? fixture.eligible_plays.length
      : fixture.events[({ 'Explosive Play Rate': 'Explosive Plays', 'Ave Start Field Pos': 'Drive Starts' })[category] || category].length;
    assert.equal(window.document.querySelectorAll('#detail .play-entry .play-card').length, expected, category);
    assert.equal(window.document.querySelectorAll('#detail .source-missing').length, 0, category);
  }
  dom.window.close();
});

test('play card shows WP endpoints only for large swings and withholds old rank labels', () => {
  const pickSix = find('4018729554262');
  assert.match(playCard(pickSix), /63\.1% → 97\.2%/);
  assert.doesNotMatch(playCard(pickSix), /WP rank|WP rarity/);
  assert.doesNotMatch(playCard(plays.find(play => Math.abs(play.home_wp_delta) > 0 && Math.abs(play.home_wp_delta) < .01)), /% → .*%/);
  assert.match(playCard(plays.find(play => play.home_wp_delta === .0002)), /WSH \+&lt;0\.1 pp/);
  assert.doesNotMatch(playCard(plays.find(play => play.down_distance === ' & Goal')), /· and Goal/);
});

test('explicitly declined penalties remain visible without charged yardage', () => {
  assert.match(playCard(find('4018729553362')), /Illegal Shift on WSH — declined/);
  const multiple = playCard(find('4018729551100'));
  assert.match(multiple, /Defensive Pass Interference on WSH — 2-yard penalty; no play/);
  assert.match(multiple, /Illegal Use of Hands on WSH — declined/);
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
  window.playContextFixture = playContextFixture;
  window.eval(`${script}\nsetPrototypeData(window.fixture, window.playContextFixture); renderRail(); renderDetail();`);
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

test('all plays gives the play list room and starts with its chart folded', () => {
  const dom = new JSDOM(html, { runScripts: 'outside-only' });
  const { window } = dom;
  window.fetch = () => new Promise(() => {});
  window.fixture = fixture;
  window.playContextFixture = playContextFixture;
  window.eval(`${script}\nsetPrototypeData(window.fixture, window.playContextFixture); renderRail(); renderDetail();`);
  const detail = window.document.querySelector('#detail');
  window.document.querySelector('[data-category="Ave Start Field Pos"]').click();
  assert.equal(detail.querySelector('.viz-toggle').getAttribute('aria-expanded'), 'true');

  detail.querySelector('#toggleMode').click();
  assert.ok(detail.classList.contains('is-plays'));
  assert.ok(detail.classList.contains('chart-collapsed'));
  assert.equal(detail.querySelector('.viz-toggle').textContent, 'Show chart');
  assert.equal(detail.querySelectorAll('.detailbody > .event').length, 6);
  assert.equal(detail.querySelector('.eventhelp').open, false);
  detail.querySelector('#loadmore').click();
  assert.equal(detail.querySelectorAll('.detailbody > .event').length, 12);

  detail.querySelector('.viz-toggle').click();
  assert.equal(detail.querySelector('.viz-toggle').getAttribute('aria-expanded'), 'true');
  detail.querySelector('#toggleMode').click();
  assert.ok(!detail.classList.contains('is-plays'));
  assert.equal(detail.querySelector('.viz-toggle').getAttribute('aria-expanded'), 'true');
  detail.querySelector('#toggleMode').click();
  assert.equal(detail.querySelector('.viz-toggle').getAttribute('aria-expanded'), 'true');
  dom.window.close();
});
