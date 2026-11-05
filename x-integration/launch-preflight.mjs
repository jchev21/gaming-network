/**
 * Offline, secret-redacting operator checklist for Gaming Network X intake.
 *
 * Usage (inside a correctly configured Railway service or a safe local shell):
 *   node launch-preflight.mjs
 *
 * Never prints values from process.env. It cannot check X Developer Console
 * callback registration, OAuth scopes, billing, identities, real account
 * approvals or Discord permissions. This is NOT a go-live authorization.
 */
import { fileURLToPath } from 'node:url';
import path from 'node:path';

function canonicalHttpsOrigin(raw) {
  if (typeof raw !== 'string' || raw !== raw.trim() || raw.length > 240) return null;
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== 'https:' ||
      parsed.username || parsed.password ||
      parsed.origin !== raw || !parsed.hostname) return null;
    return parsed.origin;
  } catch {
    return null;
  }
}

export function checkLaunchConfiguration(env = {}) {
  const checks = [];
  const check = (id, passed, description, required = true) => {
    checks.push({ id, passed: Boolean(passed), required, description });
  };

  const publicOrigin = canonicalHttpsOrigin(env.X_PUBLIC_ORIGIN);
  check('public-origin', !!publicOrigin,
    'X_PUBLIC_ORIGIN is a canonical HTTPS origin without a path or embedded credentials.');

  // The callback must be the exact public origin: the implementation uses
  // a single fixed /auth/x/callback route and strict OAuth state cookies.
  check('oauth-callback', Boolean(publicOrigin &&
    env.X_CALLBACK_URL === publicOrigin + '/auth/x/callback'),
    'X_CALLBACK_URL matches the public origin and /auth/x/callback exactly.');

  check('oauth-client', typeof env.X_CLIENT_ID === 'string' &&
    env.X_CLIENT_ID.trim().length > 0,
    'X_CLIENT_ID is configured; developer-app ownership and scopes still require a real login test.');

  // The app uses OAuth PKCE. Depending on the X app client type, a client
  // secret may or may not be required; report presence without treating
  // missing credentials as proof of OAuth failure.
  check('oauth-client-secret', typeof env.X_CLIENT_SECRET === 'string' &&
    env.X_CLIENT_SECRET.length > 0,
    'X_CLIENT_SECRET is present (required for confidential X applications).', false);

  const admin = typeof env.X_ADMIN_TOKEN === 'string' ? env.X_ADMIN_TOKEN : '';
  const join = typeof env.X_JOIN_SECRET_KEY === 'string' ? env.X_JOIN_SECRET_KEY : '';
  check('admin-token', Buffer.byteLength(admin, 'utf8') >= 32,
    'X_ADMIN_TOKEN has at least 32 bytes for protected moderation requests.');

  check('join-encryption-key', Buffer.byteLength(join, 'utf8') >= 32 && join !== admin,
    'X_JOIN_SECRET_KEY has at least 32 bytes and differs from the admin token.');

  const poll = env.X_POLL_ENABLED;
  check('paid-mention-polling-off', poll === undefined || poll === '' || poll === 'false',
    'X_POLL_ENABLED is off during the manual acceptance phase; no automatic billable scans.');

  check('discord-posting-off', env.DISCORD_LOBBY_ANNOUNCEMENTS_ENABLED !== 'true',
    'Optional Discord webhook announcements remain disabled until separate approval.');

  const handle = env.X_HANDLE;
  check('trigger-handle', typeof handle === 'string' && /^[A-Za-z0-9_]{1,15}$/.test(handle),
    'X_HANDLE has an X username format; actual account ownership is unverified.', false);

  check('bearer-token', typeof env.X_API_BEARER_TOKEN === 'string' &&
    env.X_API_BEARER_TOKEN.length > 0,
    'X_API_BEARER_TOKEN is present for separately approved read-only mention checks.', false);

  check('moderator-id', typeof env.X_MODERATOR_USER_ID === 'string' &&
    /^\\d{1,24}$/.test(env.X_MODERATOR_USER_ID),
    'X_MODERATOR_USER_ID is configured for signed-in moderator approval.', false);

  check('persistent-data-path', typeof env.DATA_DIR === 'string' && path.isAbsolute(env.DATA_DIR),
    'DATA_DIR is an absolute path; the operator must separately verify its Railway volume.', false);

  return {
    readyForManualTests: checks.every(c => !c.required || c.passed),
    checks,
    message: 'Configuration-only checks. Real X OAuth callbacks, two-account lobbies, Discord interactions, billing and owner signoff are not verified.',
  };
}

export function formatLaunchPreflight(report) {
  const lines = ['Gaming Network X intake — secret-safe preflight'];
  for (const c of report.checks) {
    const status = c.passed ? 'OK' : c.required ? 'BLOCKED' : 'OPTIONAL';
    lines.push('[' + status + '] ' + c.description);
  }
  lines.push(report.readyForManualTests
    ? 'Config checks pass. Real-account tests and explicit owner launch approval remain required.'
    : 'Configuration blockers remain. No services or flags have been changed.');
  lines.push(report.message);
  return lines.join('\\n');
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const result = checkLaunchConfiguration(process.env);
  // No raw variable values or secrets are logged, even when validation fails.
  process.stdout.write(formatLaunchPreflight(result) + '\\n');
  if (!result.readyForManualTests) process.exitCode = 1;
}
