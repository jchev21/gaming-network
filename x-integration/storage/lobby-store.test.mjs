/**
 * Tests for transactional lobby storage.
 * Run: node storage/lobby-store.test.mjs
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createLobbyStore, storeOps, LobbyError } from './lobby-store.mjs';
import { createLobby, joinLobby } from '../game-core.mjs';

const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'gn-lobby-'));
const dbPath = path.join(tmpRoot, 'test.sqlite');
let store;
let ops;
const SECRET = 'test-join-secret-key-at-least-32-chars!!';
let clock = 1_700_000_000_000;

function now() { return clock; }

function setup() {
  if (store) try { store.close(); } catch (_) {}
  if (fs.existsSync(dbPath)) fs.unlinkSync(dbPath);
  for (const s of ['-wal', '-shm']) {
    const p = dbPath + s;
    if (fs.existsSync(p)) fs.unlinkSync(p);
  }
  store = createLobbyStore(dbPath);
  ops = storeOps(store, { joinSecretKey: SECRET, now });
  clock = 1_700_000_000_000;
}

function teardown() {
  try { store?.close(); } catch (_) {}
}

function assertThrows(fn, code) {
  let threw = false;
  try { fn(); } catch (e) {
    threw = true;
    assert.equal(e.code, code, `expected ${code}, got ${e.code}: ${e.message}`);
  }
  assert.ok(threw, `expected LobbyError ${code}`);
}

setup();
{
  const g = createLobby({ game: 'fortnite', title: 'Test Lobby', seats: 3, mode: 'first' }, '111', now());
  store.writeTx((tx) => tx.persistLobby(g));
  const loaded = store.getLobby(g.id);
  assert.equal(loaded.ownerXId, '111');
  assert.equal(loaded.status, 'open');
  assert.equal(loaded.entries.length, 0);

  const pub = ops.join({ lobbyId: g.id, actorXId: '222', displayName: '@alice' });
  assert.equal(pub.entryCount, 1);
  assert.equal(pub.status, 'open');

  ops.join({ lobbyId: g.id, actorXId: '333', displayName: '@bob' });
  const pub2 = ops.join({ lobbyId: g.id, actorXId: '444', displayName: '@carol' });
  assert.equal(pub2.status, 'ready');
  assert.equal(pub2.confirmedCount, 3);
}
console.log('✓ create + concurrent-style joins finalize first-come lobby');

setup();
{
  const g = createLobby({ game: 'warzone', title: 'Dup Test', seats: 4 }, '100', now());
  store.writeTx((tx) => tx.persistLobby(g));
  ops.join({ lobbyId: g.id, actorXId: '200', displayName: '@x' });
  assertThrows(
    () => ops.join({ lobbyId: g.id, actorXId: '200', displayName: '@x' }),
    'DUPLICATE'
  );
}
console.log('✓ duplicate join rejected');

setup();
{
  const g = createLobby({ game: 'fortnite', title: 'Waitlist', seats: 2, mode: 'first' }, '1', now());
  store.writeTx((tx) => tx.persistLobby(g));
  ops.join({ lobbyId: g.id, actorXId: '10', displayName: '@a' });
  ops.join({ lobbyId: g.id, actorXId: '11', displayName: '@b' });
  const pub = ops.waitlist({ lobbyId: g.id, actorXId: '12', displayName: '@c' });
  assert.equal(pub.waitlistCount, 1);
  assert.equal(pub.waitlist[0].name, '@c');
  assert.equal(pub.waitlist[0].position, 1);
}
console.log('✓ waitlist after first-come fills');

setup();
{
  const g = createLobby({ game: 'fortnite', title: 'Cancel', seats: 2 }, '50', now());
  store.writeTx((tx) => tx.persistLobby(g));
  ops.setJoinInstructions({ lobbyId: g.id, actorXId: '50', instructions: 'party code ABC123 join now' });
  const before = ops.getJoinInstructions({ lobbyId: g.id, actorXId: '50' });
  assert.equal(before.instructions, 'party code ABC123 join now');

  ops.cancel({ lobbyId: g.id, actorXId: '50' });
  const after = store.getLobby(g.id);
  assert.equal(after.status, 'cancelled');

  const secretRow = store.db.prepare('SELECT 1 FROM join_secrets WHERE lobby_id = ?').get(g.id);
  assert.equal(secretRow, undefined);
  const hostAfter = ops.getJoinInstructions({ lobbyId: g.id, actorXId: '50' });
  assert.equal(hostAfter.role, 'host');
  assert.equal(hostAfter.instructions, null);
}
console.log('✓ cancel deletes join secrets');

setup();
{
  const g = createLobby({ game: 'fortnite', title: 'Secrets', seats: 2, mode: 'first' }, '7', now());
  store.writeTx((tx) => tx.persistLobby(g));
  ops.join({ lobbyId: g.id, actorXId: '8', displayName: '@p1' });
  ops.join({ lobbyId: g.id, actorXId: '9', displayName: '@p2' });

  ops.setJoinInstructions({ lobbyId: g.id, actorXId: '7', instructions: 'code: SECRET99 region: NA' });

  const hostView = ops.getJoinInstructions({ lobbyId: g.id, actorXId: '7' });
  assert.equal(hostView.role, 'host');
  assert.equal(hostView.instructions, 'code: SECRET99 region: NA');

  const selectedView = ops.getJoinInstructions({ lobbyId: g.id, actorXId: '8' });
  assert.equal(selectedView.role, 'selected');
  assert.equal(selectedView.instructions, 'code: SECRET99 region: NA');

  assertThrows(
    () => ops.getJoinInstructions({ lobbyId: g.id, actorXId: '999' }),
    'NOT_SELECTED'
  );
}
console.log('✓ join instructions gated to host + selected winners');

setup();
{
  const g = createLobby({ game: 'valorant', title: 'Race', seats: 5, mode: 'first' }, '0', now());
  store.writeTx((tx) => tx.persistLobby(g));

  const ids = ['101', '102', '103', '104', '105', '106'];
  for (const id of ids.slice(0, 5)) {
    ops.join({ lobbyId: g.id, actorXId: id, displayName: `@u${id}` });
  }
  assertThrows(
    () => ops.join({ lobbyId: g.id, actorXId: '106', displayName: '@u106' }),
    'CLOSED'
  );
  const final = store.getLobby(g.id);
  assert.equal(final.status, 'ready');
  assert.equal(final.entries.length, 5);
}
console.log('✓ seat capacity enforced under sequential transactional joins');

setup();
{
  const g = createLobby({ game: 'minecraft', title: 'Withdraw', seats: 4 }, '20', now());
  store.writeTx((tx) => tx.persistLobby(g));
  ops.join({ lobbyId: g.id, actorXId: '21', displayName: '@w' });
  ops.withdraw({ lobbyId: g.id, actorXId: '21' });
  const after = store.getLobby(g.id);
  assert.equal(after.entries.length, 0);
  assert.ok(after.withdrawnXIds.includes('21'));
  assertThrows(
    () => ops.join({ lobbyId: g.id, actorXId: '21', displayName: '@w' }),
    'WITHDRAWN'
  );
}
console.log('✓ withdraw prevents re-entry');

setup();
{
  const g = createLobby({ game: 'fortnite', title: 'Replace', seats: 2, mode: 'first' }, '30', now());
  store.writeTx((tx) => tx.persistLobby(g));
  ops.join({ lobbyId: g.id, actorXId: '31', displayName: '@s1' });
  ops.join({ lobbyId: g.id, actorXId: '32', displayName: '@s2' });
  ops.waitlist({ lobbyId: g.id, actorXId: '33', displayName: '@standby' });

  const pub = ops.replaceNoShow({ lobbyId: g.id, actorXId: '30', seat: 0 });
  assert.equal(pub.status, 'ready');
  const loaded = store.getLobby(g.id);
  assert.ok(loaded.removedXIds.includes('31'));
  assert.ok(loaded.winners.includes('33'));
  assert.equal(loaded.waitlist.length, 0);
}
console.log('✓ no-show replace promotes waitlist head');

setup();
{
  const g1 = createLobby({ game: 'poker', title: 'Game A', seats: 2 }, '40', now());
  const g2 = createLobby({ game: 'trivia', title: 'Game B', seats: 2 }, '41', now());
  store.writeTx((tx) => { tx.persistLobby(g1); tx.persistLobby(g2); });
  ops.join({ lobbyId: g1.id, actorXId: '42', displayName: '@viewer' });
  const list = store.listLobbiesForActor('42');
  assert.equal(list.length, 1);
  assert.equal(list[0].id, g1.id);
  const owned = store.listLobbiesForActor('40');
  assert.equal(owned.length, 1);
}
console.log('✓ listLobbiesForActor scopes correctly');

teardown();
try { fs.rmSync(tmpRoot, { recursive: true, force: true }); } catch (_) {}

console.log('\nAll lobby-store tests passed.');
