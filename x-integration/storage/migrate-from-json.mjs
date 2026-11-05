/**
 * One-shot migration: x-lobbies.json → SQLite.
 * Safe to re-run: skips if schema_meta.migrated_from_json = 1.
 * Does not delete the JSON file (operator keeps a backup).
 *
 * Usage (from x-integration/):
 *   node storage/migrate-from-json.mjs [dataDir]
 *   DATA_DIR=/path node storage/migrate-from-json.mjs
 *   node storage/migrate-from-json.mjs ./runtime --dry-run
 *   node storage/migrate-from-json.mjs ./runtime --allow-empty   # only for brand-new installs
 *
 * Never run against live /data until reviewed. Never prints secrets/tokens.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { createLobbyStore } from './lobby-store.mjs';

function parseArgs(argv) {
  const flags = new Set();
  const positionals = [];
  for (const a of argv.slice(2)) {
    if (a.startsWith('--')) flags.add(a);
    else positionals.push(a);
  }
  return {
    dataDir: positionals[0] || process.env.DATA_DIR || './runtime',
    dryRun: flags.has('--dry-run'),
    allowEmpty: flags.has('--allow-empty'),
  };
}

function normalizeLobby(id, g) {
  return {
    id: g.id || id,
    ownerXId: g.ownerXId,
    title: g.title,
    game: g.game,
    platform: g.platform || 'pc',
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
}

async function backupJson(jsonPath) {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const backupPath = `${jsonPath}.bak-${stamp}`;
  await fs.copyFile(jsonPath, backupPath);
  return backupPath;
}

function verifyIntegrity(db, expected) {
  const lobbyCount = db.prepare('SELECT COUNT(*) AS c FROM lobbies').get().c;
  const entryCount = db.prepare('SELECT COUNT(*) AS c FROM lobby_entries').get().c;
  const waitCount = db.prepare('SELECT COUNT(*) AS c FROM lobby_waitlist').get().c;
  const inviteCount = db.prepare('SELECT COUNT(*) AS c FROM invites').get().c;
  const secretCount = db.prepare('SELECT COUNT(*) AS c FROM join_secrets').get().c;

  const errors = [];
  if (lobbyCount !== expected.lobbies) errors.push(`lobbies: expected ${expected.lobbies}, got ${lobbyCount}`);
  if (inviteCount !== expected.invites) errors.push(`invites: expected ${expected.invites}, got ${inviteCount}`);
  if (secretCount !== expected.secrets) errors.push(`join_secrets: expected ${expected.secrets}, got ${secretCount}`);
  if (entryCount !== expected.entries) errors.push(`entries: expected ${expected.entries}, got ${entryCount}`);
  if (waitCount !== expected.waitlist) errors.push(`waitlist: expected ${expected.waitlist}, got ${waitCount}`);

  const orphanEntries = db.prepare(`
    SELECT COUNT(*) AS c FROM lobby_entries e
    LEFT JOIN lobbies l ON l.id = e.lobby_id WHERE l.id IS NULL
  `).get().c;
  const orphanWait = db.prepare(`
    SELECT COUNT(*) AS c FROM lobby_waitlist w
    LEFT JOIN lobbies l ON l.id = w.lobby_id WHERE l.id IS NULL
  `).get().c;
  const orphanSecrets = db.prepare(`
    SELECT COUNT(*) AS c FROM join_secrets s
    LEFT JOIN lobbies l ON l.id = s.lobby_id WHERE l.id IS NULL
  `).get().c;
  if (orphanEntries) errors.push(`orphan lobby_entries: ${orphanEntries}`);
  if (orphanWait) errors.push(`orphan lobby_waitlist: ${orphanWait}`);
  if (orphanSecrets) errors.push(`orphan join_secrets: ${orphanSecrets}`);

  return { lobbyCount, entryCount, waitCount, inviteCount, secretCount, errors };
}

async function main() {
  const { dataDir, dryRun, allowEmpty } = parseArgs(process.argv);
  const jsonPath = path.join(dataDir, 'x-lobbies.json');
  const dbPath = path.join(dataDir, 'x-lobbies.sqlite');

  await fs.mkdir(dataDir, { recursive: true });

  const store = createLobbyStore(dbPath);
  const { db } = store;

  try {
    const already = db.prepare("SELECT value FROM schema_meta WHERE key = 'migrated_from_json'").get();
    if (already?.value === '1') {
      console.log('Migration already completed (schema_meta.migrated_from_json=1). Skipping.');
      return;
    }

    let raw;
    try {
      raw = await fs.readFile(jsonPath, 'utf8');
    } catch (e) {
      if (e.code === 'ENOENT') {
        if (!allowEmpty) {
          console.error(
            `ERROR: JSON source not found at ${jsonPath}.\n` +
            `Refusing to mark migration complete (fail-closed).\n` +
            `Pass --allow-empty only for a brand-new install with no prior lobbies.`
          );
          process.exitCode = 1;
          return;
        }
        if (dryRun) {
          console.log(`[dry-run] would mark empty migration complete for ${jsonPath}`);
          return;
        }
        db.exec('BEGIN IMMEDIATE');
        try {
          db.prepare("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('migrated_from_json', '1')").run();
          db.prepare("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('migrated_at', ?)").run(String(Date.now()));
          db.prepare("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('migrated_empty', '1')").run();
          db.exec('COMMIT');
        } catch (err) {
          try { db.exec('ROLLBACK'); } catch (_) {}
          throw err;
        }
        console.log('Empty migration marked complete (--allow-empty).');
        return;
      }
      throw e;
    }

    const data = JSON.parse(raw);
    const lobbies = data.lobbies || {};
    const invites = data.invites || {};
    const joinSecrets = data.joinSecrets || {};

    let expectedEntries = 0;
    let expectedWait = 0;
    for (const g of Object.values(lobbies)) {
      expectedEntries += (g.entries || []).length;
      expectedWait += (g.waitlist || []).length;
    }
    const expected = {
      lobbies: Object.keys(lobbies).length,
      invites: Object.keys(invites).length,
      secrets: Object.keys(joinSecrets).length,
      entries: expectedEntries,
      waitlist: expectedWait,
    };

    console.log(
      `Source: ${expected.lobbies} lobbies, ${expected.entries} entries, ` +
      `${expected.waitlist} waitlist, ${expected.invites} invites, ${expected.secrets} join secrets`
    );

    if (dryRun) {
      console.log(`[dry-run] would import into ${dbPath}`);
      console.log('[dry-run] no writes performed; marker left unchanged.');
      return;
    }

    const backupPath = await backupJson(jsonPath);
    console.log(`Backup written: ${backupPath}`);

    // ONE transactional write for the entire import — no nested BEGIN.
    store.writeTx((tx) => {
      for (const [id, g] of Object.entries(lobbies)) {
        tx.persistLobby(normalizeLobby(id, g));
      }
      for (const [tokenHash, inv] of Object.entries(invites)) {
        tx.putInvite(tokenHash, {
          postId: inv.postId,
          ownerXId: inv.ownerXId,
          createdAt: inv.createdAt,
          expiresAt: inv.expiresAt,
          usedAt: inv.usedAt ?? null,
        });
      }
      for (const [lobbyId, sealed] of Object.entries(joinSecrets)) {
        tx.setJoinSecret(lobbyId, sealed, Date.now());
      }
      db.prepare("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('migrated_from_json', '1')").run();
      db.prepare("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('migrated_at', ?)").run(String(Date.now()));
      db.prepare("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('migrated_from', ?)").run(jsonPath);
    });

    const report = verifyIntegrity(db, expected);
    if (report.errors.length) {
      console.error('Integrity check FAILED after commit:', report.errors);
      console.error(
        'Restore from backup JSON and delete the sqlite file to retry:\n' +
        `  backup: ${backupPath}\n` +
        `  sqlite: ${dbPath}`
      );
      process.exitCode = 1;
      return;
    }

    console.log('Migration committed successfully.');
    console.log(
      `Verified: ${report.lobbyCount} lobbies, ${report.entryCount} entries, ` +
      `${report.waitCount} waitlist, ${report.inviteCount} invites, ${report.secretCount} secrets`
    );
    console.log(`SQLite ready at ${dbPath}`);
    console.log('JSON source left in place. Do not delete until verified in staging.');
  } finally {
    store.close();
  }
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
