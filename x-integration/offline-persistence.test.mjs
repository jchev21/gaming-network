import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { createLobbyApi } from './lobby-api.mjs';
import { createXAuth } from './x-auth.mjs';

const origin = 'https://x.persistence.test';
const clientId = 'offline-persistence-client';
const redirectUri = origin + '/auth/x/callback';
const tokenUrl = 'https://x-persistence-mock.invalid/oauth2/token';
const meUrl = 'https://x-persistence-mock.invalid/2/users/me';
const adminToken = 'offline-persistence-admin-token';
const joinSecretKey = 'offline-persistence-key-with-more-than-32-bytes';
const privateInstructions = 'PRIVATE-' + crypto.randomBytes(16).toString('hex');
const accounts = {
  A: { id: '20001', username: 'persist-host' },
  B: { id: '20002', username: 'persist-moderator' },
  C: { id: '20003', username: 'persist-winner-c' },
  D: { id: '20004', username: 'persist-winner-d' },
};
const dataDir = await fs.mkdtemp(path.join(os.tmpdir(), 'gn-offline-persistence-'));
const codes = new Map();
const tokens = new Map();
const mockedXRequests = [];
let now = 1_800_000_100_000;
let nextCode = 0;
const mentions = {
  pending: [{
    post_id: '55555555',
    author_id: accounts.A.id,
    excerpt: '@gaming-network start a game',
    status: 'awaiting_review',
  }],
};

const fetchImpl = async (input, options = {}) => {
  const url = String(input);
  mockedXRequests.push(url);
  if (url !== tokenUrl && url !== meUrl) throw new Error('Unexpected non-mock X request: ' + url);
  if (url === tokenUrl) {
    assert.equal(options.method, 'POST');
    const form = new URLSearchParams(options.body);
    const account = codes.get(form.get('code'));
    assert.ok(account, 'token exchange code must map to a local test identity');
    assert.equal(form.get('client_id'), clientId);
    assert.equal(form.get('redirect_uri'), redirectUri);
    assert.ok(form.get('code_verifier'));
    const accessToken = 'offline-persistence-access-' + form.get('code');
    tokens.set(accessToken, account);
    return Response.json({ access_token: accessToken });
  }
  const accessToken = String(options.headers?.authorization || '').replace(/^Bearer /, '');
  const account = tokens.get(accessToken);
  assert.ok(account, 'users/me must use a mock bearer token');
  return Response.json({ data: account });
};

