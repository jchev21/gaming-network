# Release candidate (#66 Batches A–J) — NO live guild apply

**Branch:** `grok/ai-discord-change-proposals-1106`  
**PR:** #71  
**Guild:** `1566290427366080612`

## Env
```
CHANGE_BRIDGE_OWNER_IDS=<owner snowflake>
CHANGE_BRIDGE_GUILD_ID=1566290427366080612
CHANGE_BRIDGE_APPLY_ENABLED=false
CHANGE_BRIDGE_OWNER_API_TOKEN=<long random>
DATA_DIR=/data
```

## Commands
`/change-preview` `/change-approve` `/change-apply` `/change-status` `/change-rollback-preview`

## Test procedure (owner)
1. Apply disabled. Preview topic-only proposal on public channel.
2. Approve exact plan hash.
3. Enable apply, apply once, disable apply.
4. Check `/change-status` journal.

## Rollback
Reverse rename/topic/move via new proposal. Creates: manual archive only.

## Limitations
No mass delete, no role escalation, no private exposure. Scheduled worker tick optional. Activity Hub view-only: see ACTIVITY_HUB_INVESTIGATION.md.
