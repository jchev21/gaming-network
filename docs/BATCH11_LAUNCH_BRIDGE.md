# Batch 11 — Launch bridge (#68 gate ↔ #80 grant ↔ #79 in-person)

**Status:** Offline package only. **Do not merge, deploy, or enable grants.**  
**Does not claim issue #79 or live two-account tests passed.**

## Why this batch exists

| Piece | PR / issue | Role |
|-------|------------|------|
| Member **grant** (Rules → X → Discord → role add) | #78 / draft **#80** | *Creates* Member after verified identities |
| Member **gate** (host/join) | draft **#68** | *Requires* existing Member on every protected action |
| In-person acceptance | **#79** | Human two-account path (deferred) |
| Activity portal | #67 / Batch 10 | Talk → Activity mappings (owner portal) |

#80 never replaces #68. #68 never grants roles. Production remains safe only while both feature flags stay **false**.

## End-to-end happy path (when owner later enables)

1. User accepts **native Discord Membership Screening** → bot/onboarding may grant **Rules Accepted** (separate flag).
2. User signs in with **X OAuth** (real account; not a typed handle).
3. Same browser session starts **Discord OAuth** (`identify guilds.members.read`).
4. X service verifies via Discord REST: target guild, `pending=false`, **Rules Accepted** role present.
5. X service posts **signed** S2S grant to Hub bot `/internal/member-grant` (`GN_MEMBER_GRANT_ENABLED=true` only after staging).
6. Bot re-checks hierarchy + membership; adds **Member** only; durable success after role observed.
7. User uses **#68** Discord Member gate: OAuth session + **fresh** Member role check on every host/join.
8. Games: first-come / lottery rules unchanged; secret codes stay private.

## Fail-closed matrix (must remain true)

| Scenario | Expected |
|----------|----------|
| X login alone | No Member; #68 denies host/join |
| Discord OAuth without Rules Accepted | Grant denied; gate denied |
| `pending=true` | Denied |
| Wrong guild | Denied |
| Grant HMAC invalid / replay | Denied |
| Discord `add_roles` fails | No success receipt; retryable |
| Member revoked mid-session | #68 next protected call fails |
| Second X bound to same Discord | Conflict / deny |
| Session / state swap | Deny |

## Flag matrix (production defaults)

| Flag | Service | Default | Notes |
|------|---------|---------|-------|
| `GN_MEMBER_GRANT_ENABLED` | bot | **false** | #80 grant path |
| `GN_DISCORD_MEMBER_GATE_ENABLED` | X | **false** | #68 host/join gate |
| `GN_RULES_AUTOGRANT` | bot | **false** | Independent of Member |
| `X_POLL_ENABLED` | X | **false** | No paid polling |
| `CHANGE_BRIDGE_APPLY_ENABLED` | bot | **false** | No live layout apply |

Enable order (owner only, after offline + staging):

1. Portal Activity mappings (Batch 10) if Activity is in scope  
2. Staging secrets sealed (see ISSUE78_RELEASE_CANDIDATE.md)  
3. Two-account grant once on staging with grant flag on **staging only**  
4. Confirm #68 gate accepts granted Member  
5. Production enable is a separate explicit decision  

## Official X handle

- Public-facing handle for fixtures/docs: **@xyzhub** (storage username `xyzhub`)  
- Do not change production `X_HANDLE` without owner verification  

## Related offline suites already green

| Suite | Result |
|-------|--------|
| Batch 5 `tests.test_member_grant_api` | 19/19 |
| Batch 7–8 `member-link-acceptance.test.mjs` | 9/9 |
| Batch 10 Activity portal preflight | PASS structure |
| Batch 11 bridge contract | **8/8** |

## Issue #79 in-person runbook (owner-executed)

See `docs/ISSUE79_IN_PERSON_RUNBOOK.md`. Automation **must not** mark any row PASS.
