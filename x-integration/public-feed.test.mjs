/**
 * Privacy-safe public lobby feed tests.
 * Run: node public-feed.test.mjs
 */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { createLobbyApi } from './lobby-api.mjs';
import { createLobby, joinLobby } from './game-core.mjs';
import { parseFeedQuery, buildPublicFeed } from './public-feed.mjs';

{
  assert.throws(() => parseFeedQuery(new URLSearchParams('game=not-a-game')), (e) => e.code === 'INVALID_GAME' && e.status === 400);
  assert.throws(() => parseFeedQuery(new URLSearchParams('platform=amiga')), (e) => e.code === 'INVALID_PLATFORM');
  assert.throws(() => parseFeedQuery(new URLSearchParams('status=exploding')), (e) => e.code === 'INVALID_STATUS');
  assert.throws(() => parseFeedQuery(new URLSearchParams('limit=0')), (e) => e.code === 'INVALID_LIMIT');
  assert.throws(() => parseFeedQuery(new URLSearchParams('limit=99')), (e) => e.code === 'INVALID_LIMIT');
  assert.throws(() => parseFeedQuery(new URLSearchParams('cursor=%%%')), (e) => e.code === 'INVALID_CURSOR');
  const q = parseFeedQuery(new URLSearchParams('game=fortnite&platform=pc&status=open&limit=10'));
  assert.equal(q.game, 'fortnite');
  assert.equal(q.platform, 'pc');
  assert.equal(q.status, 'open');
  assert.equal(q.limit, 10);
  console.log('\u2713 query validation rejects bad filters with 400');
}

{
  const now = 1_700_000_000_000;
  const a = createLobby({ game: 'fortnite', title: 'Alpha', seats: 3, mode: 'first', platform: 'pc' }, '1001', now);
  const b = createLobby({ game: 'warzone', title: 'Bravo', seats: 4, mode: 'first', platform: 'pc' }, '1002', now + 1000);
  joinLobby(a, '2002', '@alice', now + 10);
  joinLobby(a, '2003', '@bob', now + 20);
  const lobbies = { [a.id]: a, [b.id]: b };
  const page = buildPublicFeed(lobbies, parseFeedQuery(new URLSearchParams('limit=10')), () => now + 5000);
  assert.equal(page.source, 'live');
  assert.equal(page.games.length, 2);
  assert.equal(page.games[0].id, b.id);
  assert.equal(page.games[1].id, a.id);
  const raw = JSON.stringify(page);
  assert.ok(!raw.includes('ownerXId'));
  assert.ok(!raw.includes('joinSecrets'));
  assert.ok(!raw.includes('invite'));
  assert.ok(!('entries' in page.games[1]), 'public discovery should not list players');
  assert.ok(!('waitlist' in page.games[1]), 'public discovery should not list waitlisted players');
  assert.ok(!('host' in page.games[1]), 'public discovery should not expose host options');
  assert.equal(page.games[1].entryCount, 2);
  const filtered = buildPublicFeed(lobbies, parseFeedQuery(new URLSearchParams('game=fortnite')), () => now + 5000);
  assert.equal(filtered.games.length, 1);
  assert.equal(filtered.games[0].game, 'fortnite');
  const empty = buildPublicFeed({}, parseFeedQuery(new URLSearchParams('')), () => now);
  assert.equal(empty.games.length, 0);
  const first = buildPublicFeed(lobbies, parseFeedQuery(new URLSearchParams('limit=1')), () => now + 5000);
  assert.equal(first.games.length, 1);
  assert.ok(first.nextCursor);
  const second = buildPublicFeed(
    lobbies,
    parseFeedQuery(new URLSearchParams('limit=1&cursor=' + first.nextCursor)),
    () => now + 5000
  );
  assert.equal(second.games.length, 1);
  assert.equal(second.games[0].id, a.id);
  console.log('\u2713 buildPublicFeed order, filters, cursor, privacy');
}

const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'gn-feed-'));
const origin = 'https://example.test';
const auth = {
  authenticated: (req) =>
    req.headers['x-test-user']
      ? { id: req.headers['x-test-user'], username: req.headers['x-test-user'] }
      : null,
};
const mentions = {
  pending: [{ post_id: '11111111', author_id: '10001', excerpt: '@jordan__chev start a game' }],
};
let time = 100000;
const JOIN_KEY = 'public-feed-test-join-secret-key-32c';

const api = await createLobbyApi({
  dataDir: dir,
  auth,
  mentions,
  adminToken: 'admin-token-for-tests-only',
  publicOrigin: origin,
  now: () => time,
  joinSecretKey: JOIN_KEY,
});

