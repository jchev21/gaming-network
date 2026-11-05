/**
 * Concurrency-oriented tests for transactional lobby storage.
 * These exercise BEGIN IMMEDIATE serialization within a single process.
 * They do NOT prove multi-host safety (see STORAGE-DESIGN.md).
 *
 * Run: node storage/lobby-store.concurrency.test.mjs
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { createLobbyStore, storeOps, LobbyError } from './lobby-store.mjs';
import { createLobby } from '../game-core.mjs';

const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'gn-conc-'));
const dbPath = path.join(tmpRoot, 'conc.sqlite');
const SECRET = 'test-join-secret-key-at-least-32-chars!!';
let clock = 1_700_000_000_000;
const now = () => clock;

function freshStore() {
  for (const s of ['', '-wal', '-shm']) {
    const p = dbPath + s;
    if (fs.existsSync(p)) fs.unlinkSync(p);
  }
  const store = createLobbyStore(dbPath);
  const ops = storeOps(store, { joinSecretKey: SECRET, now });
  return { store, ops };
}

function assertCode(fn, code) {
  let err;
  try { fn(); } catch (e) { err = e; }
  assert.ok(err, `expected error ${code}`);
  assert.equal(err.code, code, `expected ${code}, got ${err?.code}: ${err?.message}`);
}

// ── 1. Two joins competing for the final seat ────────────────────────
{
  const { store, ops } = freshStore();
  const g = createLobby({ game: 'fortnite', title: 'Last Seat', seats: 2, mode: 'first' }, '1', now());
  store.writeTx((tx) => tx.persistLobby(g));
  ops.join({ lobbyId: g.id, actorXId: '10', displayName: '@first' });

  const results = [];
  const errors = [];
  for (const id of ['20', '21']) {
    try {
      results.push(ops.join({ lobbyId: g.id, actorXId: id, displayName: `@u${id}` }));
    } catch (e) {
      errors.push(e);
    }
  }
  assert.equal(results.length, 1, 'exactly one join must succeed for the last seat');
  assert.equal(errors.length, 1, 'exactly one join must fail');
  assert.ok(['FULL', 'CLOSED', 'DUPLICATE'].includes(errors[0].code) || errors[0].status >= 400);
  const final = store.getLobby(g.id);
  assert.equal(final.entries.length, 2);
  assert.equal(final.status, 'ready');
  store.close();
  console.log('✓ final-seat race: exactly one of two competing joins wins');
}

// ── 2. Invite consumed at most once ──────────────────────────────────
{
  const { store, ops } = freshStore();
  const tokenHash = crypto.createHash('sha256').update('raw-invite-token').digest('hex');
  store.writeTx((tx) => {
    tx.putInvite(tokenHash, {
      postId: 'post-1',
      ownerXId: '99',
      createdAt: now(),
      expiresAt: now() + 86_400_000,
      usedAt: null,
    });
  });

  const body = { game: 'warzone', title: 'Invite Game', seats: 3, mode: 'first' };
  const first = ops.createFromInvite({
    body, user: { id: '99' }, inviteTokenHash: tokenHash, sourcePostId: 'post-1',
  });
  assert.ok(first.lobbyId);

  assertCode(
    () => ops.createFromInvite({
      body, user: { id: '99' }, inviteTokenHash: tokenHash, sourcePostId: 'post-1',
    }),
    'INVITE_INVALID'
  );
  store.close();
  console.log('✓ invite token consumed at most once');
}

// ── 3. Two waitlist promotions cannot steal the same seat ────────────
{
  const { store, ops } = freshStore();
  const g = createLobby({ game: 'fortnite', title: 'Promote Once', seats: 2, mode: 'first' }, '30', now());
  store.writeTx((tx) => tx.persistLobby(g));
  ops.join({ lobbyId: g.id, actorXId: '31', displayName: '@a' });
  ops.join({ lobbyId: g.id, actorXId: '32', displayName: '@b' });
  ops.waitlist({ lobbyId: g.id, actorXId: '33', displayName: '@w1' });
  ops.waitlist({ lobbyId: g.id, actorXId: '34', displayName: '@w2' });

  ops.replaceNoShow({ lobbyId: g.id, actorXId: '30', seat: 0 });
  const mid = store.getLobby(g.id);
  assert.ok(mid.winners.includes('33'));
  assert.equal(mid.waitlist.length, 1);

  ops.replaceNoShow({ lobbyId: g.id, actorXId: '30', seat: 0 });
  const end = store.getLobby(g.id);
  const uniqueWinners = new Set(end.winners);
  assert.equal(uniqueWinners.size, end.winners.length, 'no duplicate winners');
  store.close();
  console.log('✓ waitlist promotion stays consistent across sequential replaces');
}

// ── 4. Cancel mid-flight clears secrets and blocks further joins ─────
{
  const { store, ops } = freshStore();
  const g = createLobby({ game: 'apex-legends', title: 'Cancel Race', seats: 4 }, '40', now());
  store.writeTx((tx) => tx.persistLobby(g));
  ops.setJoinInstructions({ lobbyId: g.id, actorXId: '40', instructions: 'party: CANCEL-TEST-01' });
  ops.cancel({ lobbyId: g.id, actorXId: '40' });

  let joinErr;
  try {
    ops.join({ lobbyId: g.id, actorXId: '41', displayName: '@late' });
  } catch (e) {
    joinErr = e;
  }
  assert.ok(joinErr, 'join after cancel must fail');
  assert.ok(['CANCELLED', 'CLOSED'].includes(joinErr.code), `got ${joinErr.code}`);
  const secret = store.db.prepare('SELECT 1 FROM join_secrets WHERE lobby_id = ?').get(g.id);
  assert.equal(secret, undefined);
  store.close();
  console.log('✓ cancel blocks joins and removes join secrets');
}

// ── 5. Simulated crash: aborted TX leaves prior state intact ─────────
{
  const { store, ops } = freshStore();
  const g = createLobby({ game: 'minecraft', title: 'Crash Safety', seats: 3 }, '50', now());
  store.writeTx((tx) => tx.persistLobby(g));
  ops.join({ lobbyId: g.id, actorXId: '51', displayName: '@ok' });

  let threw = false;
  try {
    store.writeTx((tx) => {
      const lobby = tx.getLobby(g.id);
      lobby.entries.push({ xId: '52', name: '@ghost', joinedAt: now() });
      tx.persistLobby(lobby);
      throw new Error('simulated crash before commit');
    });
  } catch (e) {
    threw = true;
    assert.match(e.message, /simulated crash/);
  }
  assert.ok(threw);
  const after = store.getLobby(g.id);
  assert.equal(after.entries.length, 1, 'rolled-back TX must not keep the ghost entry');
  assert.equal(after.entries[0].xId, '51');
  store.close();
  console.log('✓ simulated crash: rollback preserves pre-TX state');
}

// ── 6. Rapid sequential joins under single store (serialization) ─────
{
  const { store, ops } = freshStore();
  const g = createLobby({ game: 'valorant', title: 'Burst', seats: 8, mode: 'first' }, '60', now());
  store.writeTx((tx) => tx.persistLobby(g));
  const ids = Array.from({ length: 12 }, (_, i) => String(100 + i));
  let ok = 0;
  let fail = 0;
  for (const id of ids) {
    try {
      ops.join({ lobbyId: g.id, actorXId: id, displayName: `@p${id}` });
      ok++;
    } catch {
      fail++;
    }
  }
  assert.equal(ok, 8);
  assert.equal(fail, 4);
  const final = store.getLobby(g.id);
  assert.equal(final.entries.length, 8);
  assert.equal(final.status, 'ready');
  store.close();
  console.log('✓ burst joins: capacity hard-capped at seats under sequential TX');
}

try { fs.rmSync(tmpRoot, { recursive: true, force: true }); } catch (_) {}

console.log('\nAll concurrency-oriented lobby-store tests passed.');
console.log('Note: these prove single-process TX serialization only, not multi-host safety.');
