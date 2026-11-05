import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { createLobbyApi } from './lobby-api.mjs';
import { createXAuth } from './x-auth.mjs';

const origin = 'https://x.integration.test';
const clientId = 'offline-test-client';
const redirectUri = origin + '/auth/x/callback';
const tokenUrl = 'https://x-mock.invalid/oauth2/token';
const meUrl = 'https://x-mock.invalid/2/users/me';
const adminToken = 'offline-admin-token-never-valid';
const joinSecretKey = 'offline-join-secret-key-at-least-32-bytes';
const privateCode = 'PRIVATE-ROOM-CODE-OFFLINE-ONLY';
const accounts = {
  A: { id: '10001', username: 'host-a' },
  B: { id: '10002', username: 'moderator-b' },
  C: { id: '10003', username: 'unrelated-c' },
  D: { id: '10004', username: 'guest-d' },
  E: { id: '10005', username: 'guest-e' },
  F: { id: '10006', username: 'guest-f' },
};

const dataDir = await fs.mkdtemp(path.join(os.tmpdir(), 'gn-two-account-flow-'));
let now = 1_800_000_000_000;
let nextCode = 0;
const identitiesByCode = new Map();
const identitiesByToken = new Map();
const xRequests = [];
const mentions = { pending: [] };
const fetchImpl = async (input, options = {}) => {
  const url = String(input);
  xRequests.push(url);
  if (url !== tokenUrl && url !== meUrl) {
    throw new Error('Unexpected non-mock X request: ' + url);
  }
  if (url === tokenUrl) {
    assert.equal(options.method, 'POST');
    const form = new URLSearchParams(options.body);
    const identity = identitiesByCode.get(form.get('code'));
    assert.ok(identity, 'OAuth code must belong to a local mock identity');
    assert.equal(form.get('client_id'), clientId);
    assert.equal(form.get('redirect_uri'), redirectUri);
    assert.ok(form.get('code_verifier'));
    const accessToken = 'fake-local-access-' + form.get('code');
    identitiesByToken.set(accessToken, identity);
    return Response.json({ access_token: accessToken });
  }
  const identity = identitiesByToken.get(
    String(options.headers?.authorization || '').replace(/^Bearer /, ''),
  );
  assert.ok(identity, 'identity lookup must use a mock access token');
  return Response.json({ data: { id: identity.id, username: identity.username } });
};

const auth = await createXAuth({
  clientId,
  redirectUri,
  dataDir,
  fetchImpl,
  now: () => now,
  authorizationBase: 'https://x-mock.invalid/i/oauth2/authorize',
  tokenUrl,
  meUrl,
});
const lobbyApi = await createLobbyApi({
  dataDir,
  auth,
  mentions,
  adminToken,
  moderatorXId: accounts.B.id,
  publicOrigin: origin,
  now: () => now,
  joinSecretKey,
  random: () => 0,
});
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if (await auth.handle(req, res, url)) return;
  if (await lobbyApi.handle(req, res, url)) return;
  res.writeHead(404);
  res.end();
});
await new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(0, '127.0.0.1', resolve);
});
const base = 'http://127.0.0.1:' + server.address().port;

function applyCookies(jar, response) {
  const setCookies = response.headers.getSetCookie?.() || [response.headers.get('set-cookie')].filter(Boolean);
  for (const header of setCookies) {
    const first = header.split(';', 1)[0];
    const separator = first.indexOf('=');
    if (separator < 0) continue;
    const key = first.slice(0, separator);
    const value = decodeURIComponent(first.slice(separator + 1));
    if (/;\s*max-age=0(?:;|$)/i.test(header)) jar.delete(key);
    else jar.set(key, value);
  }
}

async function request(route, {
  method = 'GET',
  body,
  jar,
  headers = {},
} = {}) {
  const requestHeaders = { origin, 'content-type': 'application/json', ...headers };
  if (jar?.size) {
    requestHeaders.cookie = [...jar].map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join('; ');
  }
  const response = await fetch(base + route, {
    method,
    headers: requestHeaders,
    body: body === undefined ? undefined : JSON.stringify(body),
    redirect: 'manual',
  });
  if (jar) applyCookies(jar, response);
  const text = await response.text();
  let parsed = null;
  try { parsed = text ? JSON.parse(text) : null; } catch { /* OAuth redirects have no JSON body. */ }
  return { status: response.status, headers: response.headers, text, body: parsed };
}

