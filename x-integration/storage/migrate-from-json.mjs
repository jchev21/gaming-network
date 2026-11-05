/**
 * One-shot migration: x-lobbies.json → SQLite.
 * Safe to re-run: skips if schema_meta.migrated_from_json = 1.
 * Does not delete the JSON file (operator keeps a backup).
 *
 * Usage (from x-integration/):
 *   node storage/migrate-from-json.mjs [dataDir]
 *   DATA_DIR=/data node storage/migrate-from-json.mjs
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { createLobbyStore } from './lobby-store.mjs';

const dataDir = process.argv[2] || process.env.DATA_DIR || './runtime';
const jsonPath = path.join(dataDir, 'x-lobbies.json');
const dbPath = path.join(dataDir, 'x-lobbies.sqlite');

async function main() {
  const store = createLobbyStore(dbPath);
  const { db } = store;

  const already = db.prepare("SELECT value FROM schema_meta WHERE key = 'migrated_from_json'").get();
  if (already?.value === '1') {
    console.log('Migration already completed (schema_meta.migrated_from_json=1). Skipping.');
    store.close();
    return;
  }

  let raw;
  try {
    raw = await fs.readFile(jsonPath, 'utf8');
  } catch (e) {
    if (e.code === 'ENOENT') {
      console.log(`No JSON file at ${jsonPath}; marking empty migration complete.`);
      db.prepare("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('migrated_from_json', '1')").run();
      store.close();
      return;
    }
    throw e;
  }

  const data = JSON.parse(raw);
  const lobbies = data.lobbies || {};
  const invites = data.invites || {};
  const joinSecrets = data.joinSecrets || {};

  console.log(`Migrating ${Object.keys(lobbies).length} lobbies, ${Object.keys(invites).length} invites, ${Object.keys(joinSecrets).length} join secrets…`);

  db.exec('BEGIN IMMEDIATE');
  try {
    for (const [id, g] of Object.entries(lobbies)) {
      const lobby = {
        id: g.id || id,
        ownerXId: g.ownerXId,
        title: g.title,
        game: g.game,
        platform: g.platform,
        mode: g.mode,
        seats: g.seats,
        roundSeconds: g.roundSeconds,
        status: g.status,
        createdAt: g.createdAt,
        entryClosesAt: g.entryClosesAt,
        finalizedAt: g.finalizedAt ?? null,
        cancelledAt: g.cancelledAt ?? null,
        sourcePostId: g.sourcePostId,
        host: g.host || null,
        winners: g.winners || [],
        withdrawnXIds: g.withdrawnXIds || [],
        removedXIds: g.removedXIds || [],
        entries: g.entries || [],
        waitlist: g.waitlist || [],
      };
      store.writeTx((tx) => {
        tx.persistLobby(lobby);
      });
    }

    for (const [tokenHash, inv] of Object.entries(invites)) {
      store.writeTx((tx) => {
        tx.putInvite(tokenHash, {
          postId: inv.postId,
          ownerXId: inv.ownerXId,
          createdAt: inv.createdAt,
          expiresAt: inv.expiresAt,
          usedAt: inv.usedAt ?? null,
        });
      });
    }

    for (const [lobbyId, sealed] of Object.entries(joinSecrets)) {
      store.writeTx((tx) => {
        tx.setJoinSecret(lobbyId, sealed, Date.now());
      });
    }

    db.prepare("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('migrated_from_json', '1')").run();
    db.prepare("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('migrated_at', ?)").run(String(Date.now()));
    db.exec('COMMIT');
    console.log('Migration committed successfully.');
  } catch (e) {
    try { db.exec('ROLLBACK'); } catch (_) {}
    console.error('Migration failed, rolled back:', e);
    store.close();
    process.exitCode = 1;
    return;
  }

  store.close();
  console.log(`SQLite database ready at ${dbPath}`);
  console.log('JSON source left in place for backup. Do not delete until verified.');
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
