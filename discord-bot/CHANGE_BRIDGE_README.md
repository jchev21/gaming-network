# AI → Discord bot change bridge (#66)

**Branch:** `grok/ai-discord-change-proposals-1106`  
**Baseline:** `fix/discord-dashboard-response`  
**No live guild edits, no merges, no Railway deploys from Grok.**

## Allowed ops (v1)
`create_category` · `create_text_channel` · `rename_channel` · `update_topic` · `move_channel`

**Not allowed:** delete, permission escalation, invites, webhooks, private channel exposure, arbitrary scripts.

## Layout
```
discord-bot/discord_bot_change_bridge/
  schema.py approval.py diff.py journal.py apply.py
discord-bot/tests/test_change_bridge.py
```

## Offline tests
```bash
cd discord-bot
PYTHONPATH=. python3 -m unittest tests.test_change_bridge -v
# 17 tests OK
```

## Flow
1. AI emits proposal JSON (schema 1.0.0) with `snapshot_digest`
2. Preview → `plan_hash` + diff lines + risk flags
3. Owner (allowlisted Discord user id) approves **that exact hash** (TTL ≤ 1h)
4. Bot applies once via injected mutator; journal audits; idempotency token replay is no-op
5. Rollback preview: renames/topics/moves reversible; creates are **not** auto-deleted

ChatGPT owns `/change-preview` slash wiring, live Discord mutator, and production enablement.
