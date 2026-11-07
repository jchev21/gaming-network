# Issue #78 — Secure Rules Accepted → X → Discord → Member grant

**Branch:** `feature/member-grant-s2s-1106`  
**Status:** Implementation + offline tests. **Grants default OFF.** No deploy, no live role changes.

## Required onboarding sequence

1. Discord native Membership Screening (`pending: true → false`)
2. **Rules Accepted** role (existing Hub bot / `onboarding_roles.py`)
3. Gated `#verify-x` → **X OAuth** (identity only; never grants Discord roles)
4. **Discord OAuth** (`identify guilds.members.read`) in the same browser session
5. X service verifies via Discord REST: guild `1566290427366080612`, `pending=false`, Rules Accepted role present
6. Only then: X service → Hub bot **signed S2S** `POST /internal/member-grant`
7. Bot re-checks hierarchy, Rules Accepted, binding 1:1, then grants low-privilege **Member**
8. PR #68 Member gate continues to require live Member role on every host/join

## What this is not

- Not a second bot
- Not Member from X login alone
- Not an open public grant endpoint
- Not bot-token sharing with the X service
- Not paid X polling
- Not automatic enablement (`GN_MEMBER_GRANT_ENABLED` defaults false)

## Crypto / anti-replay

| Field | Purpose |
|-------|---------|
| `GN_MEMBER_GRANT_HMAC_SECRET` (≥32 chars) | Shared secret; Railway sealed vars only |
| `X-GN-Timestamp` | ±60s skew window |
| `X-GN-Nonce` | single-use, 5 min TTL |
| `idempotency_key` | `sha256(x_id:discord_id:member-grant-v1)` — safe retries |
| `X-GN-Signature` | HMAC-SHA256 over `ts\nnonce\nidem\ndiscord\nx\nguild` |

## Env (sealed; never chat)

**Hub bot:** `GN_MEMBER_GRANT_ENABLED=false`, `GN_MEMBER_GRANT_HMAC_SECRET`  
**X service:** Discord OAuth client + callback, `DISCORD_RULES_ROLE_ID`, shared HMAC secret, private `GN_MEMBER_GRANT_URL`, `X_POLL_ENABLED=false`

## Offline tests

```
cd discord-bot && python3 -m unittest tests.test_member_grant_api   # 19/19
cd x-integration && node member-grant-client.test.mjs               # 9/9
```

## Wire-in

```python
from member_grant_wire import attach_member_grant
# inside start_web(), after app = web.Application():
# attach_member_grant(app, bot, DATA_DIR)
```

Until wired and enabled, evaluate_grant returns `MEMBER_GRANT_DISABLED`.
