/**
 * Transactional SQLite store for X game lobbies.
 * Isolated prototype (grok/lobby-storage). Domain logic stays in game-core.mjs.
 *
 * Guarantees:
 * - All mutations run inside BEGIN IMMEDIATE transactions.
 * - Concurrent joins / waitlist / cancel are serialized at the DB level.
 * - Encrypted join instructions remain opaque ciphertext.
 * - Pure domain functions (createLobby, joinLobby, …) are applied inside the tx.
 */
import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  createLobby, joinLobby, publicLobby, LobbyError,
  cancelLobby, withdrawEntry, joinWaitlist, replaceNoShow, finalizeLobby,
} from '../game-core.mjs';
import { sealJoinInstructions, openJoinInstructions, joinDetailsRole } from '../host-utils.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCHEMA_PATH = path.join(__dirname, 'schema.sql');

function openDb(dbPath) {
  const dir = path.dirname(dbPath);
  fs.mkdirSync(dir, { recursive: true });
  const db = new DatabaseSync(dbPath);
  db.exec(fs.readFileSync(SCHEMA_PATH, 'utf8'));
  db.exec('PRAGMA journal_mode = WAL;');
  db.exec('PRAGMA foreign_keys = ON;');
  db.exec('PRAGMA busy_timeout = 5000;');
  return db;
}

function rowToLobby(row, entries = [], waitlist = []) {
  if (!row) return null;
  return {
    id: row.id,
    ownerXId: row.owner_x_id,
    title: row.title,
    game: row.game,
    platform: row.platform,
    mode: row.mode,
    seats: row.seats,
    roundSeconds: row.round_seconds,
    status: row.status,
    createdAt: row.created_at,
    entryClosesAt: row.entry_closes_at,
    finalizedAt: row.finalized_at,
    cancelledAt: row.cancelled_at,
    sourcePostId: row.source_post_id || undefined,
    host: row.host_json ? JSON.parse(row.host_json) : null,
    winners: JSON.parse(row.winners_json || '[]'),
    withdrawnXIds: JSON.parse(row.withdrawn_json || '[]'),
    removedXIds: JSON.parse(row.removed_json || '[]'),
    entries,
    waitlist,
  };
}

function loadEntries(db, lobbyId) {
  const stmt = db.prepare(
    'SELECT x_id, name, joined_at FROM lobby_entries WHERE lobby_id = ? ORDER BY joined_at, x_id'
  );
  return stmt.all(lobbyId).map(r => ({ xId: r.x_id, name: r.name, joinedAt: r.joined_at }));
}

function loadWaitlist(db, lobbyId) {
  const stmt = db.prepare(
    'SELECT x_id, name, joined_at, position FROM lobby_waitlist WHERE lobby_id = ? ORDER BY position, joined_at'
  );
  return stmt.all(lobbyId).map(r => ({ xId: r.x_id, name: r.name, joinedAt: r.joined_at, position: r.position }));
}

function persistLobby(db, lobby) {
  db.prepare(`
    INSERT INTO lobbies (
      id, owner_x_id, title, game, platform, mode, seats, round_seconds,
      status, created_at, entry_closes_at, finalized_at, cancelled_at,
      source_post_id, host_json, winners_json, withdrawn_json, removed_json, version
    ) VALUES (
      @id, @owner_x_id, @title, @game, @platform, @mode, @seats, @round_seconds,
      @status, @created_at, @entry_closes_at, @finalized_at, @cancelled_at,
      @source_post_id, @host_json, @winners_json, @withdrawn_json, @removed_json, @version
    )
    ON CONFLICT(id) DO UPDATE SET
      status = excluded.status,
      entry_closes_at = excluded.entry_closes_at,
      finalized_at = excluded.finalized_at,
      cancelled_at = excluded.cancelled_at,
      winners_json = excluded.winners_json,
      withdrawn_json = excluded.withdrawn_json,
      removed_json = excluded.removed_json,
      host_json = excluded.host_json,
      version = lobbies.version + 1
  `).run({
    id: lobby.id,
    owner_x_id: lobby.ownerXId,
    title: lobby.title,
    game: lobby.game,
    platform: lobby.platform,
    mode: lobby.mode,
    seats: lobby.seats,
    round_seconds: lobby.roundSeconds,
    status: lobby.status,
    created_at: lobby.createdAt,
    entry_closes_at: lobby.entryClosesAt,
    finalized_at: lobby.finalizedAt ?? null,
    cancelled_at: lobby.cancelledAt ?? null,
    source_post_id: lobby.sourcePostId ?? null,
    host_json: lobby.host ? JSON.stringify(lobby.host) : null,
    winners_json: JSON.stringify(lobby.winners || []),
    withdrawn_json: JSON.stringify(lobby.withdrawnXIds || []),
    removed_json: JSON.stringify(lobby.removedXIds || []),
    version: 1,
  });

  db.prepare('DELETE FROM lobby_entries WHERE lobby_id = ?').run(lobby.id);
  const insE = db.prepare(
    'INSERT INTO lobby_entries (lobby_id, x_id, name, joined_at) VALUES (?, ?, ?, ?)'
  );
  for (const e of lobby.entries || []) {
    insE.run(lobby.id, e.xId, e.name, e.joinedAt);
  }

  db.prepare('DELETE FROM lobby_waitlist WHERE lobby_id = ?').run(lobby.id);
  const insW = db.prepare(
    'INSERT INTO lobby_waitlist (lobby_id, x_id, name, joined_at, position) VALUES (?, ?, ?, ?, ?)'
  );
  (lobby.waitlist || []).forEach((w, i) => {
    insW.run(lobby.id, w.xId, w.name, w.joinedAt, i + 1);
  });
}

