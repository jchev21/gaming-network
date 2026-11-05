# Transactional lobby storage (grok/lobby-storage)

Isolated prototype for issue #10. Replaces the single JSON file + process-wide serial queue with SQLite transactions.

## Goals

- Safe simultaneous joins, waitlist entries, cancels, and join-detail writes
- Encrypted joining instructions stored as opaque ciphertext (same AES-GCM helpers)
- One-shot migration from `x-lobbies.json`
- Domain logic stays pure in `game-core.mjs`

## Files

| File | Role |
|------|------|
| `schema.sql` | Tables, indexes, WAL, foreign keys |
| `lobby-store.mjs` | Repository + `storeOps` high-level API |
| `migrate-from-json.mjs` | Import existing JSON into SQLite |
| `lobby-store.test.mjs` | Unit tests (no network, temp DB) |

## Schema overview

- `lobbies` — core lobby row + winners / withdrawn / removed JSON arrays
- `lobby_entries` — (lobby_id, x_id) unique, ordered by join time
- `lobby_waitlist` — FIFO with explicit `position`
- `invites` — hashed invite tokens
- `join_secrets` — sealed ciphertext per lobby
- `schema_meta` — version + migration marker

## Usage (prototype)

```js
import { createLobbyStore, storeOps } from './storage/lobby-store.mjs';

const store = createLobbyStore('/data/x-lobbies.sqlite');
const ops = storeOps(store, {
  joinSecretKey: process.env.X_JOIN_SECRET_KEY,
  now: Date.now,
});

// Example: join
const publicGame = ops.join({
  lobbyId: '…',
  actorXId: '123456',
  displayName: '@player',
});
```

All mutations use `BEGIN IMMEDIATE` so concurrent Node workers (or future multi-replica) serialize at the database.

## Migration

```bash
# From x-integration/ with DATA_DIR pointing at the volume
DATA_DIR=/data node storage/migrate-from-json.mjs
```

- Reads `DATA_DIR/x-lobbies.json`
- Writes `DATA_DIR/x-lobbies.sqlite`
- Sets `schema_meta.migrated_from_json = 1`
- Leaves the JSON file in place as a backup

Safe to re-run; second run is a no-op.

## Tests

```bash
cd x-integration
node storage/lobby-store.test.mjs
```

## Integration notes (for ChatGPT / later PR)

- This branch does **not** rewrite `lobby-api.mjs` yet. The next step is a thin adapter that swaps the JSON `serial()` helper for `storeOps` while keeping the same HTTP surface.
- Do not enable multi-replica until the API is fully on SQLite and Railway volume locking is confirmed.
- Keep `X_JOIN_SECRET_KEY` (≥32 chars) separate from the admin token (per earlier security review).

## Out of scope on this branch

- No Railway deploy
- No changes to Claude or ChatGPT branches
- No production service modifications
- No automatic X posting
