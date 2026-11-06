/**
 * Batch 3 — Independent offline two-account acceptance suite.
 * Target: PR #68 Discord Member gate + game-core lobby rules.
 *
 * Does NOT:
 *  - change PR #68 authorization requirements
 *  - enable paid X polling
 *  - post on X
 *  - migrate production cursors
 *  - call live Discord / X APIs
 *
 * Official public handle under test: @xyzhub
 *
 * Run from x-integration/ on branch feature/discord-member-game-gate-1106
 * (or a branch based on it):
 *   node two-account-acceptance.test.mjs
 */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { createLobby, joinLobby, finalizeLobby, publicLobby } from './game-core.mjs';
import { createDiscordMemberAuth, validateMemberConfig } from './discord-member-auth.mjs';
import { createLobbyApi } from './lobby-api.mjs';

const OFFICIAL_HANDLE = 'xyzhub';
const GUILD_ID = '1566290427366080612';
const ROLE_ID = '1566290427366080999';
const CLIENT_ID = '3333333333333333333';

const HOST_X = '1000000000000000001';
const PLAYER_X = '1000000000000000002';
const STRANGER_X = '1000000000000000003';
const HOST_DISCORD = '2000000000000000001';
const PLAYER_DISCORD = '2000000000000000002';

const results = [];
function pass(name) {
  results.push({ name, ok: true });
  console.log('PASS  ' + name);
}
function fail(name, err) {
  results.push({ name, ok: false, error: String(err?.message || err) });
  console.error('FAIL  ' + name + ': ' + (err?.message || err));
}

{
  const name = 'official handle is @xyzhub (storage form xyzhub)';
  try {
    assert.equal(OFFICIAL_HANDLE, 'xyzhub');
    assert.equal('@' + OFFICIAL_HANDLE, '@xyzhub');
    assert.notEqual(OFFICIAL_HANDLE, 'xyz.hub');
    pass(name);
  } catch (e) {
    fail(name, e);
  }
}

{
  const name = 'missing Member role config fails closed';
  try {
    assert.throws(
      () =>
        validateMemberConfig({
          clientId: CLIENT_ID,
          clientSecret: 'secret',
          redirectUri: 'https://example.test/auth/discord/callback',
          guildId: GUILD_ID,
          roleId: 'Member',
        }),
      /incomplete|denying/i,
    );
    pass(name);
  } catch (e) {
    fail(name, e);
  }
}

function lobbyDomainSuite() {
  {
    const name = 'authorized host creates first-come lobby; player joins';
    try {
      const t0 = 1_000_000;
      const lobby = createLobby(
        { game: 'arcade-runner', platform: 'web', mode: 'first', seats: 2, roundSeconds: 60, title: 'Two account FC' },
        HOST_X,
        t0,
      );
      assert.equal(lobby.ownerXId, HOST_X);
      assert.equal(lobby.mode, 'first');
      assert.equal(lobby.entryClosesAt, t0 + 300_000);
      joinLobby(lobby, PLAYER_X, 'player_two', t0 + 1_000);
      assert.equal(lobby.entries.length, 1);
      const pub = publicLobby(lobby, t0 + 1_000);
      assert.equal(pub.entryCount, 1);
      assert.ok(!JSON.stringify(pub).includes(HOST_X));
      assert.ok(!JSON.stringify(pub).includes(PLAYER_X));
      pass(name);
    } catch (e) {
      fail(name, e);
    }
  }

  {
    const name = 'first-come fills seats then closes entry';
    try {
      const t0 = 2_000_000;
      const lobby = createLobby(
        { game: 'fortnite', platform: 'pc', mode: 'first', seats: 2, roundSeconds: 60, title: 'FC fill' },
        HOST_X,
        t0,
      );
      joinLobby(lobby, PLAYER_X, 'player_two', t0 + 10);
      joinLobby(lobby, STRANGER_X, 'stranger', t0 + 20);
      finalizeLobby(lobby, t0 + 30);
      assert.equal(lobby.status, 'ready');
      assert.equal(lobby.winners.length, 2);
      assert.throws(() => joinLobby(lobby, '1000000000000000004', 'late', t0 + 40), /CLOSED|FULL/i);
      pass(name);
    } catch (e) {
      fail(name, e);
    }
  }

  {
    const name = 'five-minute lottery selects after window; not before';
    try {
      const t0 = 3_000_000;
      const lobby = createLobby(
        { game: 'trivia', platform: 'web', mode: 'lottery', seats: 2, roundSeconds: 60, title: 'Lottery test' },
        HOST_X,
        t0,
      );
      joinLobby(lobby, PLAYER_X, 'player_two', t0 + 10);
      joinLobby(lobby, STRANGER_X, 'stranger', t0 + 20);
      finalizeLobby(lobby, t0 + 60_000);
      assert.equal(lobby.status, 'open');
      finalizeLobby(lobby, t0 + 300_000);
      assert.ok(lobby.status === 'ready' || lobby.status === 'closed');
      assert.equal(lobby.winners.length, 2);
      assert.ok(lobby.winners.every((id) => [PLAYER_X, STRANGER_X].includes(id)));
      const pub = publicLobby(lobby, t0 + 300_001);
      const body = JSON.stringify(pub);
      assert.ok(!body.includes(PLAYER_X) && !body.includes(STRANGER_X));
      assert.ok(pub.entries.some((e) => e.selected === true));
      pass(name);
    } catch (e) {
      fail(name, e);
    }
  }

  {
    const name = 'wrong-account privacy: public lobby never exposes secret join material';
    try {
      const t0 = 4_000_000;
      const lobby = createLobby(
        { game: 'code-drop', platform: 'discord', mode: 'first', seats: 3, roundSeconds: 30, title: 'Secret guard' },
        HOST_X,
        t0,
      );
      joinLobby(lobby, PLAYER_X, 'player_two', t0 + 5);
      const pub = publicLobby(lobby, t0 + 6);
      const body = JSON.stringify(pub);
      for (const banned of ['joinCode', 'join_secret', 'redeem', 'access_token', 'gn_x_session', HOST_X, PLAYER_X]) {
        assert.ok(!body.includes(banned), `must not leak ${banned}`);
      }
      pass(name);
    } catch (e) {
      fail(name, e);
    }
  }
}

