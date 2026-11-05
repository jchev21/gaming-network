/**
 * Authenticated leaderboard core for the High Scores arcade (design + validation).
 *
 * IMPORTANT: scores come from the player's browser, so they are CLIENT-REPORTED.
 * This module rejects impossible/replayed/abusive submissions, but a determined
 * cheater can still submit plausible scores. Every accepted entry is therefore
 * tier "unverified" and `prizeEligible` is always false. Prize-grade scoring needs
 * server-side simulation or signed replays (see DESIGN.md).
 *
 * Pure logic: no network, no storage, no secrets in source. Callers supply the
 * authenticated player id (e.g. verified X id) and an HMAC secret from env.
 */
import crypto from 'node:crypto';

export const DURATIONS = Object.freeze([30, 60, 120, 300]);
// Conservative per-second ceilings derived from the game rules in index.html.
// runner: 16 pts/s survival + 85 per obstacle (assume <= 2 obstacles/s).
// targets: <= 309 pts/hit (100 + 12*14 streak + 41 speed) and <= 5 hits/s.
export const GAME_RULES = Object.freeze({
  runner:  Object.freeze({ maxPerSecond: 16 + 85 * 2, minHits: 0 }),
  targets: Object.freeze({ maxPerSecond: 309 * 5, minHits: 0 }),
});
export const LIMITS = Object.freeze({
  tokenTtlMs: 15 * 60_000,      // token must be redeemed within 15 minutes
  slackMs: 3_000,               // network/clock slack on the minimum play time
  maxRunsPerHour: 30,           // per player
  maxEntriesPerBoard: 5,        // best N kept per player per board
  nameMax: 24,
});

export class ScoreError extends Error {
  constructor(code, message, status = 400) { super(message); this.code = code; this.status = status; }
}
const fail = (code, msg, status) => { throw new ScoreError(code, msg, status); };
const b64 = buf => Buffer.from(buf).toString('base64url');
const mac = (secret, data) => crypto.createHmac('sha256', secret).update(data).digest();

function needSecret(secret) {
  if (typeof secret !== 'string' || secret.length < 32) throw new Error('Score signing secret (>=32 chars) is required');
}
function checkBoard(game, duration) {
  if (!Object.hasOwn(GAME_RULES, game)) fail('INVALID_GAME', 'Unsupported game');
  if (!DURATIONS.includes(duration)) fail('INVALID_DURATION', 'Unsupported duration');
}

/** Issued when an authenticated player starts a round; binds player, board and start time. */
export function issueRunToken({ playerId, game, duration, secret, now = Date.now(), nonce = crypto.randomBytes(12).toString('base64url') }) {
  needSecret(secret);
  if (!/^\d{1,24}$/.test(String(playerId || ''))) fail('AUTH_REQUIRED', 'Verified player required', 401);
  checkBoard(game, duration);
  const body = [playerId, game, duration, now, nonce].join('.');
  return b64(body) + '.' + b64(mac(secret, body));
}

export function parseRunToken(token, secret) {
  needSecret(secret);
  const [p, s, extra] = String(token || '').split('.');
  if (!p || !s || extra !== undefined) fail('BAD_TOKEN', 'Invalid run token', 403);
  const body = Buffer.from(p, 'base64url').toString('utf8');
  const want = mac(secret, body), got = Buffer.from(s, 'base64url');
  if (got.length !== want.length || !crypto.timingSafeEqual(got, want)) fail('BAD_TOKEN', 'Invalid run token', 403);
  const [playerId, game, duration, startedAt, nonce] = body.split('.');
  return { playerId, game, duration: Number(duration), startedAt: Number(startedAt), nonce };
}

/**
 * Validate a finished round. `claim` = { token, score, durationMs? } from the client.
 * Returns a normalized entry; throws ScoreError otherwise. Does NOT mutate state.
 */
