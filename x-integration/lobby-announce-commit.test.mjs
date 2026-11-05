/** Test that announcements are emitted only after durable lobby persistence. Mock I/O only. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { createLobbyApi } from './lobby-api.mjs';
import { createLobby, joinLobby } from './game-core.mjs';

async function scenario({ failSave }) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'gn-ann-commit-'));
  const origin = 'https://example.test';
  const lobby = createLobby({ game: 'fortnite', title: 'Hosted demo', platform: 'pc', seats: 2, mode: 'first' }, '10001', 1000);
  joinLobby(lobby, '20001', '@first', 1001);
  const dbFile = path.join(dir, 'x-lobbies.json');
  await fs.writeFile(dbFile, JSON.stringify({ invites: {}, lobbies: { [lobby.id]: lobby }, joinSecrets: {} }));
  const calls = [];
  let saveCalls = 0;
  const announceBridgeFactory = () => ({
    config: { enabled: true },
    start() {},
    stop() {},
    notifyLobbyReady: async value => { calls.push({ type: 'ready', status: value.status }); },
    notifyLobbyCancelled: async value => { calls.push({ type: 'cancelled', status: value.status }); },
  });
  const saveState = async (file, state) => {
    saveCalls++;
    if (failSave) throw new Error('injected disk failure');
    await fs.writeFile(file, JSON.stringify(state));
  };
  const auth = { authenticated: req => req.headers['x-test-user'] ? { id: req.headers['x-test-user'], username: 'second' } : null };
  const api = await createLobbyApi({
    dataDir: dir, auth, mentions: { pending: [] }, publicOrigin: origin,
    saveState, announceBridgeFactory, now: () => 1002,
  });
  const server = http.createServer(async (req, res) => {
    if (!(await api.handle(req, res, new URL(req.url, 'http://localhost')))) {
      res.writeHead(404); res.end();
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const response = await fetch(`http://127.0.0.1:${server.address().port}/api/lobbies/${lobby.id}/join`, {
      method: 'POST',
      headers: { origin, 'x-test-user': '20002', 'content-type': 'application/json' },
      body: '{}',
    });
    // Allow asynchronously scheduled mock notifications to finish.
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(response.status, failSave ? 500 : 200);
    assert.equal(saveCalls, 1);
    assert.equal(calls.length, failSave ? 0 : 1, 'No announcement before successful save');
    if (!failSave) {
      assert.deepEqual(calls[0], { type: 'ready', status: 'ready' });
      const stored = JSON.parse(await fs.readFile(dbFile, 'utf8'));
      assert.equal(stored.lobbies[lobby.id].status, 'ready', 'Ready state persisted before notifying');
    }
  } finally {
    api.close?.();
    server.close();
    await fs.rm(dir, { recursive: true, force: true });
  }
}

await scenario({ failSave: true });
await scenario({ failSave: false });
console.log('Announcement commit-order tests passed (mock only).');
