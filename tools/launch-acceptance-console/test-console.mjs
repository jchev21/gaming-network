import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
const C = createRequire(import.meta.url)('./console-core.js');
let passed = 0;
function test(name, fn) { fn(); console.log('PASS ' + name); passed++; }
function allPassed() {
  const s = C.blank();
  for (const c of C.D.cases) C.update(s, c.id, 'status', 'PASS');
  s.owner = 'Test owner';
  return s;
}
test('all tests begin NOT TESTED', () => {
  assert.equal(C.counts(C.blank()).untested, 20);
  assert.equal(C.ready(C.blank()), false);
});
test('group counts sum to twenty', () =>
  assert.equal(C.D.groups.reduce((n, g) => n + C.counts(C.blank(), g.id).total, 0), 20));
test('all PASS does not automatically grant readiness', () =>
  assert.equal(C.ready(allPassed()), false));
test('named responsible human required', () => {
  const s = allPassed(); s.owner = '';
  assert.throws(() => C.sign(s));
});
test('signoff and edit revocation', () => {
  const s = C.sign(allPassed());
  assert.equal(C.ready(s), true);
  C.update(s, 'hub-01', 'notes', 'Additional observation');
  assert.equal(C.ready(s), false);
});
test('FAIL, BLOCKED and NOT TESTED prevent signoff', () => {
  for (const status of ['FAIL', 'BLOCKED', 'NOT TESTED']) {
    const s = allPassed();
    C.update(s, 'x-03', 'status', status);
    assert.throws(() => C.sign(s));
  }
});
test('validated JSON roundtrip', () => {
  const s = C.snapshot(C.sign(allPassed()));
  assert.deepEqual(C.parse(JSON.stringify(s)), s);
});
test('malformed imports rejected', () => {
  const mutations = [
    s => s.schemaVersion = 9,
    s => s.extra = true,
    s => delete s.results['x-01'],
    s => s.results['x-01'].status = 'AUTO',
    s => s.owner = 42,
    s => s.results['x-01'].notes = 'a'.repeat(4001),
    s => s.results['x-01'].notes = '\u0000',
    s => s.acknowledged = true
  ];
  for (const mutate of mutations) {
    const s = C.blank(); mutate(s);
    assert.throws(() => C.parse(JSON.stringify(s)));
  }
  assert.throws(() => C.parse('x'.repeat(C.MAX + 1)));
  assert.throws(() => C.parse('{'));
});
test('notes never executed as HTML', () => {
  const s = C.blank();
  C.update(s, 'hub-01', 'notes', '<script>alert(1)</script>');
  assert.ok(!C.markdown(C.snapshot(s)).includes('<script>'));
  const app = readFileSync(new URL('./app.js', import.meta.url), 'utf8');
  assert.ok(!app.includes('innerHTML'));
  assert.ok(!app.includes('fetch('));
});
test('reset to blank', () => {
  const s = C.blank();
  assert.ok(Object.values(s.results).every(v => v.status === 'NOT TESTED' && !v.notes));
  assert.equal(s.acknowledged, false);
});
test('checklist covers all launch requirements', () => {
  assert.equal(new Set(C.D.cases.map(c => c.id)).size, 20);
  const markdown = C.markdown(C.snapshot(C.blank()));
  for (const c of C.D.cases) {
    assert.ok(c.required && c.action && c.expected);
    assert.ok(markdown.includes(c.id));
  }
  for (const term of ['Components V2', '429', 'Unknown interaction', '/dashboard', 'Leaderboard', 'Rewards', 'App Launcher', '1/2/4/8', 'OAuth', '5-minute', 'waitlist', 'Account C', 'X_POLL_ENABLED=false', 'issue #30', 'issue #17']) {
    assert.ok(JSON.stringify(C.D).includes(term), term);
  }
});
test('manual IN-PERSON acceptance explicit', () => {
  const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
  assert.ok(html.includes('IN-PERSON ACCEPTANCE ONLY'));
  assert.ok(C.D.cases.every(c => c.required));
});
test('no network connections or external assets', () => {
  const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
  assert.ok(html.includes("connect-src 'none'"));
  for (const match of html.matchAll(/(?:src|href)="([^"]+)"/g)) {
    assert.ok(readFileSync(new URL(match[1], import.meta.url)).length);
  }
});
console.log(passed + ' tests passed. Console self-tests do NOT certify launch.');
