# Deferred Discord ↔ X identity linking — security acceptance plan

**Status:** DESIGN ONLY; not deployed, not wired to production. Tracking: [issue #46](https://github.com/jchev21/gaming-network/issues/46). Launch gate: [issue #17](https://github.com/jchev21/gaming-network/issues/17).

## Scope and invariant

Standalone X sign-in proves **only an X session**. It must never be displayed or recorded as Discord verification. An X handle, Discord username, manually entered ID, frontend checkbox or Discord Activity frame identifier is **not** identity proof. Discord Rules Screening and limited invite preview are independent of this deferred feature.

No role changes, Discord OAuth activation, X OAuth changes, polling, posting, or production bot configuration are authorized by this document. Do not enable the linking flow until owner explicitly approves after the friends/family launch gate.

## Proposed fail-closed state machine

`unlinked → discord_authenticated → discord_member_rules_accepted → x_authenticated → bound → role_pending → role_confirmed`

Any missing evidence, expired nonce, mismatched provider subject, revoked authorization, guild mismatch or denied role update must transition to a non-verified state. A successful X login alone never advances beyond `x_authenticated`. UI must distinguish **linked** from **Discord role actually confirmed**. Role assignment must use an allowlisted guild/role ID and the live bot's narrowly scoped permissions, never user-submitted IDs.

## Identity and session trust boundaries

1. Discord provider: verify signed OAuth state and PKCE where supported, fetch immutable user ID from Discord's official authenticated identity endpoint, and check target guild membership and `pending === false` server-side before role grant.
2. X provider: reuse approved server-side PKCE session validation and fetch immutable X user ID; do not trust user-entered handles or session values from query strings.
3. Binding: atomic one-to-one uniqueness constraints on both provider IDs; reject account swaps and pre-existing links unless an authenticated unlink/relink process completes. Keep links in isolated durable storage with a reviewed migration and rollback; never rewrite the live X session database.
4. Use independent high-entropy, single-use, short-lived state/nonce for each provider and binding intent, bound to the initiating session and intended Discord user. Consume atomically; reject replay, concurrent duplicate callback, mismatched origin and cross-user session fixation.
5. Restrict callbacks to exact registered HTTPS origins; set `Secure`, `HttpOnly`, appropriate `SameSite` cookies; CSRF-protect state-changing requests. Never place tokens, cookies, join codes or private identifiers in logs, redirect URLs or public events.
6. Role grant: verify guild ID, membership, rules acceptance, role ID allowlist, bot role hierarchy and Manage Roles at time of action. On failure, return `role_pending` or explicit error, not `verified`. Make retries idempotent and bounded. Unlink must revoke access and role; if revocation fails, alert operator and do not claim successful unlink.
7. Preview remains invite-only with native Discord Rules Screening. Keep X verification disabled and clearly labeled **coming soon** until the full dual-provider security review and real-account acceptance.

## Offline test matrix (not yet executed)

| Case | Mocked input | Expected outcome |
| --- | --- | --- |
| Standalone X login | valid X session, no Discord session | Not Discord-verified; no role call |
| Rules pending | authenticated Discord member with `pending=true` | Deny role; preserve rules gate |
| Wrong Discord account | callback for Discord B during A's link intent | Reject and invalidate intent |
| Wrong X account | X subject differs from pending bound subject | Reject; no role |
| Duplicate X claim | X ID already linked to another Discord ID | Atomic conflict; no role |
| Replay | same callback state used twice | First consumes; second rejected |
| Concurrent callbacks | two claims for same X ID | Exactly one succeeds |
| Expired intent | state older than TTL | Reject |
| Callback tampering | unexpected origin/redirect | Reject |
| Guild mismatch | member in different guild | No role |
| Role escalation | user-supplied role/guild ID | Ignore/reject; allowlist only |
| Bot permission failure | role hierarchy or Manage Roles missing | No verified claim; actionable error |
| Storage restart | process restarted after link | Binding retained, no duplicate grant |
| Unlink and revoke | linked account unlinks | Revoke; verify role removal |
| Revoke failure | Discord API unavailable | Alert, retry safely; don't claim revoked |
| Sensitive data | errors/logs/events | No tokens, private codes or identity secrets |

## Required release evidence (future, gated)

- Offline Node/Python/TypeScript unit + concurrency + restart tests, with exact command, SHA and results.
- Docker build and container runtime tests; no changes to running services.
- Independent security review of OAuth redirect, cookie and identity binding.
- Owner-operated second-account Discord Rules Screening test and two Discord/two X account mismatch tests.
- Explicit owner approval for bot role changes, production OAuth provider setup and deploy; verify Railway health before and after any separately approved deployment.

**This document is not proof of implementation or passing tests.**
