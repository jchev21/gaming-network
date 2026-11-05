/**
 * JSON vs SQLite HTTP parity for lobby-api.
 * Runs the same request sequence against both backends.
 *
 * Run: node lobby-api.parity.test.mjs
 */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { createLobbyApi } from './lobby-api.mjs';
import { createLobbyStore } from './storage/lobby-store.mjs';

const origin = 'https://example.test';
const JOIN_KEY = 'parity-test-join-secret-key-32chars!!';
const ADMIN = 'parity-admin-token-not-used-for-encryption';

async function prepareSqliteDir(dir) {
  const store = createLobbyStore(path.join(dir, 'x-lobbies.sqlite'));
  store.db.prepare("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('migrated_from_json', '1')").run();
  store.close();
}

async function runSuite(storeMode) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), `gn-parity-${storeMode}-`));
  if (storeMode === 'sqlite') await prepareSqliteDir(dir);

  const auth = {
    authenticated: (req) =>
      req.headers['x-test-user']
        ? { id: req.headers['x-test-user'], username: req.headers['x-test-user'] }
        : null,
  };
  const mentions = {
    pending: [
      { post_id: '11111111', author_id: '10001', excerpt: '@jordan__chev start a game' },
      { post_id: '22222222', author_id: '10001', excerpt: '@jordan__chev game request' },
    ],
  };
  let time = 100000;

  const api = await createLobbyApi({
    dataDir: dir,
    auth,
    mentions,
    adminToken: ADMIN,
    publicOrigin: origin,
    now: () => time,
    joinSecretKey: JOIN_KEY,
    storeMode,
  });
  assert.equal(api.storeMode, storeMode);

  const server = http.createServer(async (req, res) => {
    if (!(await api.handle(req, res, new URL(req.url, 'http://localhost')))) {
      res.writeHead(404);
      res.end();
    }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = 'http://127.0.0.1:' + server.address().port;

  async function req(route, method = 'GET', body, headers = {}) {
    const response = await fetch(base + route, {
      method,
      headers: { origin, 'content-type': 'application/json', ...headers },
      body: body ? JSON.stringify(body) : undefined,
    });
    return { code: response.status, body: await response.json() };
  }

  try {
    assert.equal((await req('/admin/invites', 'POST', { post_id: '11111111' })).code, 401);

    const approval = await req(
      '/admin/invites',
      'POST',
      { post_id: '11111111' },
      { authorization: 'Bearer ' + ADMIN }
    );
    assert.equal(approval.code, 201, JSON.stringify(approval.body));
    const token = new URL(approval.body.setupUrl).searchParams.get('invite');
    assert.equal(token.length, 43);

    const config = {
      inviteToken: token,
      game: 'fortnite',
      platform: 'pc',
      mode: 'first',
      seats: 2,
      roundSeconds: 30,
      title: 'X Challenge',
    };
    assert.equal((await req('/api/lobbies', 'POST', config)).code, 401);
    assert.equal((await req('/api/lobbies', 'POST', config, { 'x-test-user': '10002' })).code, 403);
    const valid = await req('/api/lobbies', 'POST', config, { 'x-test-user': '10001' });
    assert.equal(valid.code, 201, JSON.stringify(valid.body));
    const gameId = valid.body.game.id;
    assert.ok(gameId);

    assert.equal((await req('/api/lobbies', 'POST', config, { 'x-test-user': '10001' })).code, 403);

    assert.equal((await req('/api/lobbies/' + gameId + '/join', 'POST', {}, { 'x-test-user': '10002' })).code, 200);
    assert.equal((await req('/api/lobbies/' + gameId + '/join', 'POST', {}, { 'x-test-user': '10002' })).code, 409);
    const join2 = await req('/api/lobbies/' + gameId + '/join', 'POST', {}, { 'x-test-user': '10003' });
    assert.equal(join2.code, 200);
    assert.equal(join2.body.game.status, 'ready');

    assert.equal((await req('/api/my-games')).code, 401);
    const hostGames = await req('/api/my-games', 'GET', undefined, { 'x-test-user': '10001' });
    assert.equal(hostGames.code, 200);
    assert.equal(hostGames.body.games.length, 1);
    assert.equal(hostGames.body.games[0].viewerRole, 'host');
    const playerGames = await req('/api/my-games', 'GET', undefined, { 'x-test-user': '10002' });
    assert.equal(playerGames.code, 200);
    assert.equal(playerGames.body.games[0].viewerRole, 'player');
    assert.deepEqual((await req('/api/my-games', 'GET', undefined, { 'x-test-user': '19999' })).body.games, []);
    assert.ok(!JSON.stringify(playerGames.body).includes('ownerXId'));
    assert.ok(!JSON.stringify(hostGames.body).includes('joinSecrets'));

    const badOrigin = await fetch(base + '/api/lobbies/' + gameId + '/join', {
      method: 'POST',
      headers: { origin: 'https://evil.test', 'content-type': 'application/json', 'x-test-user': '10004' },
      body: '{}',
    });
    assert.equal(badOrigin.status, 403);

    const instructionsPath = '/api/lobbies/' + gameId + '/join-details';
    const privateNotes = 'Fortnite party invite via HostX. Private key: JOIN-TEST-KEY.';
    assert.equal((await req(instructionsPath, 'POST', { instructions: privateNotes }, { 'x-test-user': '10002' })).code, 403);
    const saved = await req(instructionsPath, 'POST', { instructions: privateNotes }, { 'x-test-user': '10001' });
    assert.equal(saved.code, 200);
    assert.equal(saved.body.role, 'host');
    const selected = await req(instructionsPath, 'GET', undefined, { 'x-test-user': '10002' });
    assert.equal(selected.code, 200);
    assert.equal(selected.body.instructions, privateNotes);
    assert.equal((await req(instructionsPath)).code, 401);
    assert.equal((await req(instructionsPath, 'GET', undefined, { 'x-test-user': '10099' })).code, 403);
    const publicCheck = await req('/api/lobbies/' + gameId);
    assert.ok(!JSON.stringify(publicCheck.body).includes('JOIN-TEST-KEY'));

    assert.equal((await req('/api/lobbies/' + gameId + '/cancel', 'POST', {}, { 'x-test-user': '10002' })).code, 403);
    assert.equal((await req('/api/lobbies/' + gameId + '/cancel', 'POST', {})).code, 401);
    const cancel = await req('/api/lobbies/' + gameId + '/cancel', 'POST', {}, { 'x-test-user': '10001' });
    assert.equal(cancel.code, 200);
    assert.equal(cancel.body.game.status, 'cancelled');
    assert.equal((await req(instructionsPath, 'GET', undefined, { 'x-test-user': '10002' })).code, 403);
    assert.equal((await req(instructionsPath, 'POST', { instructions: privateNotes }, { 'x-test-user': '10001' })).code, 409);

    const a2 = await req('/admin/invites', 'POST', { post_id: '22222222' }, { authorization: 'Bearer ' + ADMIN });
    assert.equal(a2.code, 201);
    const t2 = new URL(a2.body.setupUrl).searchParams.get('invite');
    const lobby2 = await req(
      '/api/lobbies',
      'POST',
      { ...config, inviteToken: t2, mode: 'lottery', title: 'Lottery Game' },
      { 'x-test-user': '10001' }
    );
    assert.equal(lobby2.code, 201);
    const gid2 = lobby2.body.game.id;
    assert.equal((await req('/api/lobbies/' + gid2 + '/join', 'POST', {}, { 'x-test-user': '10002' })).code, 200);
    const withdraw = await req('/api/lobbies/' + gid2 + '/withdraw', 'POST', {}, { 'x-test-user': '10002' });
    assert.equal(withdraw.code, 200);
    assert.equal(withdraw.body.game.entryCount, 0);
    const repeated = await req('/api/lobbies/' + gid2 + '/join', 'POST', {}, { 'x-test-user': '10002' });
    assert.equal(repeated.code, 409);
    assert.equal(repeated.body.error, 'WITHDRAWN');

    console.log(`\u2713 parity suite passed for storeMode=${storeMode}`);
  } finally {
    server.close();
    if (api.close) api.close();
    await fs.rm(dir, { recursive: true, force: true });
  }
}

{
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'gn-parity-fail-'));
  let threw = false;
  try {
    await createLobbyApi({
      dataDir: dir,
      auth: { authenticated: () => null },
      mentions: { pending: [] },
      adminToken: ADMIN,
      publicOrigin: origin,
      joinSecretKey: JOIN_KEY,
      storeMode: 'sqlite',
    });
  } catch (e) {
    threw = true;
    assert.match(e.message, /migration|migrated_from_json/i);
  }
  assert.ok(threw, 'sqlite without migration marker must fail closed');
  await fs.rm(dir, { recursive: true, force: true });
  console.log('\u2713 sqlite without migration marker fails closed');
}

{
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'gn-parity-key-'));
  await prepareSqliteDir(dir);
  let threw = false;
  try {
    await createLobbyApi({
      dataDir: dir,
      auth: { authenticated: () => null },
      mentions: { pending: [] },
      adminToken: ADMIN,
      publicOrigin: origin,
      joinSecretKey: '',
      storeMode: 'sqlite',
    });
  } catch (e) {
    threw = true;
    assert.match(e.message, /X_JOIN_SECRET_KEY|32/);
  }
  assert.ok(threw, 'sqlite must require dedicated join secret');
  await fs.rm(dir, { recursive: true, force: true });
  console.log('\u2713 sqlite rejects missing dedicated join secret');
}

await runSuite('json');
await runSuite('sqlite');
console.log('\nAll lobby-api parity tests passed.');
