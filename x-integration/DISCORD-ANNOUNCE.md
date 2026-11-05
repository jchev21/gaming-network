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
- **Exactly-once enqueue** is guaranteed; end-to-end Discord delivery is at-least-once with dedupe key (Discord may still drop).

Future: SQLite outbox table on the storage branch; do not mix in this PR.

## Integration points

`lobby-api.mjs` calls `maybeAnnounce` after join→ready and after host cancel. Failures never break the HTTP API.

## Manual setup checklist (later deploy review)

1. Create a Discord channel webhook in the target announcements channel.
2. Store URL only in Railway secrets as `DISCORD_LOBBY_WEBHOOK_URL`.
3. Set `DISCORD_LOBBY_ANNOUNCEMENTS_ENABLED=true` only after staging verification.
4. Confirm `X_PUBLIC_ORIGIN` matches the public site origin.
5. Leave unset/false in production until approved.

## Tests

```bash
cd x-integration
node discord-announce.test.mjs
```

Uses **mock transport only** — never calls Discord.
