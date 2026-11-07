import assert from 'node:assert/strict';
import {
  signGrantRequest, buildGrantHeadersAndBody, verifyRulesAccepted,
  requestMemberGrant, enrollAfterDiscordOAuth, TARGET_GUILD_ID,
} from './member-grant-client.mjs';

const SECRET = 'test-hmac-secret-at-least-32-bytes-long!!';
const results = [];
const pass = (n) => { results.push({ n, ok: true }); console.log('PASS', n); };
const fail = (n, e) => { results.push({ n, ok: false }); console.error('FAIL', n, e?.message || e); };

{
  const name = 'signature is deterministic HMAC';
  try {
    const a = signGrantRequest({
      secret: SECRET, timestamp: '1000', nonce: 'n', idempotencyKey: 'i',
      discordUserId: '1', xUserId: '2', guildId: TARGET_GUILD_ID,
    });
    const b = signGrantRequest({
      secret: SECRET, timestamp: '1000', nonce: 'n', idempotencyKey: 'i',
      discordUserId: '1', xUserId: '2', guildId: TARGET_GUILD_ID,
    });
    assert.equal(a, b);
    assert.equal(a.length, 64);
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'buildGrantHeadersAndBody includes signed headers';
  try {
    const { headers, body } = buildGrantHeadersAndBody({
      secret: SECRET, discordUserId: '2000000000000000001', xUserId: '1000000000000000001',
      now: () => 1_700_000_000_000,
    });
    assert.ok(headers['X-GN-Signature']);
    assert.ok(headers['X-GN-Nonce']);
    assert.equal(body.guild_id, TARGET_GUILD_ID);
    const expected = signGrantRequest({
      secret: SECRET,
      timestamp: headers['X-GN-Timestamp'],
      nonce: headers['X-GN-Nonce'],
      idempotencyKey: body.idempotency_key,
      discordUserId: body.discord_user_id,
      xUserId: body.x_user_id,
      guildId: body.guild_id,
    });
    assert.equal(headers['X-GN-Signature'], expected);
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'verifyRulesAccepted requires pending=false and role';
  try {
    const fetchImpl = async (url) => {
      if (url.endsWith('/users/@me')) return { ok: true, json: async () => ({ id: '2000000000000000001' }) };
      return { ok: true, json: async () => ({ pending: false, roles: ['3000000000000000001'] }) };
    };
    const v = await verifyRulesAccepted({
      accessToken: 't', guildId: TARGET_GUILD_ID, rulesRoleId: '3000000000000000001', fetchImpl,
    });
    assert.equal(v.discordUserId, '2000000000000000001');
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'verifyRulesAccepted denies pending screening';
  try {
    const fetchImpl = async (url) => {
      if (url.endsWith('/users/@me')) return { ok: true, json: async () => ({ id: '1' }) };
      return { ok: true, json: async () => ({ pending: true, roles: ['3000000000000000001'] }) };
    };
    await assert.rejects(
      () => verifyRulesAccepted({
        accessToken: 't', guildId: TARGET_GUILD_ID, rulesRoleId: '3000000000000000001', fetchImpl,
      }),
      (err) => err.code === 'DISCORD_RULES_NOT_ACCEPTED',
    );
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'verifyRulesAccepted denies missing Rules Accepted role';
  try {
    const fetchImpl = async (url) => {
      if (url.endsWith('/users/@me')) return { ok: true, json: async () => ({ id: '1' }) };
      return { ok: true, json: async () => ({ pending: false, roles: [] }) };
    };
    await assert.rejects(
      () => verifyRulesAccepted({
        accessToken: 't', guildId: TARGET_GUILD_ID, rulesRoleId: '3000000000000000001', fetchImpl,
      }),
      (err) => err.code === 'MISSING_RULES_ACCEPTED_ROLE',
    );
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'enroll with grant disabled returns rules_verified only';
  try {
    const fetchImpl = async (url) => {
      if (url.endsWith('/users/@me')) return { ok: true, json: async () => ({ id: '2000000000000000001' }) };
      return { ok: true, json: async () => ({ pending: false, roles: ['r1'] }) };
    };
    const out = await enrollAfterDiscordOAuth({
      accessToken: 't', xUserId: 'x1', guildId: TARGET_GUILD_ID, rulesRoleId: 'r1',
      secret: SECRET, botGrantUrl: 'http://bot/internal/member-grant',
      fetchImpl, grantEnabled: false,
    });
    assert.equal(out.status, 'rules_verified_grant_disabled');
    assert.equal(out.grant, null);
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'requestMemberGrant fails closed without secret';
  try {
    await assert.rejects(
      () => requestMemberGrant({
        secret: 'short', botGrantUrl: 'http://x', discordUserId: '1', xUserId: '2',
      }),
      (err) => err.code === 'MEMBER_GRANT_MISCONFIGURED',
    );
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'requestMemberGrant posts signed body and surfaces bot denial';
  try {
    let saw = null;
    const fetchImpl = async (url, opts) => {
      saw = { url, opts };
      return { ok: false, status: 401, json: async () => ({ ok: false, code: 'INVALID_SIGNATURE' }) };
    };
    await assert.rejects(
      () => requestMemberGrant({
        secret: SECRET, botGrantUrl: 'http://bot/internal/member-grant',
        discordUserId: '2000000000000000001', xUserId: '1000000000000000001', fetchImpl,
      }),
      (err) => err.code === 'INVALID_SIGNATURE',
    );
    assert.equal(saw.opts.method, 'POST');
    assert.ok(saw.opts.headers['X-GN-Signature']);
    pass(name);
  } catch (e) { fail(name, e); }
}

{
  const name = 'X login alone never grants without Discord proof';
  try {
    const fetchImpl = async () => ({ ok: false, status: 401, json: async () => ({}) });
    await assert.rejects(
      () => enrollAfterDiscordOAuth({
        accessToken: 'bad', xUserId: 'only-x', guildId: TARGET_GUILD_ID, rulesRoleId: 'r',
        secret: SECRET, botGrantUrl: 'http://bot/internal/member-grant',
        fetchImpl, grantEnabled: true,
      }),
    );
    pass(name);
  } catch (e) { fail(name, e); }
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} passed`);
 if (failed.length) process.exit(1);
console.log('member-grant-client tests OK');
