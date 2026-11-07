/**
 * Batch 7 — Connect verified X login to Discord OAuth in one protected session.
 * Never grants Member from X alone. Grant path uses signed S2S client.
 */
import crypto from 'node:crypto';
import {
  enrollAfterDiscordOAuth,
  TARGET_GUILD_ID,
} from './member-grant-client.mjs';

const sha = (v) => crypto.createHash('sha256').update(v).digest('hex');
const random = () => crypto.randomBytes(32).toString('base64url');
const snowflake = (v) => typeof v === 'string' && /^[0-9]{15,24}$/.test(v);

export function createMemberLinkFlow({
  xAuth, clientId, clientSecret, redirectUri,
  guildId = TARGET_GUILD_ID, rulesRoleId, memberRoleId,
  grantSecret, botGrantUrl, grantEnabled = false,
  fetchImpl = fetch, now = Date.now, discordBase = 'https://discord.com',
}) {
  if (!xAuth || typeof xAuth.authenticated !== 'function') {
    throw new Error('X session provider required');
  }
  if (!snowflake(clientId) || !snowflake(guildId) || !snowflake(rulesRoleId)) {
    throw new Error('Discord OAuth / Rules role configuration incomplete');
  }
  const flows = new Map();

  function xActor(req) {
    const user = xAuth.authenticated(req);
    const cookie = String(req.headers?.cookie || '');
    const m = cookie.match(/(?:^|;\s*)gn_x_session=([^;]+)/);
    const raw = m ? decodeURIComponent(m[1]) : null;
    if (!user || !snowflake(String(user.id || '')) || !raw || raw.length < 20) {
      const e = new Error('X_SIGN_IN_REQUIRED');
      e.code = 'X_SIGN_IN_REQUIRED';
      e.status = 401;
      throw e;
    }
    return { xId: String(user.id), xProof: sha(raw), username: user.username || '' };
  }

  async function startDiscordOAuth(req) {
    const owner = xActor(req);
    const state = random();
    flows.set(sha(state), { ...owner, expires: now() + 600_000 });
    const authorize = new URL(discordBase + '/oauth2/authorize');
    for (const [k, v] of Object.entries({
      client_id: clientId, redirect_uri: redirectUri, response_type: 'code',
      scope: 'identify guilds.members.read', state, prompt: 'consent',
    })) authorize.searchParams.set(k, v);
    return { location: authorize.toString(), stateCookie: state, owner };
  }

  async function handleDiscordCallback(req, { state, code, stateCookie }) {
    const owner = xActor(req);
    if (!state || state.length < 20 || !code || state !== stateCookie) {
      const e = new Error('INVALID_DISCORD_OAUTH_STATE');
      e.code = 'INVALID_DISCORD_OAUTH_STATE';
      e.status = 400;
      throw e;
    }
    const key = sha(state);
    const flow = flows.get(key);
    flows.delete(key);
    if (!flow || flow.expires <= now() || flow.xId !== owner.xId || flow.xProof !== owner.xProof) {
      const e = new Error('SESSION_BINDING_MISMATCH');
      e.code = 'SESSION_BINDING_MISMATCH';
      e.status = 403;
      throw e;
    }
    const form = new URLSearchParams({
      client_id: clientId, client_secret: clientSecret, grant_type: 'authorization_code',
      code, redirect_uri: redirectUri,
    });
    const tokenRes = await fetchImpl(discordBase + '/api/v10/oauth2/token', {
      method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded' }, body: form,
    });
    if (!tokenRes.ok) {
      const e = new Error('DISCORD_OAUTH_EXCHANGE_FAILED');
      e.code = 'DISCORD_OAUTH_EXCHANGE_FAILED';
      e.status = 502;
      throw e;
    }
    const token = await tokenRes.json();
    if (typeof token.access_token !== 'string' || !token.access_token) {
      const e = new Error('INVALID_DISCORD_OAUTH_TOKEN');
      e.code = 'INVALID_DISCORD_OAUTH_TOKEN';
      e.status = 502;
      throw e;
    }
    const enrolled = await enrollAfterDiscordOAuth({
      accessToken: token.access_token, xUserId: owner.xId, guildId, rulesRoleId,
      secret: grantSecret || 'x'.repeat(32),
      botGrantUrl: botGrantUrl || 'http://127.0.0.1/internal/member-grant',
      fetchImpl, grantEnabled: Boolean(grantEnabled && grantSecret && botGrantUrl), now,
    });
    return {
      xUserId: owner.xId, discordUserId: enrolled.discordUserId,
      status: enrolled.status, grant: enrolled.grant, memberRoleId,
    };
  }

  return { startDiscordOAuth, handleDiscordCallback, xActor };
}