export function createLobbyStore(dbPath) {
  const db = openDb(dbPath);

  function getLobby(id) {
    const row = db.prepare('SELECT * FROM lobbies WHERE id = ?').get(id);
    if (!row) return null;
    return rowToLobby(row, loadEntries(db, id), loadWaitlist(db, id));
  }

  function listLobbiesForActor(actorXId, limit = 50) {
    const rows = db.prepare(`
      SELECT DISTINCT l.* FROM lobbies l
      LEFT JOIN lobby_entries e ON e.lobby_id = l.id
      LEFT JOIN lobby_waitlist w ON w.lobby_id = l.id
      WHERE l.owner_x_id = ?
         OR e.x_id = ?
         OR w.x_id = ?
         OR l.withdrawn_json LIKE ?
         OR l.removed_json LIKE ?
      ORDER BY l.created_at DESC, l.id DESC
      LIMIT ?
    `).all(
      actorXId, actorXId, actorXId,
      `%"${actorXId}"%`, `%"${actorXId}"%`,
      limit
    );
    return rows.map(r => rowToLobby(r, loadEntries(db, r.id), loadWaitlist(db, r.id)));
  }

  function countOwnerLobbiesSince(ownerXId, sinceMs) {
    return db.prepare(
      'SELECT COUNT(*) AS c FROM lobbies WHERE owner_x_id = ? AND created_at >= ?'
    ).get(ownerXId, sinceMs).c;
  }

  function writeTx(fn) {
    db.exec('BEGIN IMMEDIATE');
    try {
      const result = fn({
        getLobby,
        persistLobby: (lobby) => persistLobby(db, lobby),
        deleteJoinSecret: (lobbyId) => {
          db.prepare('DELETE FROM join_secrets WHERE lobby_id = ?').run(lobbyId);
        },
        setJoinSecret: (lobbyId, sealed, now) => {
          db.prepare(`
            INSERT INTO join_secrets (lobby_id, ciphertext, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(lobby_id) DO UPDATE SET ciphertext = excluded.ciphertext, updated_at = excluded.updated_at
          `).run(lobbyId, JSON.stringify(sealed), now);
        },
        getJoinSecret: (lobbyId) => {
          const r = db.prepare('SELECT ciphertext FROM join_secrets WHERE lobby_id = ?').get(lobbyId);
          return r ? JSON.parse(r.ciphertext) : null;
        },
        putInvite: (tokenHash, invite) => {
          db.prepare(`
            INSERT INTO invites (token_hash, post_id, owner_x_id, created_at, expires_at, used_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(token_hash) DO UPDATE SET
              post_id = excluded.post_id, owner_x_id = excluded.owner_x_id,
              created_at = excluded.created_at, expires_at = excluded.expires_at, used_at = excluded.used_at
          `).run(tokenHash, invite.postId, invite.ownerXId, invite.createdAt, invite.expiresAt, invite.usedAt ?? null);
        },
        getInvite: (tokenHash) => {
          const r = db.prepare('SELECT * FROM invites WHERE token_hash = ?').get(tokenHash);
          if (!r) return null;
          return {
            postId: r.post_id,
            ownerXId: r.owner_x_id,
            createdAt: r.created_at,
            expiresAt: r.expires_at,
            usedAt: r.used_at,
          };
        },
        markInviteUsed: (tokenHash, usedAt) => {
          db.prepare('UPDATE invites SET used_at = ? WHERE token_hash = ?').run(usedAt, tokenHash);
        },
        clearUnusedInvitesForPost: (postId) => {
          db.prepare('DELETE FROM invites WHERE post_id = ? AND used_at IS NULL').run(postId);
        },
        hasLobbyForPost: (postId) => {
          return !!db.prepare('SELECT 1 FROM lobbies WHERE source_post_id = ? LIMIT 1').get(postId);
        },
        countOwnerLobbiesSince,
      });
      db.exec('COMMIT');
      return result;
    } catch (e) {
      try { db.exec('ROLLBACK'); } catch (_) { /* ignore */ }
      throw e;
    }
  }

  function readTx(fn) {
    return fn({ getLobby, listLobbiesForActor, countOwnerLobbiesSince });
  }

  return {
    db,
    getLobby: (id) => readTx(({ getLobby }) => getLobby(id)),
    listLobbiesForActor: (actorXId, limit) => readTx(({ listLobbiesForActor }) => listLobbiesForActor(actorXId, limit)),
    writeTx,
    readTx,
    close: () => db.close(),
  };
}

