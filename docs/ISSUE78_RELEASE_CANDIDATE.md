# Issue #78 / PR #80 — Release candidate (Batches 5–9)

**Branch:** `feature/member-grant-s2s-1106`  
**Status:** Review only. **Do not merge, deploy, or enable grants.**

## Offline evidence

| Suite | Result |
|-------|--------|
| `tests.test_member_grant_api` (Batch 5 security blockers) | **19/19 PASS** |
| `member-grant-client.test.mjs` | **9/9 PASS** (prior) |
| `member-link-acceptance.test.mjs` (Batches 7–8) | **9/9 PASS** |
| Docker/CI | Dockerfile runs member-grant unit tests; CI workflow includes them |

## Security fixes (Batch 5)

1. X↔Discord binding written **only after** membership, `pending=false`, Rules Accepted, hierarchy, and role-safety checks.
2. Durable success (`GRANT_CONFIRMED` / `ALREADY_MEMBER`) only after Discord role presence is confirmed — not after mere authorization.
3. Restart-safe journal: nonces, in-flight attempts, idempotency, bindings under `DATA_DIR/member_grant_journal.json`; **fail closed** if unwritable.
4. Failed Discord `add_roles` clears in-flight attempt; retryable without false success.

## Integration (Batch 6)

- `member_grant_wire.attach_member_grant(app, bot, DATA_DIR)` registers `POST /internal/member-grant`
- Dockerfile applies surgical `start_web` insert if missing; preserves all Hub commands/onboarding
- Rate limit 30/min/peer; HMAC required; grants default **OFF**

## Railway sealed variables (never chat)

| Variable | Service | Purpose |
|----------|---------|--------|
| `GN_MEMBER_GRANT_ENABLED` | bot | must stay `false` until staging two-account pass |
| `GN_MEMBER_GRANT_HMAC_SECRET` | bot + X | ≥32 random bytes, shared |
| `GN_MEMBER_GRANT_URL` | X | private URL to bot `/internal/member-grant` |
| `DISCORD_CLIENT_ID` | X | OAuth app |
| `DISCORD_CLIENT_SECRET` | X | OAuth app |
| `DISCORD_CALLBACK_URL` | X | `https://x-game-intake-production.up.railway.app/auth/discord/callback` |
| `DISCORD_RULES_ROLE_ID` | X | Rules Accepted snowflake |
| `DISCORD_MEMBER_ROLE_ID` | X / PR #68 | Member snowflake |
| `DATA_DIR` | bot | `/data` volume for journal |
| `X_POLL_ENABLED` | X | keep `false` |
| `GN_RULES_AUTOGRANT` | bot | independent; keep false until owner chooses |
| `CHANGE_BRIDGE_APPLY_ENABLED` | bot | keep `false` |

## Rollback

1. Set `GN_MEMBER_GRANT_ENABLED=false` (or unset).
2. Remove `GN_MEMBER_GRANT_URL` from X service if needed.
3. Journal file may remain; does not grant roles by itself.
4. No production cursor / paid X poll to undo if never started.

## Unresolved real-account acceptance (NOT claimed passed)

| Check | Status |
|-------|--------|
| Staging two-account Rules → X → Discord → Member once | **Deferred** |
| Role revocation mid-session host/join deny | **Deferred** |
| Production OAuth consent screens | **Deferred** |
| Activity portal `/` + `/sdk` mapping (#67) | **Deferred** — see `ACTIVITY_URL_MAPPING_REMAINING.md` |
| Issue #79 in-person session | **Open** |

## Explicit non-goals honored

- No second bot
- No Member from X login alone
- No merge / deploy / live role grants by this PR
- No paid X polling or automatic X posts
- No real Discord permission modifications authorized by merge alone