async function login(accountKey, { invalidStateFirst = false } = {}) {
  const jar = new Map();
  const start = await request('/auth/x/start?next=%2Fmy-games', { jar });
  assert.equal(start.status, 302);
  const authorization = new URL(start.headers.get('location'));
  const state = authorization.searchParams.get('state');
  const stateCookie = jar.get('gn_x_oauth_state');
  assert.ok(state);
  assert.equal(stateCookie, state);
  assert.equal(authorization.searchParams.get('client_id'), clientId);
  assert.equal(authorization.searchParams.get('redirect_uri'), redirectUri);
  assert.equal(authorization.searchParams.get('scope'), 'tweet.read users.read');
  assert.equal(authorization.searchParams.get('code_challenge_method'), 'S256');

  if (invalidStateFirst) {
    const requestCount = xRequests.length;
    const invalid = await request('/auth/x/callback?state=wrong&code=not-used', { jar });
    assert.equal(invalid.status, 400);
    assert.equal(xRequests.length, requestCount, 'invalid state must not call mocked X');
  }

  const code = 'offline-' + accountKey + '-' + (++nextCode);
  identitiesByCode.set(code, accounts[accountKey]);
  const callback = await request(
    '/auth/x/callback?state=' + encodeURIComponent(state) + '&code=' + encodeURIComponent(code),
    { jar },
  );
  assert.equal(callback.status, 302);
  assert.equal(callback.headers.get('location'), '/my-games');
  assert.ok(jar.get('gn_x_session'));
  assert.equal(jar.has('gn_x_oauth_state'), false);
  return { jar, state, stateCookie, code };
}

function addMention(postId, authorId) {
  mentions.pending.push({
    post_id: postId,
    author_id: authorId,
    excerpt: '@gaming-network start a game',
    status: 'awaiting_review',
  });
}

async function approveByModerator(postId, jar) {
  const response = await request('/api/moderation/approve', {
    method: 'POST',
    body: { post_id: postId },
    jar,
  });
  assert.equal(response.status, 201, JSON.stringify(response.body));
  return new URL(response.body.setupUrl).searchParams.get('invite');
}

async function approveByAdmin(postId) {
  const response = await request('/admin/invites', {
    method: 'POST',
    body: { post_id: postId },
    headers: { authorization: 'Bearer ' + adminToken },
  });
  assert.equal(response.status, 201, JSON.stringify(response.body));
  return new URL(response.body.setupUrl).searchParams.get('invite');
}

async function createGame(inviteToken, jar, overrides = {}) {
  return request('/api/lobbies', {
    method: 'POST',
    jar,
    body: {
      inviteToken,
      game: 'fortnite',
      platform: 'pc',
      mode: 'first',
      seats: 2,
      roundSeconds: 60,
      title: 'Offline X Challenge',
      ...overrides,
    },
  });
}