export function storeOps(store, { joinSecretKey, now = Date.now } = {}) {
  return {
    createFromInvite({ body, user, inviteTokenHash, sourcePostId }) {
      return store.writeTx((tx) => {
        const invite = tx.getInvite(inviteTokenHash);
        if (!invite || invite.usedAt || invite.expiresAt <= now() || invite.ownerXId !== user.id) {
          throw new LobbyError('INVITE_INVALID', 'Invite expired or not for this X account', 403);
        }
        const recent = tx.countOwnerLobbiesSince(user.id, now() - 86_400_000);
        if (recent >= 10) throw new LobbyError('RATE_LIMIT', 'Daily game limit reached', 429);
        const g = createLobby(body, user.id, now());
        g.sourcePostId = sourcePostId || invite.postId;
        tx.persistLobby(g);
        tx.markInviteUsed(inviteTokenHash, now());
        return { game: publicLobby(g, now()), lobbyId: g.id };
      });
    },

    join({ lobbyId, actorXId, displayName }) {
      return store.writeTx((tx) => {
        const g = tx.getLobby(lobbyId);
        if (!g) throw new LobbyError('NOT_FOUND', 'Game not found', 404);
        joinLobby(g, actorXId, displayName, now());
        tx.persistLobby(g);
        return publicLobby(g, now());
      });
    },

    waitlist({ lobbyId, actorXId, displayName }) {
      return store.writeTx((tx) => {
        const g = tx.getLobby(lobbyId);
        if (!g) throw new LobbyError('NOT_FOUND', 'Game not found', 404);
        joinWaitlist(g, actorXId, displayName, now());
        tx.persistLobby(g);
        return publicLobby(g, now());
      });
    },

    cancel({ lobbyId, actorXId }) {
      return store.writeTx((tx) => {
        const g = tx.getLobby(lobbyId);
        if (!g) throw new LobbyError('NOT_FOUND', 'Game not found', 404);
        cancelLobby(g, actorXId, now());
        tx.persistLobby(g);
        tx.deleteJoinSecret(lobbyId);
        return publicLobby(g, now());
      });
    },

    withdraw({ lobbyId, actorXId }) {
      return store.writeTx((tx) => {
        const g = tx.getLobby(lobbyId);
        if (!g) throw new LobbyError('NOT_FOUND', 'Game not found', 404);
        withdrawEntry(g, actorXId, now());
        tx.persistLobby(g);
        return publicLobby(g, now());
      });
    },

    replaceNoShow({ lobbyId, actorXId, seat }) {
      return store.writeTx((tx) => {
        const g = tx.getLobby(lobbyId);
        if (!g) throw new LobbyError('NOT_FOUND', 'Game not found', 404);
        replaceNoShow(g, actorXId, seat, now());
        tx.persistLobby(g);
        return publicLobby(g, now());
      });
    },

    setJoinInstructions({ lobbyId, actorXId, instructions }) {
      if (!joinSecretKey) throw new LobbyError('NOT_CONFIGURED', 'Host joining instructions are unavailable', 503);
      return store.writeTx((tx) => {
        const g = tx.getLobby(lobbyId);
        if (!g) throw new LobbyError('NOT_FOUND', 'Game not found', 404);
        finalizeLobby(g, now());
        if (g.status === 'cancelled') throw new LobbyError('CANCELLED', 'Cannot edit a cancelled game', 409);
        const role = joinDetailsRole(g, actorXId);
        if (role !== 'host') throw new LobbyError('HOST_ONLY', 'Only the host may change instructions', 403);
        const sealed = sealJoinInstructions(instructions, joinSecretKey);
        tx.setJoinSecret(lobbyId, sealed, now());
        return { role, ready: g.status === 'ready', instructions };
      });
    },

    getJoinInstructions({ lobbyId, actorXId }) {
      if (!joinSecretKey) throw new LobbyError('NOT_CONFIGURED', 'Host joining instructions are unavailable', 503);
      return store.writeTx((tx) => {
        const g = tx.getLobby(lobbyId);
        if (!g) throw new LobbyError('NOT_FOUND', 'Game not found', 404);
        const before = g.status;
        finalizeLobby(g, now());
        if (g.status !== before) tx.persistLobby(g);
        const role = joinDetailsRole(g, actorXId);
        if (!role) throw new LobbyError('NOT_SELECTED', 'Joining details are only available to the host or selected players', 403);
        const sealed = tx.getJoinSecret(lobbyId);
        return {
          role,
          ready: g.status === 'ready',
          instructions: openJoinInstructions(sealed, joinSecretKey),
        };
      });
    },

    publicGet(lobbyId) {
      return store.writeTx((tx) => {
        const g = tx.getLobby(lobbyId);
        if (!g) throw new LobbyError('NOT_FOUND', 'Game not found', 404);
        const before = g.status;
        const pub = publicLobby(g, now());
        if (g.status !== before) tx.persistLobby(g);
        return pub;
      });
    },
  };
}

export { LobbyError };
