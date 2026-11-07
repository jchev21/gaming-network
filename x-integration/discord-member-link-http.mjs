/**
 * Production X intake adapter for the review-tested X→Discord Member link flow.
 * By DEFAULT there are no /auth/discord routes at all.
 * This adapter never grants a role or owns a Discord bot token.
 */
import { createMemberLinkFlow } from './discord-member-link.mjs';

const SCOPE = '/auth/discord';
const cookie = (req, key) => {
  const item = String(req.headers?.cookie || '').split(';').map(s => s.trim())
    .find(s => s.startsWith(key + '='));
  return item ? item.slice(key.length + 1) : '';
};
const seal = (value, age = 600) =>
  'gn_discord_oauth_state=' + value +
  '; Path=' + SCOPE + '; Max-Age=' + age +
  '; HttpOnly; Secure; SameSite=Lax';

function safeReply(res, code, body, extra = {}) {
  res.writeHead(code, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'pragma': 'no-cache',
    'x-content-type-options': 'nosniff',
    'x-frame-options': 'DENY',
    'referrer-policy': 'no-referrer',
    'content-security-policy': "default-src 'none'; frame-ancestors 'none'",
    ...extra,
  });
  res.end(JSON.stringify(body));
}

function enabledConfig(env, publicOrigin) {
  if (env.GN_DISCORD_LINK_ENABLED !== 'true') {
    return { enabled: false, reason: 'owner_gate_off' };
  }
  const needed = [
    'DISCORD_CLIENT_ID', 'DISCORD_CLIENT_SECRET', 'DISCORD_CALLBACK_URL',
    'DISCORD_RULES_ROLE_ID',
  ];
  if (needed.some(k => !env[k])) return { enabled: false, reason: 'missing_discord_oauth_configuration' };
  if (env.DISCORD_CALLBACK_URL !== publicOrigin + '/auth/discord/callback') {
    return { enabled: false, reason: 'discord_callback_origin_mismatch' };
  }
  return { enabled: true, reason: 'ready' };
}

export function createDiscordLinkHttp({
  xAuth, publicOrigin, env = process.env, fetchImpl = fetch, now = Date.now,
} = {}) {
  const cfg = enabledConfig(env, publicOrigin);
  if (!cfg.enabled) return { enabled: false, reason: cfg.reason, handle: async () => false };
  const grantsConfigured = env.GN_MEMBER_GRANT_ENABLED === 'true'
    && !!env.GN_MEMBER_GRANT_HMAC_SECRET && !!env.GN_MEMBER_GRANT_URL;
  const flow = createMemberLinkFlow({
    xAuth,
    clientId: env.DISCORD_CLIENT_ID,
    clientSecret: env.DISCORD_CLIENT_SECRET,
    redirectUri: env.DISCORD_CALLBACK_URL,
    rulesRoleId: env.DISCORD_RULES_ROLE_ID,
    memberRoleId: env.DISCORD_MEMBER_ROLE_ID || '',
    grantSecret: env.GN_MEMBER_GRANT_HMAC_SECRET || '',
    botGrantUrl: env.GN_MEMBER_GRANT_URL || '',
    grantEnabled: grantsConfigured,
    fetchImpl, now,
  });
  const hits = new Map();
  function rateOk(req) {
    const key = String(req.socket?.remoteAddress || 'unknown');
    const t = now();
    const samples = (hits.get(key) || []).filter(x => t - x < 60000);
    if (samples.length >= 12) return false;
    samples.push(t);
    hits.set(key, samples);
    if (hits.size > 1500) for (const [k,v] of hits) if (!v.length || t - v[v.length-1] > 60000) hits.delete(k);
    return true;
  }
  return {
    enabled: true,
    reason: grantsConfigured ? 'member_grants_configured' : 'rules_verification_only',
    async handle(req, res, url) {
      if (!url.pathname.startsWith(SCOPE + '/')) return false;
      if (req.method !== 'GET') {
        safeReply(res, 405, { error: 'METHOD_NOT_ALLOWED' });
        return true;
      }
      if (!rateOk(req)) {
        safeReply(res, 429, { error: 'RATE_LIMITED' });
        return true;
      }
      try {
        if (url.pathname === SCOPE + '/start') {
          const result = await flow.startDiscordOAuth(req);
          res.writeHead(302, {
            location: result.location,
            'set-cookie': seal(result.stateCookie),
            'cache-control': 'no-store',
            'referrer-policy': 'no-referrer',
            'x-content-type-options': 'nosniff',
          });
          res.end();
          return true;
        }
        if (url.pathname === SCOPE + '/callback') {
          const result = await flow.handleDiscordCallback(req, {
            state: url.searchParams.get('state'),
            code: url.searchParams.get('code'),
            stateCookie: cookie(req, 'gn_discord_oauth_state'),
          });
          safeReply(res, 200, {
            status: result.status,
            member_grant_confirmed: result.status === 'member_grant_ok',
            next_step: result.status === 'member_grant_ok'
              ? 'Open /onboarding-status in Discord and check the role'
              : 'Rules Verified. Automatic Member grant is not enabled.',
          }, { 'set-cookie': seal('', 0) });
          return true;
        }
        safeReply(res, 404, { error: 'NOT_FOUND' });
        return true;
      } catch (e) {
        const safe = new Set([
          'X_SIGN_IN_REQUIRED', 'INVALID_DISCORD_OAUTH_STATE',
          'SESSION_BINDING_MISMATCH', 'DISCORD_RULES_NOT_ACCEPTED',
          'MISSING_RULES_ACCEPTED_ROLE', 'DISCORD_MEMBER_CHECK_FAILED',
          'DISCORD_IDENTITY_CHECK_FAILED', 'DISCORD_OAUTH_EXCHANGE_FAILED',
          'INVALID_DISCORD_OAUTH_TOKEN',
        ]);
        const code = safe.has(e?.code) ? e.code : 'DISCORD_LINK_UNAVAILABLE';
        const status = Number.isInteger(e?.status) && e.status >= 400 && e.status < 600
          ? e.status : 503;
        safeReply(res, status, { error: code }, { 'set-cookie': seal('', 0) });
        return true;
      }
    },
  };
}