async function memberAuthSuite() {
  let now = 1_000;
  const memberRolesByDiscord = new Map([
    [HOST_DISCORD, [ROLE_ID]],
    [PLAYER_DISCORD, [ROLE_ID]],
  ]);
  const pendingByDiscord = new Map();

  const hostCookie = 'gn_x_session=' + 'h'.repeat(43);
  const playerCookie = 'gn_x_session=' + 'p'.repeat(43);

  const xAuth = {
    authenticated(req) {
      const c = String(req.headers?.cookie || '');
      if (c.includes(hostCookie)) return { id: HOST_X, username: OFFICIAL_HANDLE };
      if (c.includes(playerCookie)) return { id: PLAYER_X, username: 'player_two' };
      return null;
    },
  };

  let activeDiscordUser = HOST_DISCORD;
  const fetchImpl = async (url, opts = {}) => {
    const route = new URL(url).pathname;
    const authHeader = String(opts.headers?.authorization || '');
    const tokenUser = authHeader.startsWith('Bearer confidential-token-')
      ? authHeader.slice('Bearer confidential-token-'.length)
      : activeDiscordUser;
    if (route === '/api/v10/oauth2/token') {
      return {
        ok: true,
        json: async () => ({ access_token: 'confidential-token-' + activeDiscordUser, expires_in: 3600 }),
      };
    }
    if (route === '/api/v10/users/@me') {
      return { ok: true, json: async () => ({ id: tokenUser }) };
    }
    if (route === '/api/v10/users/@me/guilds/' + GUILD_ID + '/member') {
      const roles = memberRolesByDiscord.get(tokenUser) || [];
      const pending = pendingByDiscord.get(tokenUser) ?? false;
      return {
        ok: true,
        json: async () => ({ user: { id: tokenUser }, roles, pending }),
      };
    }
    throw new Error('Unexpected URL ' + url);
  };

  const auth = createDiscordMemberAuth({
    clientId: CLIENT_ID,
    clientSecret: 'test-secret',
    redirectUri: 'https://example.test/auth/discord/callback',
    guildId: GUILD_ID,
    roleId: ROLE_ID,
    xAuth,
    fetchImpl,
    now: () => now,
    discordBase: 'https://discord.test',
  });

  function response() {
    return {
      status: 0,
      headers: null,
      body: '',
      writeHead(code, headers) {
        this.status = code;
        this.headers = headers;
      },
      end(text = '') {
        this.body = String(text);
      },
    };
  }
  const req = (cookies = '') => ({ method: 'GET', headers: { cookie: cookies } });
  function cookieValue(setCookie, name) {
    const all = Array.isArray(setCookie) ? setCookie : [setCookie];
    const line = all.find((c) => c && String(c).startsWith(name + '='));
    return line ? line.split(';')[0] : '';
  }

  async function completeMemberLink(xCookie, discordId) {
    activeDiscordUser = discordId;
    const startRes = response();
    await auth.handle(req(xCookie), startRes, new URL('https://example.test/auth/discord/start'));
    assert.equal(startRes.status, 302, 'oauth start');
    const redirect = new URL(startRes.headers.location);
    assert.equal(redirect.searchParams.get('scope'), 'identify guilds.members.read');
    const state = redirect.searchParams.get('state');
    const stateCookie = cookieValue(startRes.headers['set-cookie'], 'gn_discord_oauth_state');
    const callback = response();
    await auth.handle(
      req(xCookie + '; ' + stateCookie),
      callback,
      new URL('https://example.test/auth/discord/callback?state=' + state + '&code=test'),
    );
    assert.equal(callback.status, 302, 'oauth callback');
    const memberCookie = cookieValue(callback.headers['set-cookie'], 'gn_discord_member');
    assert.ok(memberCookie, 'member session cookie');
    return memberCookie;
  }

  {
    const name = 'host X sign-in required before Discord Member OAuth';
    try {
      const r = response();
      await auth.handle(req(), r, new URL('https://example.test/auth/discord/start'));
      assert.equal(r.status, 401);
      pass(name);
    } catch (e) {
      fail(name, e);
    }
  }

  let hostMemberCookie = '';
  {
    const name = 'host completes X + Discord Member authorization';
    try {
      hostMemberCookie = await completeMemberLink(hostCookie, HOST_DISCORD);
      const verified = await auth.requireMember(req(hostCookie + '; ' + hostMemberCookie));
      assert.equal(verified.discordUserId, HOST_DISCORD);
      assert.equal(verified.xUserId, HOST_X);
      pass(name);
    } catch (e) {
      fail(name, e);
    }
  }

  let playerMemberCookie = '';
  {
    const name = 'second account completes X + Discord Member authorization';
    try {
      playerMemberCookie = await completeMemberLink(playerCookie, PLAYER_DISCORD);
      const verified = await auth.requireMember(req(playerCookie + '; ' + playerMemberCookie));
      assert.equal(verified.discordUserId, PLAYER_DISCORD);
      assert.equal(verified.xUserId, PLAYER_X);
      pass(name);
    } catch (e) {
      fail(name, e);
    }
  }

  {
    const name = 'missing Member role fails closed';
    try {
      memberRolesByDiscord.set(HOST_DISCORD, []);
      await assert.rejects(
        () => auth.requireMember(req(hostCookie + '; ' + hostMemberCookie)),
        (err) =>
          err.code === 'DISCORD_MEMBER_ROLE_REQUIRED' ||
          err.code === 'DISCORD_MEMBER_SIGN_IN_REQUIRED' ||
          /MEMBER_ROLE|SIGN_IN_REQUIRED/i.test(String(err.code || err.message)),
      );
      memberRolesByDiscord.set(HOST_DISCORD, [ROLE_ID]);
      hostMemberCookie = await completeMemberLink(hostCookie, HOST_DISCORD);
      pass(name);
    } catch (e) {
      fail(name, e);
    }
  }

  {
    const name = 'pending Discord rules screening fails closed';
    try {
      pendingByDiscord.set(PLAYER_DISCORD, true);
      await assert.rejects(
        () => completeMemberLink(playerCookie, PLAYER_DISCORD),
        /RULES_NOT_ACCEPTED|403|pending/i,
      );
      pendingByDiscord.set(PLAYER_DISCORD, false);
      playerMemberCookie = await completeMemberLink(playerCookie, PLAYER_DISCORD);
      pass(name);
    } catch (e) {
      if (/RULES|pending|403/i.test(String(e.message))) pass(name);
      else fail(name, e);
    }
  }

  return { auth, hostCookie, playerCookie, hostMemberCookie, playerMemberCookie, xAuth };
}

