/**
 * CLI migration tests against a real sample JSON fixture.
 * Run: node storage/migrate-from-json.test.mjs
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createLobbyStore } from './lobby-store.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const migrateScript = path.join(__dirname, 'migrate-from-json.mjs');
const fixtureSrc = path.join(__dirname, 'fixtures', 'sample-x-lobbies.json');

function runMigrate(dataDir, extraArgs = []) {
  return spawnSync(process.execPath, [migrateScript, dataDir, ...extraArgs], {
    encoding: 'utf8',
    env: { ...process.env },
  });
}

function tmpDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'gn-mig-'));
}

function cleanDb(dir) {
  for (const name of ['x-lobbies.sqlite', 'x-lobbies.sqlite-wal', 'x-lobbies.sqlite-shm']) {
    const p = path.join(dir, name);
    if (fs.existsSync(p)) fs.unlinkSync(p);
  }
}

// ── 1. Missing JSON fails closed (no --allow-empty) ──────────────────
{
  const dir = tmpDir();
  cleanDb(dir);
  const r = runMigrate(dir);
  assert.notEqual(r.status, 0, 'must exit non-zero when JSON missing');
  assert.match(r.stderr + r.stdout, /Refusing to mark migration complete|JSON source not found/);
  if (fs.existsSync(path.join(dir, 'x-lobbies.sqlite'))) {
    const store = createLobbyStore(path.join(dir, 'x-lobbies.sqlite'));
    const m = store.db.prepare("SELECT value FROM schema_meta WHERE key='migrated_from_json'").get();
    assert.notEqual(m?.value, '1');
    store.close();
  }
  fs.rmSync(dir, { recursive: true, force: true });
  console.log('✓ missing JSON fails closed (marker unchanged)');
}

// ── 2. --allow-empty marks empty install ─────────────────────────────
{
  const dir = tmpDir();
  cleanDb(dir);
  const r = runMigrate(dir, ['--allow-empty']);
  assert.equal(r.status, 0, r.stderr);
  const store = createLobbyStore(path.join(dir, 'x-lobbies.sqlite'));
  const m = store.db.prepare("SELECT value FROM schema_meta WHERE key='migrated_from_json'").get();
  assert.equal(m?.value, '1');
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
  console.log('✓ --allow-empty marks empty migration complete');
}

// ── 3. Dry-run does not write marker or data ─────────────────────────
{
  const dir = tmpDir();
  cleanDb(dir);
  fs.copyFileSync(fixtureSrc, path.join(dir, 'x-lobbies.json'));
  const r = runMigrate(dir, ['--dry-run']);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /dry-run/);
  const store = createLobbyStore(path.join(dir, 'x-lobbies.sqlite'));
  const m = store.db.prepare("SELECT value FROM schema_meta WHERE key='migrated_from_json'").get();
  assert.notEqual(m?.value, '1');
  const c = store.db.prepare('SELECT COUNT(*) AS c FROM lobbies').get().c;
  assert.equal(c, 0);
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
  console.log('✓ --dry-run leaves marker and tables empty');
}

// ── 4. Full CLI migration with sample fixture ────────────────────────
{
  const dir = tmpDir();
  cleanDb(dir);
  fs.copyFileSync(fixtureSrc, path.join(dir, 'x-lobbies.json'));
  const r = runMigrate(dir);
  assert.equal(r.status, 0, `migration failed:\n${r.stdout}\n${r.stderr}`);
  assert.match(r.stdout, /Migration committed successfully/);
  assert.match(r.stdout, /Backup written/);

  const backups = fs.readdirSync(dir).filter((f) => f.startsWith('x-lobbies.json.bak-'));
  assert.ok(backups.length >= 1, 'expected timestamped backup');
  assert.ok(fs.existsSync(path.join(dir, 'x-lobbies.json')));

  const store = createLobbyStore(path.join(dir, 'x-lobbies.sqlite'));
  const { db } = store;
  assert.equal(db.prepare("SELECT value FROM schema_meta WHERE key='migrated_from_json'").get().value, '1');
  assert.equal(db.prepare('SELECT COUNT(*) AS c FROM lobbies').get().c, 2);
  assert.equal(db.prepare('SELECT COUNT(*) AS c FROM lobby_entries').get().c, 4);
  assert.equal(db.prepare('SELECT COUNT(*) AS c FROM lobby_waitlist').get().c, 1);
  assert.equal(db.prepare('SELECT COUNT(*) AS c FROM invites').get().c, 2);
  assert.equal(db.prepare('SELECT COUNT(*) AS c FROM join_secrets').get().c, 1);

  const sealed = JSON.parse(db.prepare('SELECT ciphertext FROM join_secrets WHERE lobby_id=?').get('lobby-sample-1').ciphertext);
  assert.equal(sealed.v, 1);
  assert.equal(sealed.iv, 'dGVzdGl2MTIzNDU2');
  assert.equal(sealed.data, 'dGVzdGNpcGlwaGVydGV4dGhlcmUxMjM=');

  const g = store.getLobby('lobby-sample-1');
  assert.equal(g.ownerXId, '1001');
  assert.equal(g.entries.length, 3);
  assert.equal(g.waitlist.length, 1);
  assert.equal(g.winners.length, 3);
  assert.equal(g.sourcePostId, 'post-abc');

  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
  console.log('✓ full CLI migration imports fixture with integrity checks');
}

// ── 5. Re-run is no-op ───────────────────────────────────────────────
{
  const dir = tmpDir();
  cleanDb(dir);
  fs.copyFileSync(fixtureSrc, path.join(dir, 'x-lobbies.json'));
  assert.equal(runMigrate(dir).status, 0);
  const r2 = runMigrate(dir);
  assert.equal(r2.status, 0, r2.stderr);
  assert.match(r2.stdout, /already completed/);
  fs.rmSync(dir, { recursive: true, force: true });
  console.log('✓ re-run skips (already migrated)');
}

// ── 6. Failed import cannot leave marker set ─────────────────────────
{
  const dir = tmpDir();
  cleanDb(dir);
  const bad = {
    lobbies: {
      bad: {
        id: 'bad',
        seats: 3,
        mode: 'first',
        status: 'open',
        createdAt: 1,
        entryClosesAt: 2,
        roundSeconds: 60,
        game: 'fortnite',
        platform: 'pc',
        entries: [],
        waitlist: [],
        winners: [],
      },
    },
    invites: {},
    joinSecrets: {},
  };
  fs.writeFileSync(path.join(dir, 'x-lobbies.json'), JSON.stringify(bad));
  const r = runMigrate(dir);
  if (r.status !== 0) {
    if (fs.existsSync(path.join(dir, 'x-lobbies.sqlite'))) {
      const store = createLobbyStore(path.join(dir, 'x-lobbies.sqlite'));
      const m = store.db.prepare("SELECT value FROM schema_meta WHERE key='migrated_from_json'").get();
      assert.notEqual(m?.value, '1', 'failed migration must not set marker');
      store.close();
    }
    console.log('✓ failed import leaves marker unset');
  } else {
    console.log('✓ import with sparse lobby did not crash (nested TX fixed)');
  }
  fs.rmSync(dir, { recursive: true, force: true });
}

console.log('\nAll migrate-from-json CLI tests passed.');
