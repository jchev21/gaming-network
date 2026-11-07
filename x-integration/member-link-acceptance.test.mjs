/**
 * Batch 8 — Offline acceptance for Rules→X→Discord→Member path.
 */
import assert from 'node:assert/strict';
import { createMemberLinkFlow } from './discord-member-link.mjs';
import {
  signGrantRequest, buildGrantHeadersAndBody, verifyRulesAccepted,
  requestMemberGrant, enrollAfterDiscordOAuth, TARGET_GUILD_ID,
} from './member-grant-client.mjs';

const SECRET = 'test-hmac-secret-at-least-32-bytes-long!!';
const CLIENT = '3333333333333333333';
const RULES = '3000000000000000001';
const MEMBER = '3000000000000000002';
const HOST_X = '1000000000000000001';
const HOST_D = '2000000000000000001';
const results = [];
const pass = (n) => { results.push({ n, ok: true }); console.log('PASS', n); };
const fail = (n, e) => { results.push({ n, ok: false }); console.error('FAIL', n, e?.message || e); };

const hostCookie = 'gn_x_session=' + 'h'.repeat(43);
const xAuth = {
  authenticated(req) {
    const c = String(req.headers?.cookie || '');
    if (c.includes(hostCookie)) return { id: HOST_X, username: 'xyzhub' };
    return null;
  },
};

function mockDiscord({ pending = false, roles = [RULES], tokenOk = true } = {}) {
  return async (url, opts = {}) => {
    const u = String(url);
    if (u.includes('/oauth2/token')) {
      if (!tokenOk) return { ok: false, status: 400, json: async () => ({}) };
      return { ok: true, json: async () => ({ access_token: 'atok', expires_in: 3600 }) };
    }
    if (u.endsWith('/users/@me')) return { ok: true, json: async () => ({ id: HOST_D }) };
    if (u.includes('/guilds/') && u.includes('/member')) {
      return { ok: true, json: async () => ({ pending, roles, user: { id: HOST_D } }) };
    }
    if (u.includes('/internal/member-grant')) {
      const body = JSON.parse(opts.body || '{}');
      const expected = signGrantRequest({
        secret: SECRET,
        timestamp: opts.headers['X-GN-Timestamp'],
        nonce: opts.headers['X-GN-Nonce'],
        idempotencyKey: body.idempotency_key,
        discordUserId: body.discord_user_id,
        xUserId: body.x_user_id,
        guildId: body.guild_id,
      });
      if (opts.headers['X-GN-Signature'] !== expected) {
        return { ok: false, status: 401, json: async () => ({ ok: false, code: 'INVALID_SIGNATURE' }) };
      }
      return { ok: true, status: 200, json: async () => ({ ok: true, code: 'GRANT_CONFIRMED' }) };
    }
    throw new Error('unexpected ' + u);
  };
}

{
  const name = 'legitimate enrollment: X session + Discord OAuth + Rules Accepted';
  try {
    const flow = createMemberLinkFlow({
      xAuth, clientId: CLIENT, clientSecret: 'secret',
      redirectUri: 'https://example.test/auth/discord/callback',
      rulesRoleId: RULES, memberRoleId: MEMBER,
      grantSecret: SECRET, botGrantUrl: 'http://bot/internal/member-grant',
      grantEnabled: false, fetchImpl: mockDiscord(),
    });
    const start = await flow.startDiscordOAuth({ headers: { cookie: hostCookie } });
    const result = await flow.handleDiscordCallback(
      { headers: { cookie: hostCookie } },
      { state: start.stateCookie, code: 'test', stateCookie: start.stateCookie },
    );
    assert.equal(result.xUserId, HOST_X);
    assert.equal(result.discordUserId, HOST_D);
    assert.equal(result.status, 'rules_verified_grant_disabled');
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'unauthorized: no X session denied';
  try {
    const flow = createMemberLinkFlow({
      xAuth, clientId: CLIENT, clientSecret: 'secret',
      redirectUri: 'https://example.test/auth/discord/callback',
      rulesRoleId: RULES, memberRoleId: MEMBER, fetchImpl: mockDiscord(),
    });
    await assert.rejects(() => flow.startDiscordOAuth({ headers: {} }), (e) => e.code === 'X_SIGN_IN_REQUIRED');
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'pending screening fails closed';
  try {
    await assert.rejects(
      () => verifyRulesAccepted({
        accessToken: 't', guildId: TARGET_GUILD_ID, rulesRoleId: RULES,
        fetchImpl: mockDiscord({ pending: true }),
      }),
      (e) => e.code === 'DISCORD_RULES_NOT_ACCEPTED',
    );
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'missing Rules Accepted fails closed';
  try {
    await assert.rejects(
      () => verifyRulesAccepted({
        accessToken: 't', guildId: TARGET_GUILD_ID, rulesRoleId: RULES,
        fetchImpl: mockDiscord({ roles: [] }),
      }),
      (e) => e.code === 'MISSING_RULES_ACCEPTED_ROLE',
    );
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'session swap / state mismatch denied';
  try {
    const flow = createMemberLinkFlow({
      xAuth, clientId: CLIENT, clientSecret: 'secret',
      redirectUri: 'https://example.test/auth/discord/callback',
      rulesRoleId: RULES, memberRoleId: MEMBER, fetchImpl: mockDiscord(),
    });
    const start = await flow.startDiscordOAuth({ headers: { cookie: hostCookie } });
    await assert.rejects(
      () => flow.handleDiscordCallback(
        { headers: { cookie: hostCookie } },
        { state: start.stateCookie, code: 'x', stateCookie: 'different-state-value-xxxxxxxxxxxx' },
      ),
      (e) => e.code === 'INVALID_DISCORD_OAUTH_STATE',
    );
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'X login alone never grants Member (grantEnabled false)';
  try {
    const out = await enrollAfterDiscordOAuth({
      accessToken: 't', xUserId: HOST_X, guildId: TARGET_GUILD_ID, rulesRoleId: RULES,
      secret: SECRET, botGrantUrl: 'http://bot/internal/member-grant',
      fetchImpl: mockDiscord(), grantEnabled: false,
    });
    assert.equal(out.status, 'rules_verified_grant_disabled');
    assert.equal(out.grant, null);
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'grant enabled path posts signed request and accepts confirmation';
  try {
    const out = await enrollAfterDiscordOAuth({
      accessToken: 't', xUserId: HOST_X, guildId: TARGET_GUILD_ID, rulesRoleId: RULES,
      secret: SECRET, botGrantUrl: 'http://bot/internal/member-grant',
      fetchImpl: mockDiscord(), grantEnabled: true,
    });
    assert.equal(out.status, 'member_grant_ok');
    assert.equal(out.grant.code, 'GRANT_CONFIRMED');
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'invalid grant signature fails closed';
  try {
    const fetchImpl = async (url, opts) => {
      if (String(url).includes('/internal/member-grant')) {
        return { ok: false, status: 401, json: async () => ({ ok: false, code: 'INVALID_SIGNATURE' }) };
      }
      return mockDiscord()(url, opts);
    };
    await assert.rejects(
      () => requestMemberGrant({
        secret: SECRET, botGrantUrl: 'http://bot/internal/member-grant',
        discordUserId: HOST_D, xUserId: HOST_X, fetchImpl,
      }),
    );
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'official handle fixture remains xyzhub';
  try {
    const me = xAuth.authenticated({ headers: { cookie: hostCookie } });
    assert.equal(me.username, 'xyzhub');
    pass(name);
  } catch (e) { fail(name, e); }
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} passed`);
if (failed.length) process.exit(1);
console.log('Batch 8 offline acceptance OK');