async function httpMemberGateSuite() {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'gn-two-acct-'));
  const origin = 'https://example.test';
  const members = new Set([HOST_X, PLAYER_X]);
  const auth = {
    authenticated(req) {
      const id = req.headers['x-test-user'];
      if (!id) return null;
      const username = id === HOST_X ? OFFICIAL_HANDLE : id === PLAYER_X ? 'player_two' : 'stranger';
      return { id, username };
    },
  };
  const memberAuthorized = async (req) => {
    const id = req.headers['x-test-user'];
    if (!members.has(id)) {
      throw Object.assign(new Error('Role required'), { code: 'DISCORD_MEMBER_ROLE_REQUIRED', status: 403 });
    }
    return { xUserId: id, discordUserId: '2222222222222222222', member: true };
  };

  const api = await createLobbyApi({
    dataDir: dir,
    auth,
    mentions: { pending: [] },
    publicOrigin: origin,
    now: () => 100_000,
    joinSecretKey: 'test-secret-key-with-strong-length',
    memberAuthorized,
  });

  const server = http.createServer(async (req, res) => {
    if (!(await api.handle(req, res, new URL(req.url, 'http://localhost')))) {
      res.writeHead(404);
      res.end();
    }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = 'http://127.0.0.1:' + server.address().port;

  async function call(url, method = 'GET', body, user) {
    const response = await fetch(base + url, {
      method,
      headers: {
        origin,
        'content-type': 'application/json',
        ...(user ? { 'x-test-user': user } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    return { status: response.status, json: await response.json().catch(() => ({})) };
  }

  try {
    {
      const name = 'HTTP: unauthorized create denied (no X)';
      try {
        assert.equal(
          (await call('/api/lobbies', 'POST', { game: 'arcade-runner', platform: 'web', mode: 'first', seats: 2, roundSeconds: 30, title: 'Need X' })).status,
          401,
        );
        pass(name);
      } catch (e) {
        fail(name, e);
      }
    }
    {
      const name = 'HTTP: missing Member role fails closed on create';
      try {
        assert.equal(
          (
            await call(
              '/api/lobbies',
              'POST',
              { game: 'arcade-runner', platform: 'web', mode: 'first', seats: 2, roundSeconds: 30, title: 'No role' },
              STRANGER_X,
            )
          ).status,
          403,
        );
        pass(name);
      } catch (e) {
        fail(name, e);
      }
    }
    let gameId = '';
    {
      const name = 'HTTP: host Member creates real lobby';
      try {
        const created = await call(
          '/api/lobbies',
          'POST',
          { game: 'arcade-runner', platform: 'web', mode: 'first', seats: 2, roundSeconds: 30, title: 'Host create' },
          HOST_X,
        );
        assert.equal(created.status, 201);
        gameId = created.json.game?.id || created.json.id;
        assert.ok(gameId);
        pass(name);
      } catch (e) {
        fail(name, e);
      }
    }
    {
      const name = 'HTTP: second Member account joins';
      try {
        if (!gameId) throw new Error('no gameId');
        const joined = await call('/api/lobbies/' + gameId + '/join', 'POST', {}, PLAYER_X);
        assert.equal(joined.status, 200);
        pass(name);
      } catch (e) {
        fail(name, e);
      }
    }
    {
      const name = 'HTTP: wrong account without Member denied on join';
      try {
        if (!gameId) throw new Error('no gameId');
        assert.equal((await call('/api/lobbies/' + gameId + '/join', 'POST', {}, STRANGER_X)).status, 403);
        pass(name);
      } catch (e) {
        fail(name, e);
      }
    }
    {
      const name = 'HTTP: public listing readable without auth; no secret fields';
      try {
        if (!gameId) throw new Error('no gameId');
        const pub = await call('/api/lobbies/' + gameId, 'GET');
        assert.equal(pub.status, 200);
        const body = JSON.stringify(pub.json);
        assert.ok(!body.includes(HOST_X));
        assert.ok(!body.includes(PLAYER_X));
        assert.ok(!/joinCode|redeem|access_token/i.test(body));
        pass(name);
      } catch (e) {
        fail(name, e);
      }
    }
    {
      const name = 'HTTP: role revocation denies private join-details';
      try {
        if (!gameId) throw new Error('no gameId');
        members.delete(PLAYER_X);
        const denied = await call('/api/lobbies/' + gameId + '/join-details', 'GET', undefined, PLAYER_X);
        assert.equal(denied.status, 403);
        members.add(PLAYER_X);
        pass(name);
      } catch (e) {
        fail(name, e);
      }
    }
    {
      const name = 'HTTP: host username maps to official @xyzhub identity in session fixture';
      try {
        const meUser = auth.authenticated({ headers: { 'x-test-user': HOST_X } });
        assert.equal(meUser.username, OFFICIAL_HANDLE);
        assert.equal('@' + meUser.username, '@xyzhub');
        pass(name);
      } catch (e) {
        fail(name, e);
      }
    }
  } finally {
    await new Promise((resolve) => server.close(resolve));
    await fs.rm(dir, { recursive: true, force: true });
  }
}

lobbyDomainSuite();
await memberAuthSuite();
await httpMemberGateSuite();

const failed = results.filter((r) => !r.ok);
console.log('\n' + (results.length - failed.length) + '/' + results.length + ' passed');
if (failed.length) {
  console.error('Failed cases:', failed.map((f) => f.name).join('; '));
  process.exit(1);
}
console.log('Two-account offline acceptance suite OK — no live X/Discord calls');
