/**
 * Privacy-safe public lobby discovery helpers.
 * Never include ownerXId, player xIds, invites, secrets, or session data.
 */
import { GAME_TYPES, PLATFORMS, publicLobby, LobbyError } from './game-core.mjs';

export const PUBLIC_STATUSES = Object.freeze(['open', 'ready', 'closed', 'cancelled']);
export const MAX_FEED_LIMIT = 50;
export const DEFAULT_FEED_LIMIT = 20;

/**
 * Parse and validate query params for GET /api/lobbies.
 * Invalid values → LobbyError 400 (never 500).
 */
export function parseFeedQuery(searchParams) {
  const game = searchParams.get('game');
  const platform = searchParams.get('platform');
  const status = searchParams.get('status');
  const limitRaw = searchParams.get('limit');
  const cursor = searchParams.get('cursor');

  if (game != null && game !== '' && !GAME_TYPES.includes(game)) {
    throw new LobbyError('INVALID_GAME', 'Unsupported game filter', 400);
  }
  if (platform != null && platform !== '' && !PLATFORMS.includes(platform)) {
    throw new LobbyError('INVALID_PLATFORM', 'Unsupported platform filter', 400);
  }
  if (status != null && status !== '' && !PUBLIC_STATUSES.includes(status)) {
    throw new LobbyError('INVALID_STATUS', 'Unsupported status filter', 400);
  }

  let limit = DEFAULT_FEED_LIMIT;
  if (limitRaw != null && limitRaw !== '') {
    const n = Number(limitRaw);
    if (!Number.isInteger(n) || n < 1 || n > MAX_FEED_LIMIT) {
      throw new LobbyError('INVALID_LIMIT', `limit must be an integer from 1 to ${MAX_FEED_LIMIT}`, 400);
    }
    limit = n;
  }

  let cursorCreatedAt = null;
  let cursorId = null;
  if (cursor != null && cursor !== '') {
    try {
      const decoded = Buffer.from(String(cursor), 'base64url').toString('utf8');
      const sep = decoded.indexOf(':');
      if (sep < 1) throw new Error('bad cursor');
      cursorCreatedAt = Number(decoded.slice(0, sep));
      cursorId = decoded.slice(sep + 1);
      if (!Number.isSafeInteger(cursorCreatedAt) || !cursorId || cursorId.length > 64) {
        throw new Error('bad cursor fields');
      }
    } catch {
      throw new LobbyError('INVALID_CURSOR', 'Invalid pagination cursor', 400);
    }
  }

  return {
    game: game || null,
    platform: platform || null,
    status: status || null,
    limit,
    cursorCreatedAt,
    cursorId,
  };
}

export function encodeCursor(createdAt, id) {
  return Buffer.from(`${createdAt}:${id}`, 'utf8').toString('base64url');
}

/**
 * Build a sanitized feed page from an in-memory lobby map.
 */
export function buildPublicFeed(lobbies, query, now = Date.now) {
  let list = Object.values(lobbies || {});

  if (query.game) list = list.filter((g) => g.game === query.game);
  if (query.platform) list = list.filter((g) => g.platform === query.platform);
  if (query.status) list = list.filter((g) => {
    publicLobby(g, now());
    return g.status === query.status;
  });

  list.sort((a, b) => b.createdAt - a.createdAt || b.id.localeCompare(a.id));

  if (query.cursorCreatedAt != null) {
    list = list.filter((g) =>
      g.createdAt < query.cursorCreatedAt ||
      (g.createdAt === query.cursorCreatedAt && g.id < query.cursorId)
    );
  }

  const page = list.slice(0, query.limit);
  // Public marketing/dashboard discovery is intentionally COUNT-ONLY.
  // publicLobby() has optional public display names and host options for an
  // individual lobby, but a globally discoverable index must not aggregate
  // identifiable player lists, public handles or host configuration details.
  const games = page.map((g) => {
    const view = publicLobby(g, now());
    const {id, title, game, platform, mode, seats, roundSeconds, status,
      entryClosesAt, entryCount, confirmedCount, waitlistCount} = view;
    return {id, title, game, platform, mode, seats, roundSeconds, status,
      entryClosesAt, entryCount, confirmedCount, waitlistCount};
  });
  const last = page[page.length - 1];
  const nextCursor = page.length === query.limit && last
    ? encodeCursor(last.createdAt, last.id)
    : null;

  return {
    source: 'live',
    games,
    count: games.length,
    limit: query.limit,
    nextCursor,
  };
}

export function publicFeedHeaders() {
  return {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'public, max-age=5, stale-while-revalidate=15',
    'x-content-type-options': 'nosniff',
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET',
    'access-control-allow-headers': 'content-type',
    'vary': 'Accept',
  };
}
