/**
 * Persistent invite-to-lobby API; all writes require verified X identity or admin approval.
 *
 * Storage backends:
 *   - JSON (default): process-local serial queue + x-lobbies.json
 *   - SQLite (opt-in): LOBBY_STORE=sqlite — requires migrated x-lobbies.sqlite
 *
 * Never silently creates empty SQLite state over existing JSON.
 */
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import {
  createLobby, joinLobby, publicLobby, LobbyError,
  cancelLobby, withdrawEntry, joinWaitlist, replaceNoShow,
} from './game-core.mjs';
import { sealJoinInstructions, openJoinInstructions, joinDetailsRole } from './host-utils.mjs';
import { createLobbyStore } from './storage/lobby-store.mjs';

const sha = (s) => crypto.createHash('sha256').update(String(s)).digest('hex');
const send = (res, status, body) => {
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff',
  });
  res.end(JSON.stringify(body));
};
const err = (code, message, status = 400) => new LobbyError(code, message, status);

async function readBody(req) {
  let bytes = 0;
  const chunks = [];
  for await (const c of req) {
    bytes += c.length;
    if (bytes > 8192) throw err('TOO_LARGE', 'Request body too large', 413);
    chunks.push(c);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    throw err('INVALID_JSON', 'Invalid JSON');
  }
}

async function loadJson(file) {
  try {
    const d = JSON.parse(await fs.readFile(file, 'utf8'));
    return { invites: d.invites || {}, lobbies: d.lobbies || {}, joinSecrets: d.joinSecrets || {} };
  } catch (e) {
    if (e.code !== 'ENOENT') throw e;
    return { invites: {}, lobbies: {}, joinSecrets: {} };
  }
}

async function saveJson(file, db) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file + '.tmp', JSON.stringify(db), { mode: 0o600 });
  await fs.rename(file + '.tmp', file);
}

function resolveStoreMode(explicit) {
  if (explicit === 'sqlite' || explicit === 'json') return explicit;
  const env = String(process.env.LOBBY_STORE || 'json').toLowerCase();
  return env === 'sqlite' ? 'sqlite' : 'json';
}

function requireJoinSecretKey(key, mode) {
  if (mode === 'sqlite') {
    if (!key || key.length < 32) {
      throw new Error('LOBBY_STORE=sqlite requires X_JOIN_SECRET_KEY (≥32 characters); admin token is not accepted');
    }
  }
  return key || '';
}

