/**
 * Issue #78 — X service → Hub bot signed Member grant client.
 * No bot token. No browser-trusted role JSON. Grants default OFF.
 */
import crypto from 'node:crypto';

export const TARGET_GUILD_ID = '1566290427366080612';

export function signGrantRequest({
  secret, timestamp, nonce, idempotencyKey, discordUserId, xUserId, guildId,
}) {
  const msg = [timestamp, nonce, idempotencyKey, discordUserId, xUserId, guildId].join('\n');
  return crypto.createHmac('sha256', secret).update(msg).digest('hex');
}

export function buildGrantHeadersAndBody({
  secret, discordUserId, xUserId, guildId = TARGET_GUILD_ID,
  now = Date.now, requestId = crypto.randomBytes(8).toString('hex'),
}) {
  const timestamp = String(Math.floor(now() / 1000));
  const nonce = crypto.randomBytes(24).toString('base64url');
  const idempotencyKey = crypto
    .createHash('sha256')
    .update(`${xUserId}:${discordUserId}:member-grant-v1`)
    .digest('hex');
  const signature = signGrantRequest({
    secret, timestamp, nonce, idempotencyKey,
    discordUserId, xUserId, guildId,
  });
  return {
    headers: {
      'content-type': 'application/json',
      'X-GN-Timestamp': timestamp,
      'X-GN-Nonce': nonce,
      'X-GN-Signature': signature,
    },
    body: {
      discord_user_id: discordUserId,
      x_user_id: xUserId,
      guild_id: guildId,
      idempotency_key: idempotencyKey,
      request_id: requestId,
    },
  };
}

/** Verify Discord member via REST: pending=false + Rules Accepted role. */
export async function verifyRulesAccepted({
  accessToken, guildId, rulesRoleId, fetchImpl = fetch, discordBase = 'https://discord.com',
}) {
  const me = await fetchImpl(discordBase + '/api/v10/users/@me', {
    headers: { authorization: 'Bearer ' + accessToken },
  });
  if (!me.ok) throw Object.assign(new Error('DISCORD_IDENTITY_CHECK_FAILED'), { code: 'DISCORD_IDENTITY_CHECK_FAILED', status: 403 });
  const user = await me.json();
  if (!user?.id) throw Object.assign(new Error('INVALID_DISCORD_USER'), { code: 'INVALID_DISCORD_USER', status: 403 });

  const memRes = await fetchImpl(
    discordBase + '/api/v10/users/@me/guilds/' + guildId + '/member',
    { headers: { authorization: 'Bearer ' + accessToken } },
  );
  if (!memRes.ok) throw Object.assign(new Error('DISCORD_MEMBER_CHECK_FAILED'), { code: 'DISCORD_MEMBER_CHECK_FAILED', status: 403 });
  const member = await memRes.json();
  if (member.pending !== false) {
    throw Object.assign(new Error('DISCORD_RULES_NOT_ACCEPTED'), { code: 'DISCORD_RULES_NOT_ACCEPTED', status: 403 });
  }
  if (!Array.isArray(member.roles) || !member.roles.includes(rulesRoleId)) {
    throw Object.assign(new Error('MISSING_RULES_ACCEPTED_ROLE'), { code: 'MISSING_RULES_ACCEPTED_ROLE', status: 403 });
  }
  return { discordUserId: String(user.id), roles: member.roles.map(String) };
}

export async function requestMemberGrant({
  secret, botGrantUrl, discordUserId, xUserId, guildId = TARGET_GUILD_ID,
  fetchImpl = fetch, now = Date.now,
}) {
  if (!secret || secret.length < 32) {
    const e = new Error('MEMBER_GRANT_MISCONFIGURED');
    e.code = 'MEMBER_GRANT_MISCONFIGURED';
    e.status = 503;
    throw e;
  }
  const { headers, body } = buildGrantHeadersAndBody({
    secret, discordUserId, xUserId, guildId, now,
  });
  const res = await fetchImpl(botGrantUrl, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || !json.ok) {
    const e = new Error(json.code || 'MEMBER_GRANT_DENIED');
    e.code = json.code || 'MEMBER_GRANT_DENIED';
    e.status = res.status;
    e.detail = json.detail;
    throw e;
  }
  return json;
}

/** After X + Discord OAuth: prove Rules Accepted, optionally request Member grant. */
export async function enrollAfterDiscordOAuth({
  accessToken, xUserId, guildId, rulesRoleId, secret, botGrantUrl,
  fetchImpl = fetch, grantEnabled = false, now = Date.now,
}) {
  const verified = await verifyRulesAccepted({
    accessToken, guildId, rulesRoleId, fetchImpl,
  });
  if (!grantEnabled) {
    return {
      status: 'rules_verified_grant_disabled',
      discordUserId: verified.discordUserId,
      grant: null,
    };
  }
  const grant = await requestMemberGrant({
    secret, botGrantUrl,
    discordUserId: verified.discordUserId,
    xUserId, guildId, fetchImpl, now,
  });
  return {
    status: 'member_grant_ok',
    discordUserId: verified.discordUserId,
    grant,
  };
}
