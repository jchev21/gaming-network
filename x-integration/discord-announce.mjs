/**
 * Opt-in X lobby → Discord announcement bridge.
 *
 * DEFAULT: disabled. Enable only with:
 *   DISCORD_LOBBY_ANNOUNCEMENTS_ENABLED=true
 *   DISCORD_LOBBY_WEBHOOK_URL=https://discord.com/api/webhooks/...
 *
 * Never posts live unless both are set. Tests inject a mock transport.
 * Never includes join codes, X IDs, invites, secrets, or private instructions.
 */
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { publicLobby } from './game-core.mjs';

const DISCORD_WEBHOOK_RE =
  /^https:\/\/((canary|ptb)\.)?discord\.com\/api\/webhooks\/\d{5,30}\/[A-Za-z0-9_-]{20,200}$/;

export class AnnounceConfigError extends Error {
  constructor(message) {
    super(message);
    this.code = 'ANNOUNCE_CONFIG';
  }
}

export function resolveAnnounceConfig(env = process.env, opts = {}) {
  const enabled =
    opts.enabled === true ||
    String(env.DISCORD_LOBBY_ANNOUNCEMENTS_ENABLED || '').toLowerCase() === 'true';

  const webhookUrl = String(opts.webhookUrl || env.DISCORD_LOBBY_WEBHOOK_URL || '').trim();
  const publicOrigin = String(opts.publicOrigin || env.X_PUBLIC_ORIGIN || '').replace(/\/$/, '');
  const dataDir = opts.dataDir || env.DATA_DIR || './runtime';

  if (!enabled) {
    return { enabled: false, reason: 'disabled', webhookUrl: null, publicOrigin, dataDir };
  }
  if (!DISCORD_WEBHOOK_RE.test(webhookUrl)) {
    return {
      enabled: false,
      reason: 'invalid_or_missing_webhook',
      webhookUrl: null,
      publicOrigin,
      dataDir,
    };
  }
  if (!publicOrigin || !/^https:\/\/[^/?#]+$/.test(publicOrigin)) {
    return {
      enabled: false,
      reason: 'invalid_public_origin',
      webhookUrl: null,
      publicOrigin: null,
      dataDir,
    };
  }
  return { enabled: true, reason: null, webhookUrl, publicOrigin, dataDir };
}

export function buildAnnouncementPayload(lobby, {
  publicOrigin,
  hostDisplayName = null,
  event = 'ready',
  now = Date.now(),
} = {}) {
  if (!lobby || !lobby.id) throw new Error('lobby required');
  const view = publicLobby(lobby, typeof now === 'function' ? now() : now);
  const lobbyUrl = `${publicOrigin}/lobby?id=${encodeURIComponent(view.id)}`;
  const host =
    typeof hostDisplayName === 'string' && hostDisplayName.trim()
      ? hostDisplayName.trim().replace(/[\x00-\x1f\x7f]/g, '').slice(0, 48)
      : null;

  const payload = {
    event,
    lobbyId: view.id,
    title: view.title,
    game: view.game,
    platform: view.platform,
    mode: view.mode,
    status: view.status,
    seats: view.seats,
    entryCount: view.entryCount,
    confirmedCount: view.confirmedCount,
    waitlistCount: view.waitlistCount,
    host,
    lobbyUrl,
    announcedAt: typeof now === 'function' ? now() : now,
  };

  const json = JSON.stringify(payload);
  if (/\b(ownerXId|joinSecrets|inviteToken)\b/.test(json)) {
    throw new Error('announcement payload privacy check failed');
  }
  return payload;
}

export function formatDiscordContent(payload) {
  const hostLine = payload.host ? `Host: ${payload.host}` : 'Host: (signed-in X host)';
  const seats = `${payload.confirmedCount}/${payload.seats} seats`;
  const wait = payload.waitlistCount > 0 ? ` \u00b7 waitlist ${payload.waitlistCount}` : '';
  const lines = [
    payload.event === 'cancelled'
      ? `**Lobby cancelled:** ${payload.title}`
      : `**Lobby ready:** ${payload.title}`,
    `${payload.game} \u00b7 ${payload.platform} \u00b7 ${payload.mode}`,
    `${hostLine} \u00b7 ${seats}${wait}`,
    payload.lobbyUrl,
  ];
  return lines.join('\n');
}

export function announcementKey(lobbyId, event = 'ready') {
  return `${event}:${String(lobbyId)}`;
}

async function loadOutbox(file) {
  try {
    const raw = await fs.readFile(file, 'utf8');
    const data = JSON.parse(raw);
    return {
      sent: data.sent && typeof data.sent === 'object' ? data.sent : {},
      pending: Array.isArray(data.pending) ? data.pending : [],
    };
  } catch (e) {
    if (e.code === 'ENOENT') return { sent: {}, pending: [] };
    throw e;
  }
}

async function saveOutbox(file, state) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  const tmp = file + '.tmp';
  await fs.writeFile(tmp, JSON.stringify(state, null, 2), { mode: 0o600 });
  await fs.rename(tmp, file);
}

