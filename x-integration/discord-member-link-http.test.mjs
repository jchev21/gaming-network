import assert from 'node:assert/strict';
import { createDiscordLinkHttp } from './discord-member-link-http.mjs';

const ROOT = 'https://x-game-intake-production.up.railway.app';
const CALLBACK = ROOT + '/auth/discord/callback';
const XID = '1000000000000000001';
const DID = '2000000000000000001';
const RULES = '3000000000000000001';
const CLIENT = '3333333333333333333';
const HOST_COOKIE = 'gn_x_session=' + 'h'.repeat(43);
const fakeAuth = {
  authenticated(req) {
    return String(req.headers?.cookie || '').includes(HOST_COOKIE)
      ? { id: XID, username: '_xyzhub_' } : null;
  },
};
const env = {
  GN_DISCORD_LINK_ENABLED: 'true',
  GN_MEMBER_GRANT_ENABLED: 'false',
  DISCORD_CLIENT_ID: CLIENT,
  DISCORD_CLIENT_SECRET: 'unit-test-only-private-secret',
  DISCORD_CALLBACK_URL: CALLBACK,
  DISCORD_RULES_ROLE_ID: RULES,
};
const req = (cookie = HOST_COOKIE) => ({
  method: 'GET', headers: { cookie },
  socket: { remoteAddress: '127.0.0.1' },
});
const res = () => ({
  status: 0, headers: {}, body: '',
  writeHead(status, headers) { this.status = status; this.headers = headers; },
  end(value = '') { this.body += value; },
});
const url = (path) => new URL(path, ROOT);

{
  const disabled = createDiscordLinkHttp({ xAuth: fakeAuth, publicOrigin: ROOT, env: {} });
  assert.equal(disabled.enabled, false);
  const reply = res();
  assert.equal(await disabled.handle(req(), reply, url('/auth/discord/start')), false);
  assert.equal(reply.status, 0);
  console.log('PASS no feature flag = no OAuth routes');
}
{
  const incomplete = createDiscordLinkHttp({
    xAuth: fakeAuth, publicOrigin: ROOT,
    env: { GN_DISCORD_LINK_ENABLED: 'true', DISCORD_CLIENT_ID: CLIENT },
  });
  assert.equal(incomplete.enabled, false);
  console.log('PASS missing sealed OAuth config fails closed');
}
{
  const mismatch = createDiscordLinkHttp({
    xAuth: fakeAuth, publicOrigin: ROOT,
    env: { ...env, DISCORD_CALLBACK_URL: 'https://attacker.example/auth/discord/callback' },
  });
  assert.equal(mismatch.enabled, false);
  console.log('PASS incorrect callback origin fails closed');
}
{
  const invalid = createDiscordLinkHttp({
    xAuth: fakeAuth, publicOrigin: ROOT, env,
  });
  const reply = res();
  await invalid.handle(req(), reply, url('/auth/discord/start'));
  assert.equal(reply.status, 302);
  assert.ok(reply.headers.location.startsWith('https://discord.com/oauth2/authorize?'));
  assert.ok(reply.headers['set-cookie'].includes('HttpOnly; Secure; SameSite=Lax'));
  const state = new URL(reply.headers.location).searchParams.get('state');
  assert.ok(state.length >= 20);
  const denied = res();
  await invalid.handle(req('gn_x_session=wrong'), denied,
    url('/auth/discord/callback?state=' + state + '&code=example'));
  assert.equal(denied.status, 401);
  assert.equal(JSON.parse(denied.body).error, 'X_SIGN_IN_REQUIRED');
  console.log('PASS genuine X session required for callback');
}
{
  let calls = 0;
  let signedGrantCalls = 0;
  const fetchImpl = async (target) => {
    calls += 1;
    const t = String(target);
    if (t.includes('/internal/member-grant')) {
      signedGrantCalls += 1;
      throw Error('grant endpoint should not be contacted with owner gate OFF');
    }
    if (t.endsWith('/oauth2/token')) {
      return { ok: true, json: async () => ({ access_token: 'testing-only' }) };
    }
    if (t.endsWith('/users/@me')) {
      return { ok: true, json: async () => ({ id: DID }) };
    }
    if (t.includes('/users/@me/guilds/')) {
      return { ok: true, json: async () => ({ pending: false, roles: [RULES] }) };
    }
    throw Error('Unexpected external call ' + t);
  };
  const flow = createDiscordLinkHttp({ xAuth: fakeAuth, publicOrigin: ROOT, env, fetchImpl });
  const started = res();
  await flow.handle(req(), started, url('/auth/discord/start'));
  assert.equal(started.status, 302);
  const state = new URL(started.headers.location).searchParams.get('state');
  const stateCookie = started.headers['set-cookie'].split(';')[0];
  const finished = res();
  await flow.handle(req(HOST_COOKIE + '; ' + stateCookie), finished,
    url('/auth/discord/callback?state=' + state + '&code=testing-only'));
  assert.equal(finished.status, 200);
  const response = JSON.parse(finished.body);
  assert.equal(response.status, 'rules_verified_grant_disabled');
  assert.equal(response.member_grant_confirmed, false);
  assert.equal(calls, 3);
  assert.equal(signedGrantCalls, 0);
  assert.ok(finished.headers['set-cookie'].includes('Max-Age=0'));
  console.log('PASS same-X-session OAuth callback verifies rules but never auto-grants Member');
}
{
  const flow = createDiscordLinkHttp({ xAuth: fakeAuth, publicOrigin: ROOT, env });
  const started = res();
  await flow.handle(req(), started, url('/auth/discord/start'));
  const realState = new URL(started.headers.location).searchParams.get('state');
  const bad = res();
  await flow.handle(req(HOST_COOKIE + '; ' + started.headers['set-cookie'].split(';')[0]),
    bad, url('/auth/discord/callback?state=' + realState + 'incorrect&code=example'));
  assert.equal(bad.status, 400);
  assert.equal(JSON.parse(bad.body).error, 'INVALID_DISCORD_OAUTH_STATE');
  console.log('PASS invalid state cannot authorize Discord identity');
}
console.log('X/Discord disabled-by-default HTTP boundary tests PASS');
