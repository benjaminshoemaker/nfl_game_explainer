const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const directory = __dirname;
const html = readFileSync(path.join(directory, 'nfl-category-explorer.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(script, 'prototype has an inline script');

const fixture = JSON.parse(readFileSync(path.join(directory, 'nfl-category-prototype-data.json'), 'utf8'));
const context = vm.createContext({ fetch: () => new Promise(() => {}), fixture });
vm.runInContext(script, context);
vm.runInContext('data = fixture', context);
const { tapeBeneficiary, tapeTypeGroup, tapeOutcomeMatch, tapeSorted, tapeFacts } =
  vm.runInContext('({ tapeBeneficiary, tapeTypeGroup, tapeOutcomeMatch, tapeSorted, tapeFacts })', context);
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