export async function discordWebhookTransport(webhookUrl, body, { fetchImpl = fetch, timeoutMs = 8000 } = {}) {
  if (!DISCORD_WEBHOOK_RE.test(webhookUrl)) {
    throw new AnnounceConfigError('Refusing non-Discord webhook URL');
  }
  const res = await fetchImpl(webhookUrl, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!res.ok) {
    const err = new Error(`Discord webhook HTTP ${res.status}`);
    err.status = res.status;
    err.retryable = res.status === 429 || res.status >= 500;
    throw err;
  }
  return { status: res.status };
}

export function createDiscordAnnounceBridge(opts = {}) {
  const cfg = resolveAnnounceConfig(process.env, opts);
  const dataDir = opts.dataDir || cfg.dataDir || './runtime';
  const outboxFile = path.join(dataDir, 'discord-announce-outbox.json');
  const transport = opts.transport || discordWebhookTransport;
  const now = opts.now || Date.now;
  const maxAttempts = opts.maxAttempts ?? 3;

  let queue = Promise.resolve();
  function serial(fn) {
    const task = queue.then(fn, fn);
    queue = task.catch(() => {});
    return task;
  }

  async function enqueue(lobby, { event = 'ready', hostDisplayName = null } = {}) {
    if (!cfg.enabled) {
      return { queued: false, key: null, reason: cfg.reason || 'disabled' };
    }
    if (event !== 'ready' && event !== 'cancelled') {
      return { queued: false, key: null, reason: 'unsupported_event' };
    }

    const key = announcementKey(lobby.id, event);
    const payload = buildAnnouncementPayload(lobby, {
      publicOrigin: cfg.publicOrigin,
      hostDisplayName,
      event,
      now,
    });

    return serial(async () => {
      const state = await loadOutbox(outboxFile);
      if (state.sent[key]) {
        return { queued: false, key, reason: 'already_sent' };
      }
      if (state.pending.some((p) => p.key === key)) {
        return { queued: false, key, reason: 'already_pending' };
      }
      state.pending.push({
        key,
        event,
        lobbyId: lobby.id,
        payload,
        attempts: 0,
        createdAt: now(),
        nextAttemptAt: now(),
      });
      await saveOutbox(outboxFile, state);
      return { queued: true, key };
    });
  }

  async function flush() {
    if (!cfg.enabled) return { sent: 0, failed: 0, skipped: 0 };

    return serial(async () => {
      const state = await loadOutbox(outboxFile);
      let sent = 0;
      let failed = 0;
      let skipped = 0;
      const remaining = [];

      for (const item of state.pending) {
        if (state.sent[item.key]) {
          skipped++;
          continue;
        }
        if (item.nextAttemptAt > now()) {
          remaining.push(item);
          continue;
        }

        try {
          const content = formatDiscordContent(item.payload);
          await transport(cfg.webhookUrl, {
            content,
            allowed_mentions: { parse: [] },
          });
          state.sent[item.key] = {
            sentAt: now(),
            event: item.event,
            lobbyId: item.lobbyId,
          };
          sent++;
        } catch (e) {
          item.attempts = (item.attempts || 0) + 1;
          if (e.retryable !== false && item.attempts < maxAttempts) {
            const delay = Math.min(60_000, 2000 * 4 ** (item.attempts - 1));
            item.nextAttemptAt = now() + delay;
            item.lastError = String(e.message || e).slice(0, 200);
            remaining.push(item);
          } else {
            state.sent[item.key] = {
              sentAt: now(),
              event: item.event,
              lobbyId: item.lobbyId,
              failed: true,
              error: String(e.message || e).slice(0, 200),
            };
            failed++;
          }
        }
      }

      state.pending = remaining;
      const keys = Object.keys(state.sent);
      if (keys.length > 500) {
        keys.slice(0, keys.length - 500).forEach((k) => delete state.sent[k]);
      }
      await saveOutbox(outboxFile, state);
      return { sent, failed, skipped };
    });
  }

  async function notifyLobbyReady(lobby, meta = {}) {
    const result = await enqueue(lobby, { event: 'ready', ...meta });
    if (result.queued) {
      try { await flush(); } catch (_) {}
    }
    return result;
  }

  async function notifyLobbyCancelled(lobby, meta = {}) {
    const result = await enqueue(lobby, { event: 'cancelled', ...meta });
    if (result.queued) {
      try { await flush(); } catch (_) {}
    }
    return result;
  }

  return {
    config: cfg,
    enqueue,
    flush,
    notifyLobbyReady,
    notifyLobbyCancelled,
    outboxFile,
  };
}

export { DISCORD_WEBHOOK_RE };
