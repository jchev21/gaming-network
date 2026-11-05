import assert from 'node:assert/strict';
import { issueRunToken, validateSubmission, createLeaderboard, ScoreError, LIMITS } from './scoring.mjs';
const secret = 'test-only-signing-secret-0123456789abcdef';
const rejects = async (fn, code) => { try { await fn(); } catch (e) { assert.ok(e instanceof ScoreError, String(e)); assert.equal(e.code, code); return; } assert.fail('expected ' + code); };
let t = 1_000_000;
const lb = createLeaderboard({ secret, now: () => t });
const tok = (p, g = 'targets', d = 60) => lb.start(p, g, d);

// valid submission after playing full duration
let token = tok('111'); t += 61_000;
assert.deepEqual(await lb.submit('111', 'Ann', { token, score: 5000 }), { accepted: true, tier: 'unverified', prizeEligible: false });
// replay
await rejects(() => lb.submit('111', 'Ann', { token, score: 5000 }), 'REPLAY');
// tampered / forged tokens
await rejects(() => lb.submit('111', 'Ann', { token: token.slice(0, -2) + 'xx', score: 1 }), 'BAD_TOKEN');
await rejects(() => lb.submit('111', 'Ann', { token: 'a.b.c', score: 1 }), 'BAD_TOKEN');
await rejects(() => lb.submit('111', 'Ann', { token: issueRunToken({ playerId: '111', game: 'runner', duration: 60, secret: 'other-secret-other-secret-other-secret!' , now: t }), score: 1 }), 'BAD_TOKEN');
// token stolen by another player
token = tok('111'); t += 61_000;
await rejects(() => lb.submit('222', 'Eve', { token, score: 1 }), 'TOKEN_MISMATCH');
// impossible score for elapsed time (submitted 1s after start)
token = tok('222'); t += 1_000;
await rejects(() => lb.submit('222', 'Eve', { token, score: 100_000 }), 'IMPOSSIBLE_SCORE');
// non-integers / negatives
t += 60_000;
for (const bad of [-1, 1.5, NaN, '9', Infinity, 2 ** 60]) { const k = tok('333'); t += 61_000; await rejects(() => lb.submit('333', 'x', { token: k, score: bad }), 'INVALID_SCORE'); }
// expired token
token = tok('444'); t += 60_000 + LIMITS.tokenTtlMs + 1;
await rejects(() => lb.submit('444', 'Old', { token, score: 1 }), 'TOKEN_EXPIRED');
// invalid board and unauthenticated start
assert.throws(() => lb.start('111', 'poker', 60), e => e.code === 'INVALID_GAME');
assert.throws(() => lb.start('111', 'runner', 45), e => e.code === 'INVALID_DURATION');
assert.throws(() => lb.start('', 'runner', 60), e => e.code === 'AUTH_REQUIRED');
assert.throws(() => createLeaderboard({ secret: 'short' }), /secret/);
// per-hour rate limit
const rl = createLeaderboard({ secret, now: () => t });
for (let i = 0; i < LIMITS.maxRunsPerHour; i++) { const k = rl.start('555', 'runner', 30); t += 31_000 - 1; await rl.submit('555', 'R', { token: k, score: 10 }); t += 1 }
// 30 runs * ~31s = ~15.5 min, all inside one hour
const extra = rl.start('555', 'runner', 30); t += 31_000;
await rejects(() => rl.submit('555', 'R', { token: extra, score: 10 }), 'RATE_LIMIT');
// board privacy, name sanitizing, per-player best-N and ranking
const b = createLeaderboard({ secret, now: () => t });
for (const [p, n, s] of [['1', '<b>Zed</b>\u0000', 900], ['2', 'Yan', 1200], ['1', 'Zed', 700]]) { const k = b.start(p, 'targets', 30); t += 31_000; await b.submit(p, n, { token: k, score: s }); }
const top = b.top('targets', 30);
assert.deepEqual(top.map(r => [r.rank, r.name, r.score]), [[1, 'Yan', 1200], [2, 'bZed/b', 900]]);
assert.ok(!JSON.stringify(top).match(/playerId|nonce|prizeEligible/));
for (let i = 0; i < 8; i++) { const k = b.start('9', 'targets', 30); t += 31_000; await b.submit('9', 'N', { token: k, score: i }); }
assert.equal(b.state.entries.filter(e => e.playerId === '9').length, LIMITS.maxEntriesPerBoard);
assert.ok(b.state.entries.every(e => e.prizeEligible === false && e.tier === 'unverified'));
console.log('Arcade score validation tests passed');