async function boot(random) {
  const auth = await createXAuth({
    clientId,
    redirectUri,
    dataDir,
    fetchImpl,
    now: () => now,
    authorizationBase: 'https://x-persistence-mock.invalid/i/oauth2/authorize',
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
    random,
    joinSecretKey,
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
  return {
    server,
    close: () => new Promise((resolve, reject) => {
      server.close(error => error ? reject(error) : resolve());
    }),
  };
}

function updateJar(jar, response) {
  const setCookies = response.headers.getSetCookie?.() || [response.headers.get('set-cookie')].filter(Boolean);
  for (const header of setCookies) {
    const first = header.split(';', 1)[0];
    const separator = first.indexOf('=');
    if (separator < 0) continue;
    const name = first.slice(0, separator);
    const value = decodeURIComponent(first.slice(separator + 1));
    if (/;\s*max-age=0(?:;|$)/i.test(header)) jar.delete(name);
    else jar.set(name, value);
  }
}

async function request(runtime, route, {
  method = 'GET',
  body,
  jar,
  headers = {},
} = {}) {
  const requestHeaders = { origin, 'content-type': 'application/json', ...headers };
  if (jar?.size) {
    requestHeaders.cookie = [...jar]
      .map(([name, value]) => `${name}=${encodeURIComponent(value)}`)
      .join('; ');
  }
  const response = await fetch('http://127.0.0.1:' + runtime.server.address().port + route, {
    method,
    headers: requestHeaders,
    body: body === undefined ? undefined : JSON.stringify(body),
    redirect: 'manual',
  });
  if (jar) updateJar(jar, response);
  const text = await response.text();
  let parsed = null;
  try { parsed = text ? JSON.parse(text) : null; } catch { /* Successful OAuth callbacks redirect without JSON. */ }
  return { status: response.status, headers: response.headers, text, body: parsed };
}

async function login(runtime, key, { checkInvalidState = false } = {}) {
  const jar = new Map();
  const start = await request(runtime, '/auth/x/start?next=%2Fmy-games', { jar });
  assert.equal(start.status, 302);
  const authorization = new URL(start.headers.get('location'));
  const state = authorization.searchParams.get('state');
  const stateCookie = jar.get('gn_x_oauth_state');
  assert.ok(state);
  assert.equal(stateCookie, state);

  if (checkInvalidState) {
    const requestCount = mockedXRequests.length;
    const invalid = await request(runtime, '/auth/x/callback?state=bad&code=not-used', { jar });
    assert.equal(invalid.status, 400);
    assert.equal(mockedXRequests.length, requestCount);
  }

  const code = 'offline-persist-' + key + '-' + (++nextCode);
  codes.set(code, accounts[key]);
  const callback = await request(
    runtime,
    '/auth/x/callback?state=' + encodeURIComponent(state) + '&code=' + encodeURIComponent(code),
    { jar },
  );
  assert.equal(callback.status, 302);
  assert.equal(callback.headers.get('location'), '/my-games');
  assert.ok(jar.get('gn_x_session'));
  assert.equal(jar.has('gn_x_oauth_state'), false);
  return { jar, state, stateCookie };
}

let runtime;
try {
  let initialRandomCalls = 0;
  runtime = await boot(() => {
    initialRandomCalls++;
    return 0;
  });
  const host = await login(runtime, 'A', { checkInvalidState: true });
  const moderator = await login(runtime, 'B');
  const entrantC = await login(runtime, 'C');
  const entrantD = await login(runtime, 'D');

  const pendingJar = new Map();
  const pendingStart = await request(runtime, '/auth/x/start', { jar: pendingJar });
  assert.equal(pendingStart.status, 302);
  const pendingState = pendingJar.get('gn_x_oauth_state');
  now += 600_000;
  const expiredAtBoundary = await request(
    runtime,
    '/auth/x/callback?state=' + encodeURIComponent(pendingState) + '&code=expired-at-boundary',
    { jar: pendingJar },
  );
  assert.equal(expiredAtBoundary.status, 400, 'PKCE state expires at its exact ten-minute boundary');

  assert.equal((await request(runtime, '/api/moderation/approve', {
    method: 'POST', body: { post_id: '55555555' }, jar: host.jar,
  })).status, 403, 'non-moderator host cannot approve an invitation');
  assert.equal((await request(runtime, '/api/moderation/approve', {
    method: 'POST', body: { post_id: '55555555' }, jar: entrantC.jar,
  })).status, 403, 'unrelated account cannot approve an invitation');
  const approved = await request(runtime, '/api/moderation/approve', {
    method: 'POST',
    body: { post_id: '55555555' },
    jar: moderator.jar,
  });
  assert.equal(approved.status, 201);
  const inviteToken = new URL(approved.body.setupUrl).searchParams.get('invite');
  const wrongHost = await request(runtime, '/api/lobbies', {
    method: 'POST',
    jar: moderator.jar,
    body: { inviteToken, mode: 'lottery', seats: 2, game: 'fortnite', platform: 'pc', title: 'Persisted draw' },
  });
  assert.equal(wrongHost.status, 403);

  const created = await request(runtime, '/api/lobbies', {
    method: 'POST',
    jar: host.jar,
    body: { inviteToken, mode: 'lottery', seats: 2, game: 'fortnite', platform: 'pc', title: 'Persisted draw' },
  });
  assert.equal(created.status, 201);
  const gameId = created.body.game.id;
  const gamePath = '/api/lobbies/' + gameId;
  assert.equal((await request(runtime, '/api/lobbies', {
    method: 'POST',
    jar: host.jar,
    body: { inviteToken, mode: 'lottery', seats: 2, game: 'fortnite', platform: 'pc', title: 'Invite replay' },
  })).status, 403);

  assert.equal((await request(runtime, gamePath + '/join-details', {
    method: 'POST',
    jar: host.jar,
    body: { instructions: privateInstructions },
  })).status, 200);
  for (const entrant of [moderator, entrantC, entrantD]) {
    assert.equal((await request(runtime, gamePath + '/join', {
      method: 'POST', jar: entrant.jar, body: {},
    })).status, 200);
  }
  now = created.body.game.entryClosesAt;
  const finalizedFeed = await request(runtime, '/api/lobbies?status=ready');
  assert.equal(finalizedFeed.status, 200);
  assert.equal(finalizedFeed.body.games.find(game => game.id === gameId).confirmedCount, 2);
  assert.equal(initialRandomCalls, 2, 'public feed finalizes once with the injected source');
  const draw = await request(runtime, gamePath);
  assert.equal(draw.status, 200);
  assert.equal(draw.body.game.status, 'ready');
  assert.deepEqual(
    draw.body.game.entries.filter(entry => entry.selected).map(entry => entry.name),
    ['@persist-winner-c', '@persist-winner-d'],
  );
  assert.equal((await request(runtime, gamePath + '/join-details', { jar: entrantC.jar })).body.instructions, privateInstructions);
  assert.equal((await request(runtime, gamePath + '/join-details', { jar: moderator.jar })).status, 403);

  await runtime.close();
  runtime = undefined;
  let forbiddenRedrawCalls = 0;
  runtime = await boot(() => {
    forbiddenRedrawCalls++;
    throw new Error('Persisted lottery must not be redrawn');
  });

  assert.deepEqual((await request(runtime, '/api/me', { jar: host.jar })).body.user, accounts.A);
  assert.equal((await request(runtime, '/api/lobbies', {
    method: 'POST',
    jar: host.jar,
    body: { inviteToken, mode: 'lottery', seats: 2, game: 'fortnite', platform: 'pc', title: 'Replay after restart' },
  })).status, 403, 'consumed invite remains unusable after handlers restart');
  const persistedDraw = await request(runtime, gamePath);
  assert.deepEqual(persistedDraw.body, draw.body);
  assert.equal(forbiddenRedrawCalls, 0, 'loaded winners must be reused without calling the random source');
  assert.equal((await request(runtime, gamePath + '/join-details', { jar: entrantC.jar })).body.instructions, privateInstructions);
  assert.equal((await request(runtime, gamePath + '/join-details', { jar: moderator.jar })).status, 403);
  assert.equal((await request(runtime, gamePath + '/join-details')).status, 401);

  const hostGames = await request(runtime, '/api/my-games', { jar: host.jar });
  assert.equal(hostGames.body.games.find(game => game.id === gameId).viewerRole, 'host');
  assert.ok(!JSON.stringify(hostGames.body).includes(privateInstructions));
  const outsiderGames = await request(runtime, '/api/my-games', { jar: moderator.jar });
  assert.equal(outsiderGames.body.games.find(game => game.id === gameId).viewerSelected, false);

  const publicIndividual = JSON.stringify(persistedDraw.body);
  const publicFeed = JSON.stringify((await request(runtime, '/api/lobbies')).body);
  const forbiddenValues = [
    accounts.A.id, accounts.B.id, accounts.C.id, accounts.D.id,
    inviteToken, adminToken, joinSecretKey, privateInstructions, 'offline-persistence-access-',
  ];
  const forbiddenFields = [
    'ownerXId', 'xId', 'joinSecrets', 'inviteToken', 'access_token',
    'authorization', 'adminToken', 'privateInstructions',
  ];
  for (const payload of [publicIndividual, publicFeed]) {
    for (const value of forbiddenValues) assert.ok(!payload.includes(value), 'public payload leaked a private value');
    for (const field of forbiddenFields) assert.ok(!payload.includes('"' + field + '"'), 'public payload exposed ' + field);
  }

  const storedLobbies = JSON.parse(await fs.readFile(path.join(dataDir, 'x-lobbies.json'), 'utf8'));
  assert.ok(storedLobbies.invites);
  assert.ok(storedLobbies.joinSecrets[gameId]?.iv);
  assert.ok(!JSON.stringify(storedLobbies).includes(inviteToken));
  assert.ok(!JSON.stringify(storedLobbies).includes(privateInstructions), 'join instructions must remain encrypted at rest');
  const storedAuth = await fs.readFile(path.join(dataDir, 'x-auth-sessions.json'), 'utf8');
  for (const token of tokens.keys()) assert.ok(!storedAuth.includes(token), 'OAuth access tokens must not persist');
  assert.ok(mockedXRequests.every(url => url === tokenUrl || url === meUrl));
  assert.equal(new Set(mockedXRequests).size, 2);
  console.log('Offline restart, persistence, invite, PKCE boundary, and privacy regression passed');
} finally {
  if (runtime) await runtime.close();
  await fs.rm(dataDir, { recursive: true, force: true });
}
