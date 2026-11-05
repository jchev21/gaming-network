import crypto from 'node:crypto';

const MENTION_ID = /^\d{1,24}$/;
const LIFECYCLE_TYPES = new Set(['created', 'ready', 'cancelled', 'closed']);
const MAX_SEEN = 5_000;

/**
 * Opt-in interface seam for official X API integrations.
 * This module performs no network I/O, polling, OAuth, or X posting. Production
 * callers must inject server-verified identity and their approved official API
 * client; the default is intentionally disabled.
 */
export function createXAdapter({ enabled = false, verifyAuthor = () => false, maxSeen = MAX_SEEN } = {}) {
  const seen = new Set();
  const replyQueue = new Map();

  function acceptMention(event) {
    if (!enabled) return { accepted: false, reason: 'disabled' };
    if (!event || !MENTION_ID.test(String(event.mentionId || '')) ||
        !MENTION_ID.test(String(event.authorId || ''))) {
      return { accepted: false, reason: 'invalid' };
    }
    const mentionId = String(event.mentionId);
    if (seen.has(mentionId)) return { accepted: false, reason: 'duplicate' };
    // Do not trust a submitted handle or display name; verifier is server-owned.
    if (!verifyAuthor(String(event.authorId))) return { accepted: false, reason: 'unverified' };
    seen.add(mentionId);
    if (seen.size > maxSeen) seen.delete(seen.values().next().value);
    return { accepted: true, request: { mentionId, status: 'awaiting_host_setup' } };
  }

  function queueApprovedReply({ mentionId, text, approved = false, expiresAt, now = Date.now() } = {}) {
    if (!enabled) return { queued: false, reason: 'disabled' };
    if (approved !== true) return { queued: false, reason: 'approval_required' };
    if (!MENTION_ID.test(String(mentionId || '')) || typeof text !== 'string' ||
        text.trim().length < 1 || text.length > 280 ||
        !Number.isSafeInteger(expiresAt) || expiresAt <= now) {
      return { queued: false, reason: 'invalid' };
    }
    const id = String(mentionId);
    if (replyQueue.has(id)) return { queued: false, reason: 'duplicate' };
    replyQueue.set(id, { mentionId: id, text: text.trim(), expiresAt });
    return { queued: true, queuedCount: replyQueue.size };
  }

  function listApprovedReplies(now = Date.now()) {
    for (const [id, item] of replyQueue) if (item.expiresAt <= now) replyQueue.delete(id);
    return [...replyQueue.values()].map((item) => ({ ...item }));
  }

  return Object.freeze({ enabled: enabled === true, acceptMention, queueApprovedReply, listApprovedReplies });
}

const safeText = (value, max = 120) => typeof value === 'string'
  ? value.replace(/[\x00-\x1f\x7f<>]/g, '').trim().slice(0, max)
  : '';

/**
 * Build an allowlisted, public-only lifecycle event. Never pass a domain lobby
 * object through directly: it can contain X IDs, waitlists, and encrypted data.
 * Delivery/outbox wiring is deliberately left to the separately reviewed
 * Discord outbox workstream; this function is safe to call before enqueue.
 */
export function createPublicLifecycleEvent(type, lobby, occurredAt = new Date().toISOString()) {
  if (!LIFECYCLE_TYPES.has(type)) throw new TypeError('Unsupported lobby lifecycle event');
  if (!lobby || typeof lobby !== 'object' || Array.isArray(lobby)) throw new TypeError('Lobby snapshot is required');
  const status = type === 'cancelled' ? 'cancelled' : type === 'closed' ? 'closed' : safeText(lobby.status, 20);
  const payload = {
    id: safeText(lobby.id, 80),
    title: safeText(lobby.title, 100),
    game: safeText(lobby.game, 40),
    platform: safeText(lobby.platform, 32),
    mode: safeText(lobby.mode, 24),
    status,
    seats: Number.isSafeInteger(lobby.seats) ? Math.max(0, Math.min(200, lobby.seats)) : 0,
    entryCount: Number.isSafeInteger(lobby.entryCount) ? Math.max(0, Math.min(200, lobby.entryCount)) : 0,
    confirmedCount: Number.isSafeInteger(lobby.confirmedCount) ? Math.max(0, Math.min(200, lobby.confirmedCount)) : 0,
    entryClosesAt: Number.isSafeInteger(lobby.entryClosesAt) ? lobby.entryClosesAt : null,
  };
  if (!payload.id || !payload.title || !payload.game) throw new TypeError('Lobby public fields are incomplete');
  const timestamp = new Date(occurredAt);
  if (!Number.isFinite(timestamp.getTime())) throw new TypeError('Invalid lifecycle timestamp');
  const eventId = crypto.createHash('sha256')
    .update(`${type}:${payload.id}`)
    .digest('hex');
  return Object.freeze({
    schemaVersion: 1,
    eventId,
    type,
    occurredAt: timestamp.toISOString(),
    source: 'gaming-network-preview',
    lobby: Object.freeze(payload),
  });
}

export const LIFECYCLE_EVENT_TYPES = Object.freeze([...LIFECYCLE_TYPES]);