export function validateSubmission({ playerId, claim, secret, now = Date.now() }) {
  const run = parseRunToken(claim && claim.token, secret);
  if (run.playerId !== String(playerId)) fail('TOKEN_MISMATCH', 'Run belongs to another player', 403);
  checkBoard(run.game, run.duration);
  const age = now - run.startedAt;
  if (!(age >= 0)) fail('BAD_TIME', 'Run starts in the future', 400);
  if (age > run.duration * 1000 + LIMITS.tokenTtlMs) fail('TOKEN_EXPIRED', 'Run expired', 410);
  // A completed round cannot be submitted before its time limit elapsed; early
  // crashes (runner) end sooner, so allow them but scale the score ceiling by real elapsed time.
  const score = claim.score;
  if (!Number.isSafeInteger(score) || score < 0) fail('INVALID_SCORE', 'Score must be a non-negative integer');
  const playedSeconds = Math.min(run.duration, (age + LIMITS.slackMs) / 1000);
  const ceiling = Math.ceil(GAME_RULES[run.game].maxPerSecond * playedSeconds);
  if (score > ceiling) fail('IMPOSSIBLE_SCORE', 'Score is not achievable in the elapsed time', 422);
  return { playerId: run.playerId, game: run.game, duration: run.duration, nonce: run.nonce, score, startedAt: run.startedAt };
}

/** In-memory store; swap `persist` for a DB. Handles replay, rate limiting and per-player caps. */
export function createLeaderboard({ secret, now = Date.now, persist = async () => {}, state = { entries: [], usedNonces: {}, runs: {} } } = {}) {
  needSecret(secret);
  const sanitizeName = n => String(n || 'Player').replace(/[\x00-\x1f\x7f<>]/g, '').trim().slice(0, LIMITS.nameMax) || 'Player';
  return {
    state,
    start(playerId, game, duration) {
      return issueRunToken({ playerId, game, duration, secret, now: now() });
    },
    async submit(playerId, displayName, claim) {
      const t = now();
      const hourAgo = t - 3_600_000;
      const recent = (state.runs[playerId] || []).filter(x => x > hourAgo);
      if (recent.length >= LIMITS.maxRunsPerHour) fail('RATE_LIMIT', 'Too many submissions; try later', 429);
      const entry = validateSubmission({ playerId, claim, secret, now: t });
      if (state.usedNonces[entry.nonce]) fail('REPLAY', 'Run already submitted', 409);
      state.usedNonces[entry.nonce] = entry.startedAt + entry.duration * 1000 + LIMITS.tokenTtlMs;
      state.runs[playerId] = [...recent, t];
      for (const [k, exp] of Object.entries(state.usedNonces)) if (exp < t - LIMITS.tokenTtlMs) delete state.usedNonces[k];
      state.entries.push({ ...entry, name: sanitizeName(displayName), submittedAt: t, tier: 'unverified', prizeEligible: false });
      // Keep each player's best N per board.
      const mine = state.entries.filter(e => e.playerId === playerId && e.game === entry.game && e.duration === entry.duration)
        .sort((a, b) => b.score - a.score).slice(LIMITS.maxEntriesPerBoard);
      if (mine.length) state.entries = state.entries.filter(e => !mine.includes(e));
      await persist(state);
      return { accepted: true, tier: 'unverified', prizeEligible: false };
    },
    /** Public view: never exposes player ids or nonces. */
    top(game, duration, limit = 10) {
      checkBoard(game, duration);
      const best = new Map();
      for (const e of state.entries) if (e.game === game && e.duration === duration) {
        const cur = best.get(e.playerId);
        if (!cur || e.score > cur.score) best.set(e.playerId, e);
      }
      return [...best.values()].sort((a, b) => b.score - a.score || a.submittedAt - b.submittedAt)
        .slice(0, Math.min(50, Math.max(1, limit)))
        .map((e, i) => ({ rank: i + 1, name: e.name, score: e.score, tier: e.tier }));
    },
  };
}
