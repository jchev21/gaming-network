/**
 * Two independent DatabaseSync connections competing for the final seat.
 * This is closer to multi-process contention than sequential storeOps calls.
 * Still single-host / same filesystem — not multi-replica proof.
 *
 * Run: node storage/lobby-store.two-conn.test.mjs
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createLobbyStore, storeOps } from './lobby-store.mjs';
import { createLobby, joinLobby, publicLobby } from '../game-core.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'gn-2conn-'));
const dbPath = path.join(tmpRoot, 'race.sqlite');

const bootstrap = createLobbyStore(dbPath);
const g = createLobby({ game: 'fortnite', title: 'Two Conn Race', seats: 2, mode: 'first' }, '1', Date.now());
bootstrap.writeTx((tx) => tx.persistLobby(g));
const ops = storeOps(bootstrap, { now: () => Date.now() });
ops.join({ lobbyId: g.id, actorXId: '10', displayName: '@first' });
bootstrap.close();

function tryJoin(actorId, name) {
  const store = createLobbyStore(dbPath);
  try {
    return store.writeTx((tx) => {
      const lobby = tx.getLobby(g.id);
      if (!lobby) throw new Error('missing lobby');
      joinLobby(lobby, actorId, name, Date.now());
      tx.persistLobby(lobby);
      return publicLobby(lobby, Date.now());
    });
  } finally {
    store.close();
  }
}

const outcomes = [];
for (const [id, name] of [['20', '@a'], ['21', '@b']]) {
  try {
    outcomes.push({ ok: true, id, result: tryJoin(id, name) });
  } catch (e) {
    outcomes.push({ ok: false, id, code: e.code || e.message });
  }
}

const wins = outcomes.filter((o) => o.ok);
const losses = outcomes.filter((o) => !o.ok);
assert.equal(wins.length, 1, `expected exactly one winner, got ${JSON.stringify(outcomes)}`);
assert.equal(losses.length, 1, `expected exactly one loser, got ${JSON.stringify(outcomes)}`);

const verify = createLobbyStore(dbPath);
const final = verify.getLobby(g.id);
assert.equal(final.entries.length, 2);
assert.equal(final.status, 'ready');
verify.close();

fs.rmSync(tmpRoot, { recursive: true, force: true });
console.log('✓ two independent connections: exactly one final-seat join wins');
console.log('  outcomes:', outcomes.map((o) => o.ok ? `win:${o.id}` : `lose:${o.id}:${o.code}`).join(', '));
