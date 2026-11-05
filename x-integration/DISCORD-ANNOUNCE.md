# X lobby → Discord announcement bridge

**Branch:** `grok/discord-announcement-bridge`  
**Issue:** #18  
**Status:** Opt-in, off by default. **No live Discord posts. Not deployed.**

## Purpose

When an X-hosted lobby reaches `ready` (or is `cancelled`), optionally post a **public** summary into a configured Discord channel webhook.

## Enable (staging only, never auto)

```bash
export DISCORD_LOBBY_ANNOUNCEMENTS_ENABLED=true
export DISCORD_LOBBY_WEBHOOK_URL='https://discord.com/api/webhooks/<id>/<token>'
export X_PUBLIC_ORIGIN='https://your-x-intake.example'
```

Requirements:

- Dedicated **channel webhook** credential (not the Discord bot token, not X admin token, not join-secret key).
- Webhook URL must match `https://discord.com/api/webhooks/...` (canary/ptb allowed). Arbitrary URLs rejected.
- Valid `X_PUBLIC_ORIGIN` for canonical `/lobby?id=` links.

If any requirement is missing, the bridge stays **disabled** (fail closed).

## Event shape (internal payload)

```json
{
  "event": "ready",
  "lobbyId": "uuid",
  "title": "Squad Up",
  "game": "fortnite",
  "platform": "pc",
  "mode": "first",
  "status": "ready",
  "seats": 4,
  "entryCount": 4,
  "confirmedCount": 4,
  "waitlistCount": 0,
  "host": "@publicHandle-or-null",
  "lobbyUrl": "https://origin/lobby?id=uuid",
  "announcedAt": 1700000000000
}
```

**Never included:** join instructions, passwords, island private codes, OAuth tokens, X numeric user IDs, invite tokens, sessions, ciphertext, mention raw text, redemption codes.

## Idempotency / outbox

- File: `$DATA_DIR/discord-announce-outbox.json` (JSON, single-replica).
- Key: `ready:<lobbyId>` or `cancelled:<lobbyId>`.
- Pending queue + `sent` map → process restart does not re-announce.
- Bounded retries with backoff on 429/5xx; dead-letter after max attempts.
- **Single-process best-effort enqueue deduplication** for pending/sent keys. Multiple replicas are **not supported** by this JSON outbox.
- End-to-end Discord delivery is **at-least-once**, not exactly-once. A crash after webhook 2xx and before the sent marker persists may produce duplicate posts; other outages may cause drops.

Future: SQLite outbox table on the storage branch; do not mix in this PR.

## Integration points

`lobby-api.mjs` dispatches the announcement **only after the lobby JSON save completes** for join→ready or host cancellation. A failed save never emits a webhook. A failed operation also reloads the last durable lobby snapshot so a later request cannot accidentally persist the rejected in-memory mutation. An ungraceful process crash between lobby save and outbox enqueue can still lose the event; fully atomic handling requires a transactional durable outbox.

When the bridge is explicitly enabled, it starts a bounded retry drain (5-second polling interval by default) and attempts a drain of persisted pending events after restart. The retry scheduler coalesces overlapping timer ticks if webhook delivery is slow, rather than building an unbounded backlog of timer-originated drains. When disabled, no background timer is created. On shutdown, call the returned API's `close()` to clear the drain timer. Failures never break the HTTP API.

## Manual setup checklist (later deploy review)

1. Create a Discord channel webhook in the target announcements channel.
2. Store URL only in Railway secrets as `DISCORD_LOBBY_WEBHOOK_URL`.
3. Set `DISCORD_LOBBY_ANNOUNCEMENTS_ENABLED=true` only after staging verification.
4. Confirm `X_PUBLIC_ORIGIN` matches the public site origin.
5. Leave unset/false in production until approved.

## Tests

```bash
cd x-integration
npm test
# Docker build and embedded tests are also run by the X Host Workflow CI.
```

Uses **mock transport only** — never calls Discord. The commit-order regression test injects a failed lobby save and asserts zero announcements; the retry test uses a controlled clock and mock transport. Public title/handle text is stripped of mentions and user-supplied hyperlinks before formatting.
