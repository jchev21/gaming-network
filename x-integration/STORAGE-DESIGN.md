# Storage design — X lobby persistence

**Branch:** `grok/lobby-storage`  
**Issue:** #10  
**Status:** Design + SQLite prototype only. No provisioned cloud database. No production cutover.

## 1. Current state (problem)

`lobby-api.mjs` keeps all lobby state in a single JSON file:

- Full rewrite on every mutation (`writeFile` + rename)
- Process-wide `serial()` promise queue
- Works for one Node process on one Railway volume
- **Fails under concurrent writers** (two workers, or crash mid-write)
- No transactional seat allocation → two players can claim the last seat
- Join secrets (AES-GCM ciphertext) live in the same file

Auth sessions live in a separate JSON path (`x-auth-sessions.json`) and are out of scope for the lobby store, but must not be mixed with lobby data.

## 2. Options compared

| Criterion | SQLite on volume (`node:sqlite`) | Railway Postgres |
|-----------|----------------------------------|------------------|
| Transactional seat allocation | Yes (`BEGIN IMMEDIATE`) | Yes |
| Concurrent processes (multi-replica) | **No** — file lock is local | Yes |
| Operational cost | $0 extra (uses existing volume) | Paid service |
| Schema evolution | Migrations as SQL files | Same + managed tooling |
| Backup | Copy `.sqlite` (+ WAL) | Managed snapshots |
| Dependency surface | Built-in Node 22+ | `pg` / driver |
| Fit for current single-replica deploy | **Best** | Overkill until scale |
| Fit for future multi-replica | Unsuitable | **Required** |

### Recommendation

1. **Near term (this prototype):** SQLite on the existing Railway volume.  
   - Matches current single-replica deployment.  
   - Zero new paid services.  
   - `BEGIN IMMEDIATE` serializes writers safely within one host.  
2. **Before enabling multiple replicas or horizontal scale:** migrate to Railway Postgres (or equivalent).  
   - Do **not** claim SQLite is multi-replica safe.  
   - Do **not** provision Postgres in this workstream.

The prototype on this branch implements the SQLite path only.

## 3. Logical schema (target model)

Same domain whether backed by SQLite or Postgres.

### Core lobby entities

| Entity | Keys / constraints | Notes |
|--------|--------------------|-------|
| **lobbies** | `id` PK | status ∈ {open, ready, closed, cancelled}; mode ∈ {first, lottery}; seats 2–8 |
| **lobby_entries** | `(lobby_id, x_id)` PK | Ordered by `joined_at`; unique player per lobby |
| **lobby_waitlist** | `(lobby_id, x_id)` PK + `position` | FIFO; promotion is transactional |
| **invites** | `token_hash` PK | One-time consume; `used_at` null until claimed |
| **join_secrets** | `lobby_id` PK | Opaque AES-GCM blob only; never plaintext |

### Related (not in SQLite prototype yet)

| Entity | Purpose | Current home |
|--------|---------|--------------|
| **auth_sessions** | X OAuth session cookies / tokens | `x-auth-sessions.json` |
| **oauth_states** | PKCE state / code_verifier | ephemeral or session store |
| **pending_mentions** | Moderator queue of X mentions | in-memory / mention helper |

These stay outside the lobby SQLite file so a lobby migration cannot corrupt auth.

### Indexes (SQLite prototype)

- `lobbies(owner_x_id)`, `lobbies(status)`, `lobbies(source_post_id)`
- `lobby_entries(x_id)`
- `lobby_waitlist(lobby_id, position)`
- `invites(post_id)`, `invites(owner_x_id)`

### Idempotency & transaction boundaries

| Operation | Boundary | Idempotency rule |
|-----------|----------|------------------|
| Create lobby from invite | Single TX: validate invite → insert lobby → mark invite used | Invite token hash consumed at most once |
| Join | Single TX: load → domain `joinLobby` → persist | Duplicate `(lobby_id, x_id)` rejected |
| Waitlist | Single TX | Same player cannot re-queue |
| Finalize (first/lottery) | Triggered inside read/write path via pure `finalizeLobby` | Domain ensures at-most-once transition to `ready` |
| Cancel | Single TX: cancel + delete join_secrets | Host-only |
| Replace no-show | Single TX: promote waitlist head | Host-only, first-mode |
| Set join instructions | Single TX | Host-only; ciphertext replace |

### Data retention (proposal)

| Data | Retention |
|------|-----------|
| Open / ready lobbies | Live |
| Closed / cancelled | 30 days, then soft-delete or archive |
| Join secrets | Deleted on cancel; otherwise retained with lobby |
| Used invites | 7 days after `used_at` |
| Auth sessions | Existing TTL in `x-auth` (unchanged) |

Retention jobs are **not** implemented in this prototype.

## 4. Migration plan (JSON → SQLite)

See `storage/migrate-from-json.mjs` and PR #12.

1. **Backup:** copy `x-lobbies.json` off-volume before any cutover.
2. **Dry-run:** run migration against a copy of the JSON in a temp dir; verify row counts.
3. **Migrate:**  
   `DATA_DIR=/data node storage/migrate-from-json.mjs`  
   - Writes `x-lobbies.sqlite`  
   - Sets `schema_meta.migrated_from_json = 1`  
   - Leaves JSON in place
4. **Verify:** spot-check lobby IDs, entry counts, invite hashes, join_secret presence.
5. **Cutover (separate PR):** point `lobby-api` at `storeOps` (feature flag recommended).
6. **Rollback:** stop service → restore JSON path → restart previous code. Delete or ignore `.sqlite`.

**Never** read or print live Railway secrets, session tokens, or production user records during migration development.

## 5. Rollback procedure

| Stage | Action |
|-------|--------|
| Before API wire-up | No-op — production still on JSON |
| After wire-up, bad data | Restore JSON backup; restart JSON-backed binary |
| After wire-up, good data but want SQLite out | Export SQLite → JSON (not yet automated) or restore pre-cutover JSON |

## 6. Concurrency model

- **SQLite path:** one writer at a time via `BEGIN IMMEDIATE`. Safe for multiple Node event-loop tasks and for a single multi-worker process **only if all workers share the same OS process filesystem and respect the lock**. Not safe across hosts.
- **Postgres path (future):** use `SELECT … FOR UPDATE` or equivalent seat-check-in-transaction; connection pool per replica.

## 7. Explicit non-claims

- This prototype does **not** prove production data safety under multi-replica load.
- SQLite is **not** a shared multi-host store.
- No cloud database is provisioned or billed by this workstream.
- Auth session migration is a separate concern.

## 8. Follow-up decisions for ChatGPT / owner

1. Accept SQLite single-replica cutover, or require Postgres design + provision first?
2. Wire `lobby-api` via feature flag on this branch, or a dedicated integration PR?
3. Who owns auth-session persistence redesign?

---

*Prototype implementation: `x-integration/storage/` on `grok/lobby-storage`.*
