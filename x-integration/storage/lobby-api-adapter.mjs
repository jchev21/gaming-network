/**
 * Thin adapter scaffold — NOT wired into lobby-api.mjs yet.
 *
 * Purpose: show ChatGPT the minimal surface to swap JSON serial() for storeOps
 * without changing HTTP routes or domain rules.
 *
 * Enable only after:
 *  1. Migration dry-run + verify on a volume copy
 *  2. Feature flag (e.g. LOBBY_STORE=sqlite) agreed
 *  3. Review of PR #12
 *
 * This file is intentionally unused by production entrypoints on this branch.
 */
import path from 'node:path';
import crypto from 'node:crypto';
import { createLobbyStore, storeOps } from './lobby-store.mjs';
import { publicLobby, LobbyError } from '../game-core.mjs';

const sha = (s) => crypto.createHash('sha256').update(String(s)).digest('hex');

/**
 * Build a store-backed handler map that mirrors the mutation side of lobby-api.
 * Callers still own auth, origin checks, and HTTP framing.
 *
 * @param {object} opts
 * @param {string} opts.dataDir
 * @param {string} [opts.joinSecretKey]
 * @param {() => number} [opts.now]
 */
export function createStoreBackedLobbyOps({
  dataDir = './runtime',
  joinSecretKey = process.env.X_JOIN_SECRET_KEY || '',
  now = Date.now,
} = {}) {
  const dbPath = path.join(dataDir, 'x-lobbies.sqlite');
  const store = createLobbyStore(dbPath);
  const ops = storeOps(store, { joinSecretKey, now });

  return {
    store,
    ops,

    /** Create lobby after invite validation (caller already authenticated the X user). */
    createLobbyFromInvite({ body, user, rawInviteToken, sourcePostId }) {
      const inviteTokenHash = sha(rawInviteToken);
      return ops.createFromInvite({ body, user, inviteTokenHash, sourcePostId });
    },

    join({ lobbyId, actorXId, displayName }) {
      return ops.join({ lobbyId, actorXId, displayName });
    },

    waitlist({ lobbyId, actorXId, displayName }) {
      return ops.waitlist({ lobbyId, actorXId, displayName });
    },

    cancel({ lobbyId, actorXId }) {
      return ops.cancel({ lobbyId, actorXId });
    },

    withdraw({ lobbyId, actorXId }) {
      return ops.withdraw({ lobbyId, actorXId });
    },

    replaceNoShow({ lobbyId, actorXId, seat }) {
      return ops.replaceNoShow({ lobbyId, actorXId, seat });
    },

    getPublic(lobbyId) {
      return ops.publicGet(lobbyId);
    },

    getJoinInstructions({ lobbyId, actorXId }) {
      return ops.getJoinInstructions({ lobbyId, actorXId });
    },

    setJoinInstructions({ lobbyId, actorXId, instructions }) {
      return ops.setJoinInstructions({ lobbyId, actorXId, instructions });
    },

    listForActor(actorXId, limit = 50) {
      return store.listLobbiesForActor(actorXId, limit).map((g) => publicLobby(g, now()));
    },

    close() {
      store.close();
    },
  };
}

export { LobbyError };