const server = http.createServer(async (req, res) => {
  if (!(await api.handle(req, res, new URL(req.url, 'http://localhost')))) {
    res.writeHead(404);
    res.end();
  }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = 'http://127.0.0.1:' + server.address().port;

async function req(route, method = 'GET', body, headers = {}) {
  const response = await fetch(base + route, {
    method,
    headers: { origin, 'content-type': 'application/json', ...headers },
    body: body ? JSON.stringify(body) : undefined,
  });
  let parsed = null;
  try { parsed = await response.json(); } catch { /* empty */ }
  return { code: response.status, body: parsed, headers: response.headers };
}

try {
  const empty = await req('/api/lobbies');
  assert.equal(empty.code, 200);
  assert.deepEqual(empty.body.games, []);
  assert.equal(empty.body.source, 'live');
  assert.ok(String(empty.headers.get('cache-control') || '').includes('max-age'));

  const approval = await req(
    '/admin/invites',
    'POST',
    { post_id: '11111111' },
    { authorization: 'Bearer admin-token-for-tests-only' }
  );
  assert.equal(approval.code, 201);
  const token = new URL(approval.body.setupUrl).searchParams.get('invite');
  const created = await req(
    '/api/lobbies',
    'POST',
    { inviteToken: token, game: 'fortnite', platform: 'pc', mode: 'first', seats: 2, title: 'Public Feed Game', roundSeconds: 60 },
    { 'x-test-user': '10001' }
  );
  assert.equal(created.code, 201, JSON.stringify(created.body));
  const gameId = created.body.game.id;
  await req('/api/lobbies/' + gameId + '/join', 'POST', {}, { 'x-test-user': '10002' });
  await req('/api/lobbies/' + gameId + '/join', 'POST', {}, { 'x-test-user': '10003' });

  const feed = await req('/api/lobbies');
  assert.equal(feed.code, 200);
  assert.equal(feed.body.games.length, 1);
  assert.equal(feed.body.games[0].status, 'ready');
  assert.equal(feed.body.games[0].game, 'fortnite');
  assert.ok(feed.body.games[0].seats >= 2);
  assert.ok('waitlistCount' in feed.body.games[0]);
  assert.ok('entryCount' in feed.body.games[0]);

  const blob = JSON.stringify(feed.body);
  for (const leak of ['ownerXId', 'joinSecrets', 'inviteToken', 'JOIN-', 'ciphertext', 'admin-token', '"xId"']) {
    assert.ok(!blob.includes(leak), `feed must not contain ${leak}`);
  }
  assert.ok(!/"xId"\s*:/.test(blob));
  assert.ok(!/"ownerXId"\s*:/.test(blob));
  for (const sensitive of ['entries', 'waitlist', 'host', 'ownerXId', 'username', 'xId']) {
    assert.ok(!Object.hasOwn(feed.body.games[0], sensitive), `public lobby list must omit ${sensitive}`);
  }

  assert.equal((await req('/api/lobbies?game=fortnite')).body.games.length, 1);
  assert.equal((await req('/api/lobbies?game=warzone')).body.games.length, 0);
  assert.equal((await req('/api/lobbies?status=ready')).body.games.length, 1);
  assert.equal((await req('/api/lobbies?status=open')).body.games.length, 0);
  assert.equal((await req('/api/lobbies?platform=pc')).body.games.length, 1);

  assert.equal((await req('/api/lobbies?game=nope')).code, 400);
  assert.equal((await req('/api/lobbies?limit=999')).code, 400);
  assert.equal((await req('/api/lobbies?status=weird')).code, 400);

  const one = await req('/api/lobbies/' + gameId);
  assert.equal(one.code, 200);
  assert.ok(!JSON.stringify(one.body).includes('ownerXId'));

  assert.equal((await req('/api/lobbies/' + gameId + '/join-details')).code, 401);

  await req('/api/lobbies/' + gameId + '/cancel', 'POST', {}, { 'x-test-user': '10001' });
  const cancelled = await req('/api/lobbies?status=cancelled');
  assert.equal(cancelled.code, 200);
  assert.equal(cancelled.body.games.length, 1);
  assert.equal(cancelled.body.games[0].status, 'cancelled');
  assert.equal(cancelled.body.games[0].waitlistCount, 0);

  console.log('\u2713 HTTP public feed: empty, populated, filters, privacy, cancel');
} finally {
  server.close();
  await fs.rm(dir, { recursive: true, force: true });
}

console.log('\nAll public-feed tests passed.');