try {
  const A = await login('A');
  const B = await login('B', { invalidStateFirst: true });
  const C = await login('C');
  const D = await login('D');
  const E = await login('E');
  const F = await login('F');

  const meA = await request('/api/me', { jar: A.jar });
  const meB = await request('/api/me', { jar: B.jar });
  assert.equal(meA.status, 200);
  assert.deepEqual(meA.body.user, accounts.A);
  assert.deepEqual(meB.body.user, accounts.B);
  assert.equal((await request('/api/me')).body.authenticated, false);
  assert.equal((await request('/api/my-games')).status, 401);

  const expiredFlowJar = new Map();
  const expiredStart = await request('/auth/x/start', { jar: expiredFlowJar });
  assert.equal(expiredStart.status, 302);
  const expiredState = expiredFlowJar.get('gn_x_oauth_state');
  const requestsBeforeExpiredCallback = xRequests.length;
  now += 600_001;
  const expiredCallback = await request(
    '/auth/x/callback?state=' + encodeURIComponent(expiredState) + '&code=expired-flow',
    { jar: expiredFlowJar },
  );
  assert.equal(expiredCallback.status, 400);
  assert.equal(xRequests.length, requestsBeforeExpiredCallback, 'expired PKCE state must not call mocked X');

  assert.equal((await request('/api/moderation/mentions')).status, 403);
  assert.equal((await request('/api/moderation/mentions', { jar: C.jar })).status, 403);
  assert.equal((await request('/api/moderation/mentions', { jar: B.jar })).status, 200);
  addMention('11111111', accounts.A.id);
  assert.equal((await request('/admin/invites', {
    method: 'POST', jar: B.jar, body: { post_id: '11111111' },
  })).status, 401, 'moderator session cannot use the bearer-admin endpoint');

  const revokedInvite = await approveByModerator('11111111', B.jar);
  const invite = await approveByModerator('11111111', B.jar);
  assert.notEqual(invite, revokedInvite);
  assert.equal((await createGame(revokedInvite, A.jar)).status, 403, 'reapproval revokes the prior unused invite');
  assert.equal((await createGame(invite, B.jar)).status, 403, 'another X identity cannot use the invite');

  const created = await createGame(invite, A.jar);
  assert.equal(created.status, 201, JSON.stringify(created.body));
  const gameId = created.body.game.id;
  const lobbyPath = '/api/lobbies/' + gameId;
  assert.equal((await createGame(invite, A.jar)).status, 403, 'a consumed invitation cannot be replayed');

  assert.equal((await request(lobbyPath + '/join', { method: 'POST', jar: B.jar, body: {} })).status, 200);
  const duplicate = await request(lobbyPath + '/join', { method: 'POST', jar: B.jar, body: {} });
  assert.equal(duplicate.status, 409);
  assert.equal(duplicate.body.error, 'DUPLICATE');
  assert.equal((await request(lobbyPath + '/join', { method: 'POST', jar: D.jar, body: {} })).status, 200);
  assert.equal((await request(lobbyPath)).body.game.status, 'ready');
  const overflow = await request(lobbyPath + '/join', { method: 'POST', jar: C.jar, body: {} });
  assert.equal(overflow.status, 409);
  assert.ok(['CLOSED', 'FULL'].includes(overflow.body.error));

  assert.equal((await request(lobbyPath + '/cancel', { method: 'POST', jar: B.jar, body: {} })).status, 403);
  assert.equal((await request(lobbyPath + '/replace', { method: 'POST', jar: D.jar, body: { seat: 1 } })).status, 403);
  assert.equal((await request(lobbyPath + '/waitlist', { method: 'POST', jar: E.jar, body: {} })).body.game.waitlist[0].name, '@guest-e');
  assert.equal((await request(lobbyPath + '/waitlist', { method: 'POST', jar: F.jar, body: {} })).body.game.waitlist[1].name, '@guest-f');
  assert.equal((await request(lobbyPath + '/waitlist', { method: 'POST', jar: E.jar, body: {} })).status, 409);

  const saveNotes = await request(lobbyPath + '/join-details', {
    method: 'POST', jar: A.jar, body: { instructions: privateCode },
  });
  assert.equal(saveNotes.status, 200);
  assert.equal((await request(lobbyPath + '/join-details', {
    method: 'POST', jar: B.jar, body: { instructions: 'GUEST-MUST-NOT-EDIT' },
  })).status, 403);
  assert.equal((await request(lobbyPath + '/join-details', { jar: B.jar })).body.instructions, privateCode);
  assert.equal((await request(lobbyPath + '/join-details', { jar: C.jar })).status, 403);
  assert.equal((await request(lobbyPath + '/join-details')).status, 401);

  const beforeReplacement = await request(lobbyPath);
  assert.equal(beforeReplacement.body.game.entries[0].seat, 0);
  assert.equal(beforeReplacement.body.game.entries[1].seat, 1);
  const replacement = await request(lobbyPath + '/replace', {
    method: 'POST', jar: A.jar, body: { seat: 1 },
  });
  assert.equal(replacement.status, 200);
  assert.equal(replacement.body.game.waitlistCount, 1);
  assert.deepEqual(replacement.body.game.waitlist, [{ name: '@guest-f', position: 1 }]);
  assert.equal((await request(lobbyPath + '/join-details', { jar: D.jar })).status, 403, 'removed no-show loses private access');
  assert.equal((await request(lobbyPath + '/join-details', { jar: E.jar })).body.instructions, privateCode);
  assert.equal((await request(lobbyPath + '/waitlist', { method: 'POST', jar: D.jar, body: {} })).body.error, 'REMOVED');
  const gamesDAfterReplacement = await request('/api/my-games', { jar: D.jar });
  assert.equal(gamesDAfterReplacement.body.games.find(game => game.id === gameId).viewerRole, 'removed');
  assert.equal(gamesDAfterReplacement.body.games.find(game => game.id === gameId).viewerSelected, false);
  assert.equal((await request(lobbyPath + '/withdraw', { method: 'POST', jar: F.jar, body: {} })).status, 200);
  const gamesF = await request('/api/my-games', { jar: F.jar });
  assert.equal(gamesF.body.games.find(game => game.id === gameId).viewerRole, 'withdrawn');
  assert.deepEqual((await request('/api/my-games', { jar: C.jar })).body.games, [], 'unrelated account sees no private games');
  const gamesB = await request('/api/my-games', { jar: B.jar });
  assert.equal(gamesB.body.games[0].viewerRole, 'player');
  assert.equal(gamesB.body.games.find(game => game.id === gameId).viewerSelected, true);
  assert.ok(!JSON.stringify(gamesB.body).includes(privateCode));

  const publicBeforeCancel = JSON.stringify((await request('/api/lobbies')).body);
  const oneBeforeCancel = JSON.stringify((await request(lobbyPath)).body);
  for (const leak of [accounts.A.id, accounts.B.id, accounts.C.id, adminToken, joinSecretKey, privateCode, 'ownerXId', 'joinSecrets']) {
    assert.ok(!publicBeforeCancel.includes(leak), 'public feed leaked ' + leak);
    assert.ok(!oneBeforeCancel.includes(leak), 'public lobby leaked ' + leak);
  }
  assert.equal((await request(lobbyPath + '/cancel', { method: 'POST', jar: A.jar, body: {} })).body.game.status, 'cancelled');
  assert.equal((await request(lobbyPath + '/join-details', { jar: B.jar })).status, 403, 'cancellation revokes selected-player access');
  assert.equal((await request(lobbyPath + '/join-details', { jar: E.jar })).status, 403);

  addMention('22222222', accounts.A.id);
  const withdrawalInvite = await approveByAdmin('22222222');
  const withdrawalGame = await createGame(withdrawalInvite, A.jar, { seats: 3, title: 'Withdrawal test' });
  assert.equal(withdrawalGame.status, 201);
  const withdrawalPath = '/api/lobbies/' + withdrawalGame.body.game.id;
  assert.equal((await request(withdrawalPath + '/join', { method: 'POST', jar: B.jar, body: {} })).status, 200);
  assert.equal((await request(withdrawalPath + '/withdraw', { method: 'POST', jar: B.jar, body: {} })).status, 200);
  const withdrawnJoin = await request(withdrawalPath + '/join', { method: 'POST', jar: B.jar, body: {} });
  assert.equal(withdrawnJoin.status, 409);
  assert.equal(withdrawnJoin.body.error, 'WITHDRAWN');
  assert.equal((await request('/api/my-games', { jar: B.jar })).body.games.find(game => game.id === withdrawalGame.body.game.id).viewerRole, 'withdrawn');
  assert.equal((await request(withdrawalPath + '/cancel', { method: 'POST', jar: A.jar, body: {} })).status, 200);

  addMention('33333333', accounts.A.id);
  const lotteryInvite = await approveByAdmin('33333333');
  const lottery = await createGame(lotteryInvite, A.jar, {
    mode: 'lottery',
    seats: 2,
    title: 'Five-minute selection',
  });
  assert.equal(lottery.status, 201);
  const lotteryId = lottery.body.game.id;
  const lotteryPath = '/api/lobbies/' + lotteryId;
  assert.equal((await request(lotteryPath + '/join-details', { method: 'POST', jar: A.jar, body: { instructions: privateCode } })).status, 200);
  for (const account of [B, D, F]) {
    assert.equal((await request(lotteryPath + '/join', { method: 'POST', jar: account.jar, body: {} })).status, 200);
  }
  const beforeClose = await request(lotteryPath);
  assert.equal(beforeClose.body.game.status, 'open');
  assert.ok(beforeClose.body.game.entries.every(entry => entry.selected === null));
  assert.equal((await request(lotteryPath + '/join-details', { jar: B.jar })).status, 403);
  assert.ok(!JSON.stringify(beforeClose.body).includes(privateCode));

  now = lottery.body.game.entryClosesAt;
  const atDeadline = await request(lotteryPath);
  assert.equal(atDeadline.status, 200);
  assert.equal(atDeadline.body.game.status, 'ready');
  assert.deepEqual(
    atDeadline.body.game.entries.filter(entry => entry.selected).map(entry => entry.name),
    ['@guest-d', '@guest-f'],
    'injected deterministic random choices select one stable two-player result',
  );
  const selectedAgain = await request(lotteryPath);
  assert.deepEqual(selectedAgain.body, atDeadline.body, 'subsequent views do not redraw the lottery');
  const lateJoin = await request(lotteryPath + '/join', { method: 'POST', jar: C.jar, body: {} });
  assert.equal(lateJoin.status, 409);
  assert.ok(['CLOSED', 'FULL'].includes(lateJoin.body.error));
  const gamesDAfterDraw = await request('/api/my-games', { jar: D.jar });
  assert.equal(gamesDAfterDraw.body.games.find(game => game.id === lotteryId).viewerSelected, true);
  assert.equal((await request('/api/my-games', { jar: B.jar })).body.games.find(game => game.id === lotteryId).viewerSelected, false);
  assert.equal((await request(lotteryPath + '/join-details', { jar: D.jar })).body.instructions, privateCode);
  assert.equal((await request(lotteryPath + '/join-details', { jar: B.jar })).status, 403);
  assert.equal((await request(lotteryPath + '/join-details', { jar: C.jar })).status, 403);

  const publicLottery = JSON.stringify((await request('/api/lobbies')).body);
  const publicLotteryOne = JSON.stringify(atDeadline.body);
  for (const leak of [
    accounts.A.id, accounts.B.id, accounts.D.id, accounts.F.id,
    adminToken, joinSecretKey, privateCode, 'ownerXId', 'joinSecrets',
    'inviteToken', 'fake-local-access',
  ]) {
    assert.ok(!publicLottery.includes(leak), 'lottery public feed leaked ' + leak);
    assert.ok(!publicLotteryOne.includes(leak), 'lottery public lobby leaked ' + leak);
  }

  const replay = await request(
    '/auth/x/callback?state=' + encodeURIComponent(B.state) + '&code=' + encodeURIComponent(B.code),
    { headers: { cookie: 'gn_x_oauth_state=' + B.stateCookie } },
  );
  assert.equal(replay.status, 400, 'OAuth callback state cannot be replayed');
  assert.equal((await request('/auth/logout', { method: 'POST', jar: B.jar })).status, 200);
  assert.equal((await request('/api/me', { jar: B.jar })).body.authenticated, false);
  assert.equal((await request('/api/my-games', { jar: B.jar })).status, 401);

  addMention('44444444', accounts.A.id);
  const expiringInvite = await approveByAdmin('44444444');
  now += 86_400_001;
  assert.equal((await request('/api/me', { jar: A.jar })).body.authenticated, false);
  const freshA = await login('A');
  const expiredInvite = await createGame(expiringInvite, freshA.jar);
  assert.equal(expiredInvite.status, 403);
  assert.equal(expiredInvite.body.error, 'INVITE_INVALID');

  const authDb = JSON.parse(await fs.readFile(path.join(dataDir, 'x-auth-sessions.json'), 'utf8'));
  const serializedAuth = JSON.stringify(authDb);
  for (const token of identitiesByToken.keys()) {
    assert.ok(!serializedAuth.includes(token), 'OAuth access tokens must never be persisted');
  }
  assert.equal(new Set(xRequests).size, 2, 'mocked OAuth used only token exchange and users/me endpoints');
  assert.ok(xRequests.every(url => url === tokenUrl || url === meUrl));
  console.log('Offline two-account OAuth, lobby, lottery, and privacy flow passed');
} finally {
  await new Promise(resolve => server.close(resolve));
  await fs.rm(dataDir, { recursive: true, force: true });
}