export async function createLobbyApi({
  dataDir = './runtime',
  auth,
  mentions,
  adminToken = '',
  moderatorXId = process.env.X_MODERATOR_USER_ID || '',
  publicOrigin,
  now = Date.now,
  joinSecretKey = process.env.X_JOIN_SECRET_KEY || '',
  storeMode,
} = {}) {
  if (!auth || typeof auth.authenticated !== 'function') throw Error('X auth required');
  if (!publicOrigin || !/^https:\/\/[^/?#]+$/.test(publicOrigin)) {
    throw Error('A secure public origin is required');
  }

  const mode = resolveStoreMode(storeMode);
  const effectiveJoinKey = mode === 'sqlite'
    ? requireJoinSecretKey(joinSecretKey || process.env.X_JOIN_SECRET_KEY, mode)
    : (joinSecretKey || process.env.X_JOIN_SECRET_KEY || adminToken);

  let backend;

  if (mode === 'sqlite') {
    const dbPath = path.join(dataDir, 'x-lobbies.sqlite');
    const store = createLobbyStore(dbPath);
    const marker = store.db.prepare(
      "SELECT value FROM schema_meta WHERE key = 'migrated_from_json'"
    ).get();
    if (marker?.value !== '1') {
      store.close();
      throw new Error(
        'LOBBY_STORE=sqlite requires a completed migration (schema_meta.migrated_from_json=1). ' +
        'Run: node storage/migrate-from-json.mjs <dataDir>  (or --allow-empty for new installs). ' +
        'Refusing to create empty game state over existing JSON.'
      );
    }
    backend = createSqliteBackend(store, { now, joinSecretKey: effectiveJoinKey, mentions });
  } else {
    const file = path.join(dataDir, 'x-lobbies.json');
    const db = await loadJson(file);
    let queue = Promise.resolve();
    async function serial(fn, write = true) {
      const task = queue.then(async () => {
        const result = await fn();
        if (write) await saveJson(file, db);
        return result;
      });
      queue = task.catch(() => {});
      return task;
    }
    backend = createJsonBackend(db, serial, { now, joinSecretKey: effectiveJoinKey, mentions });
  }

  function admin(req) {
    const given = req.headers.authorization || '';
    if (!adminToken || !given.startsWith('Bearer ')) return false;
    const a = Buffer.from(given.slice(7));
    const b = Buffer.from(adminToken);
    return a.length === b.length && crypto.timingSafeEqual(a, b);
  }
  function origin(req) {
    if (req.headers.origin !== publicOrigin) throw err('FORBIDDEN_ORIGIN', 'Same-origin request required', 403);
  }
  function who(req) {
    const user = auth.authenticated(req);
    if (!user) throw err('AUTH_REQUIRED', 'Sign in with X first', 401);
    return user;
  }
  function isModerator(req) {
    const u = auth.authenticated(req);
    return /^\d+$/.test(String(moderatorXId || '')) && u && u.id === String(moderatorXId);
  }

  async function handle(req, res, url) {
    const method = req.method || 'GET';
    const pathname = url.pathname;

    if (method === 'GET' && pathname === '/api/my-games') {
      try {
        const actor = who(req);
        const result = await backend.myGames(actor);
        send(res, 200, result);
      } catch (e) {
        send(res, e.status || 500, { error: e.code || 'FAILED', message: e.status ? e.message : 'Server temporarily unavailable' });
      }
      return true;
    }

    if (method === 'GET' && pathname === '/api/moderation/mentions') {
      if (!isModerator(req)) { send(res, 403, { error: 'Moderator X sign-in required' }); return true; }
      const requests = await backend.moderationMentions();
      send(res, 200, { requests });
      return true;
    }

    if (method === 'POST' && (pathname === '/admin/invites' || pathname === '/api/moderation/approve')) {
      const viaSession = pathname === '/api/moderation/approve';
      if (viaSession && !isModerator(req)) { send(res, 403, { error: 'Moderator X sign-in required' }); return true; }
      if (!viaSession && !admin(req)) { send(res, 401, { error: 'Unauthorized' }); return true; }
      try {
        if (viaSession) origin(req);
        const body = await readBody(req);
        const result = await backend.approveInvite(body);
        send(res, 201, { ...result, setupUrl: publicOrigin + '/setup?invite=' + encodeURIComponent(result.rawToken) });
      } catch (e) {
        send(res, e.status || 500, { error: e.code || 'FAILED', message: e.message });
      }
      return true;
    }

    if (method === 'POST' && pathname === '/api/lobbies') {
      try {
        origin(req);
        const user = who(req);
        const body = await readBody(req);
        const result = await backend.createLobby(body, user);
        send(res, 201, { game: result.game, lobbyUrl: publicOrigin + '/lobby?id=' + result.game.id });
      } catch (e) {
        send(res, e.status || 500, { error: e.code || 'FAILED', message: e.message });
      }
      return true;
    }

    const manage = pathname.match(/^\/api\/lobbies\/([a-zA-Z0-9-]+)\/(me|cancel|withdraw|waitlist|replace)$/);
    if (manage && ((manage[2] === 'me' && method === 'GET') || (method === 'POST' && manage[2] !== 'me'))) {
      try {
        const actor = who(req);
        if (method === 'POST') origin(req);
        const body = manage[2] === 'replace' && method === 'POST' ? await readBody(req) : null;
        const result = await backend.manage(manage[1], manage[2], actor, body);
        send(res, 200, result);
      } catch (e) {
        send(res, e.status || 500, { error: e.code || 'FAILED', message: e.status ? e.message : 'Server temporarily unavailable' });
      }
      return true;
    }

    const privateMatch = pathname.match(/^\/api\/lobbies\/([a-zA-Z0-9-]+)\/join-details$/);
    if (privateMatch && (method === 'GET' || method === 'POST')) {
      try {
        const actor = who(req);
        if (!effectiveJoinKey) throw err('NOT_CONFIGURED', 'Host joining instructions are unavailable', 503);
        let body = null;
        if (method === 'POST') { origin(req); body = await readBody(req); }
        const result = await backend.joinDetails(privateMatch[1], actor, method, body);
        send(res, 200, result);
      } catch (e) {
        send(res, e.status || 500, { error: e.code || 'FAILED', message: e.status ? e.message : 'Server temporarily unavailable' });
      }
      return true;
    }

    const match = pathname.match(/^\/api\/lobbies\/([a-zA-Z0-9-]+)(\/join)?$/);
    if (match && method === 'GET' && !match[2]) {
      try {
        const result = await backend.getPublic(match[1]);
        send(res, 200, { game: result });
      } catch (e) {
        send(res, e.status || 500, { error: e.code || 'FAILED', message: e.message });
      }
      return true;
    }
    if (match && match[2] && method === 'POST') {
      try {
        origin(req);
        const user = who(req);
        const result = await backend.join(match[1], user);
        send(res, 200, { game: result });
      } catch (e) {
        send(res, e.status || 500, { error: e.code || 'FAILED', message: e.message });
      }
      return true;
    }
    return false;
  }

  return { handle, storeMode: mode, close: backend.close || (() => {}) };
}

function createJsonBackend(db, serial, { now, joinSecretKey, mentions }) {
  return {
    async myGames(actor) {
      return serial(() => {
        const all = Object.values(db.lobbies).filter((g) =>
          g.ownerXId === actor.id ||
          g.entries.some((e) => e.xId === actor.id) ||
          (g.waitlist || []).some((e) => e.xId === actor.id) ||
          (g.withdrawnXIds || []).includes(actor.id) ||
          (g.removedXIds || []).includes(actor.id)
        );
        all.sort((a, b) => b.createdAt - a.createdAt || b.id.localeCompare(a.id));
        return {
          games: all.slice(0, 50).map((g) => {
            const game = publicLobby(g, now());
            const role = g.ownerXId === actor.id ? 'host'
              : (g.withdrawnXIds || []).includes(actor.id) ? 'withdrawn'
              : (g.removedXIds || []).includes(actor.id) ? 'removed'
              : (g.waitlist || []).some((e) => e.xId === actor.id) ? 'waitlisted' : 'player';
            return { ...game, viewerRole: role, viewerSelected: game.status === 'ready' && g.winners.includes(actor.id) };
          }),
        };
      }, false);
    },

    async moderationMentions() {
      return (mentions.pending || []).slice(0, 100).map((p) => ({
        post_id: p.post_id,
        created_at: p.created_at,
        request_type: p.request_type,
        excerpt: p.excerpt,
        status: p.status,
        game_created: Object.values(db.lobbies).some((g) => g.sourcePostId === p.post_id),
      }));
    },

    async approveInvite(body) {
      return serial(() => {
        const post = (mentions.pending || []).find((p) => p.post_id === String(body.post_id || ''));
        if (!post || !/^\d+$/.test(post.author_id)) throw err('MENTION_NOT_FOUND', 'Recognized mention not found', 404);
        if (Object.values(db.lobbies).some((g) => g.sourcePostId === post.post_id)) {
          throw err('ALREADY_USED', 'Mention already has a game', 409);
        }
        const raw = crypto.randomBytes(32).toString('base64url');
        const key = sha(raw);
        for (const [k, v] of Object.entries(db.invites)) {
          if (v.postId === post.post_id && !v.usedAt) delete db.invites[k];
        }
        db.invites[key] = {
          postId: post.post_id,
          ownerXId: post.author_id,
          createdAt: now(),
          expiresAt: now() + 86400000,
          usedAt: null,
        };
        return { rawToken: raw, expiresAt: db.invites[key].expiresAt };
      });
    },

    async createLobby(body, user) {
      return serial(() => {
        const token = String(body.inviteToken || '');
        if (!/^[A-Za-z0-9_-]{43}$/.test(token)) throw err('INVITE_REQUIRED', 'Valid invitation required', 403);
        const invite = db.invites[sha(token)];
        if (!invite || invite.usedAt || invite.expiresAt <= now() || invite.ownerXId !== user.id) {
          throw err('INVITE_INVALID', 'Invite expired or not for this X account', 403);
        }
        const recent = Object.values(db.lobbies).filter(
          (g) => g.ownerXId === user.id && g.createdAt >= now() - 86400000
        ).length;
        if (recent >= 10) throw err('RATE_LIMIT', 'Daily game limit reached', 429);
        const g = createLobby(body, user.id, now());
        g.sourcePostId = invite.postId;
        db.lobbies[g.id] = g;
        invite.usedAt = now();
        return { game: publicLobby(g, now()) };
      });
    },

    async manage(lobbyId, action, actor, body) {
      return serial(() => {
        const game = db.lobbies[lobbyId];
        if (!game) throw err('NOT_FOUND', 'Game not found', 404);
        publicLobby(game, now());
        if (action === 'waitlist') {
          joinWaitlist(game, actor.id, '@' + actor.username, now());
          return { game: publicLobby(game, now()) };
        }
        if (action === 'replace') {
          replaceNoShow(game, actor.id, body?.seat, now());
          return { game: publicLobby(game, now()) };
        }
        if (action === 'cancel') {
          cancelLobby(game, actor.id, now());
          delete db.joinSecrets[game.id];
          return { game: publicLobby(game, now()) };
        }
        if (action === 'withdraw') {
          withdrawEntry(game, actor.id, now());
          return { game: publicLobby(game, now()) };
        }
        const joined = game.entries.some((p) => p.xId === actor.id);
        const queuePosition = (game.waitlist || []).findIndex((p) => p.xId === actor.id);
        const isHost = game.ownerXId === actor.id;
        const withdrawn = (game.withdrawnXIds || []).includes(actor.id);
        const removed = (game.removedXIds || []).includes(actor.id);
        return {
          isHost, joined,
          selected: game.status === 'ready' && game.winners.includes(actor.id),
          waitlistPosition: queuePosition < 0 ? null : queuePosition + 1,
          withdrawn, removed,
          canCancel: isHost && game.status !== 'cancelled',
          canReplace: isHost && game.mode === 'first' && game.status === 'ready',
          canWaitlist: !isHost && game.mode === 'first' && game.status === 'ready' && !joined && queuePosition < 0 && !withdrawn && !removed && (game.waitlist || []).length < 100,
          canWithdraw: (joined && game.status === 'open') || queuePosition >= 0,
        };
      }, action === 'me' ? false : true);
    },

    async joinDetails(lobbyId, actor, method, body) {
      return serial(() => {
        const g = db.lobbies[lobbyId];
        if (!g) throw err('NOT_FOUND', 'Game not found', 404);
        publicLobby(g, now());
        if (method === 'POST' && g.status === 'cancelled') throw err('CANCELLED', 'Cannot edit a cancelled game', 409);
        const role = joinDetailsRole(g, actor.id);
        if (!role) throw err('NOT_SELECTED', 'Joining details are only available to the host or selected players', 403);
        if (method === 'POST') {
          if (role !== 'host') throw err('HOST_ONLY', 'Only the host may change instructions', 403);
          db.joinSecrets[g.id] = sealJoinInstructions(body.instructions, joinSecretKey);
        }
        return {
          role,
          ready: g.status === 'ready',
          instructions: openJoinInstructions(db.joinSecrets[g.id], joinSecretKey),
        };
      });
    },

    async getPublic(lobbyId) {
      return serial(() => publicLobby(db.lobbies[lobbyId], now()), false);
    },

    async join(lobbyId, user) {
      return serial(() => {
        const g = db.lobbies[lobbyId];
        if (!g) throw err('NOT_FOUND', 'Game not found', 404);
        joinLobby(g, user.id, '@' + user.username, now());
        return publicLobby(g, now());
      });
    },
  };
}

function createSqliteBackend(store, { now, joinSecretKey, mentions }) {
  return {
    close: () => store.close(),

    async myGames(actor) {
      const all = store.listLobbiesForActor(actor.id, 50);
      return {
        games: all.map((g) => {
          const game = publicLobby(g, now());
          const role = g.ownerXId === actor.id ? 'host'
            : (g.withdrawnXIds || []).includes(actor.id) ? 'withdrawn'
            : (g.removedXIds || []).includes(actor.id) ? 'removed'
            : (g.waitlist || []).some((e) => e.xId === actor.id) ? 'waitlisted' : 'player';
          return { ...game, viewerRole: role, viewerSelected: game.status === 'ready' && g.winners.includes(actor.id) };
        }),
      };
    },

    async moderationMentions() {
      return store.writeTx((tx) =>
        (mentions.pending || []).slice(0, 100).map((p) => ({
          post_id: p.post_id,
          created_at: p.created_at,
          request_type: p.request_type,
          excerpt: p.excerpt,
          status: p.status,
          game_created: tx.hasLobbyForPost(p.post_id),
        }))
      );
    },

    async approveInvite(body) {
      return store.writeTx((tx) => {
        const post = (mentions.pending || []).find((p) => p.post_id === String(body.post_id || ''));
        if (!post || !/^\d+$/.test(post.author_id)) throw err('MENTION_NOT_FOUND', 'Recognized mention not found', 404);
        if (tx.hasLobbyForPost(post.post_id)) throw err('ALREADY_USED', 'Mention already has a game', 409);
        const raw = crypto.randomBytes(32).toString('base64url');
        const key = sha(raw);
        tx.clearUnusedInvitesForPost(post.post_id);
        tx.putInvite(key, {
          postId: post.post_id,
          ownerXId: post.author_id,
          createdAt: now(),
          expiresAt: now() + 86400000,
          usedAt: null,
        });
        return { rawToken: raw, expiresAt: now() + 86400000 };
      });
    },

    async createLobby(body, user) {
      return store.writeTx((tx) => {
        const token = String(body.inviteToken || '');
        if (!/^[A-Za-z0-9_-]{43}$/.test(token)) throw err('INVITE_REQUIRED', 'Valid invitation required', 403);
        const invite = tx.getInvite(sha(token));
        if (!invite || invite.usedAt || invite.expiresAt <= now() || invite.ownerXId !== user.id) {
          throw err('INVITE_INVALID', 'Invite expired or not for this X account', 403);
        }
        const recent = tx.countOwnerLobbiesSince(user.id, now() - 86400000);
        if (recent >= 10) throw err('RATE_LIMIT', 'Daily game limit reached', 429);
        const g = createLobby(body, user.id, now());
        g.sourcePostId = invite.postId;
        tx.persistLobby(g);
        tx.markInviteUsed(sha(token), now());
        return { game: publicLobby(g, now()) };
      });
    },

    async manage(lobbyId, action, actor, body) {
      return store.writeTx((tx) => {
        const game = tx.getLobby(lobbyId);
        if (!game) throw err('NOT_FOUND', 'Game not found', 404);
        publicLobby(game, now());
        if (action === 'waitlist') {
          joinWaitlist(game, actor.id, '@' + actor.username, now());
          tx.persistLobby(game);
          return { game: publicLobby(game, now()) };
        }
        if (action === 'replace') {
          replaceNoShow(game, actor.id, body?.seat, now());
          tx.persistLobby(game);
          return { game: publicLobby(game, now()) };
        }
        if (action === 'cancel') {
          cancelLobby(game, actor.id, now());
          tx.persistLobby(game);
          tx.deleteJoinSecret(lobbyId);
          return { game: publicLobby(game, now()) };
        }
        if (action === 'withdraw') {
          withdrawEntry(game, actor.id, now());
          tx.persistLobby(game);
          return { game: publicLobby(game, now()) };
        }
        const joined = game.entries.some((p) => p.xId === actor.id);
        const queuePosition = (game.waitlist || []).findIndex((p) => p.xId === actor.id);
        const isHost = game.ownerXId === actor.id;
        const withdrawn = (game.withdrawnXIds || []).includes(actor.id);
        const removed = (game.removedXIds || []).includes(actor.id);
        return {
          isHost, joined,
          selected: game.status === 'ready' && game.winners.includes(actor.id),
          waitlistPosition: queuePosition < 0 ? null : queuePosition + 1,
          withdrawn, removed,
          canCancel: isHost && game.status !== 'cancelled',
          canReplace: isHost && game.mode === 'first' && game.status === 'ready',
          canWaitlist: !isHost && game.mode === 'first' && game.status === 'ready' && !joined && queuePosition < 0 && !withdrawn && !removed && (game.waitlist || []).length < 100,
          canWithdraw: (joined && game.status === 'open') || queuePosition >= 0,
        };
      });
    },

    async joinDetails(lobbyId, actor, method, body) {
      return store.writeTx((tx) => {
        const g = tx.getLobby(lobbyId);
        if (!g) throw err('NOT_FOUND', 'Game not found', 404);
        publicLobby(g, now());
        if (method === 'POST' && g.status === 'cancelled') throw err('CANCELLED', 'Cannot edit a cancelled game', 409);
        const role = joinDetailsRole(g, actor.id);
        if (!role) throw err('NOT_SELECTED', 'Joining details are only available to the host or selected players', 403);
        if (method === 'POST') {
          if (role !== 'host') throw err('HOST_ONLY', 'Only the host may change instructions', 403);
          const sealed = sealJoinInstructions(body.instructions, joinSecretKey);
          tx.setJoinSecret(lobbyId, sealed, now());
          return { role, ready: g.status === 'ready', instructions: body.instructions.trim() };
        }
        const sealed = tx.getJoinSecret(lobbyId);
        return {
          role,
          ready: g.status === 'ready',
          instructions: openJoinInstructions(sealed, joinSecretKey),
        };
      });
    },

    async getPublic(lobbyId) {
      return store.writeTx((tx) => {
        const g = tx.getLobby(lobbyId);
        if (!g) throw err('NOT_FOUND', 'Game not found', 404);
        const before = g.status;
        const pub = publicLobby(g, now());
        if (g.status !== before) tx.persistLobby(g);
        return pub;
      });
    },

    async join(lobbyId, user) {
      return store.writeTx((tx) => {
        const g = tx.getLobby(lobbyId);
        if (!g) throw err('NOT_FOUND', 'Game not found', 404);
        joinLobby(g, user.id, '@' + user.username, now());
        tx.persistLobby(g);
        return publicLobby(g, now());
      });
    },
  };
}
