# Games + X integration handoff

## Baseline and branch
- Repository: `jchev21/gaming-network`
- User-selected branch: `ai/games-x`
- Verified base: `cce7e9e126f4d05f9369ac18be2a122c87556761`
- The selected branch was at the verified base when inspected. No deployment or production service was touched.

## Files added
- `x-integration/bridge-contracts.mjs`
- `x-integration/bridge-contracts.test.mjs`
- `x-integration/API_CONTRACT.md`
- `x-integration/INTEGRATION.md`
- `x-integration/fixtures/games-x-preview.json`

## Architecture and choices
- Existing lobby state machine and HTTP API remain the source of truth; no parallel lobby API was introduced.
- Added a disabled-by-default X adapter seam. It accepts only validated numeric mention/author IDs, asks an injected server-owned verifier to authenticate the author, deduplicates mention IDs, and stores only explicitly approved, bounded, expiring reply drafts. It does not poll X, make OAuth calls, or post replies.
- Added an allowlisted public lifecycle-event builder for `created`, `ready`, `cancelled`, and `closed`. It intentionally excludes X identities, entry names, waitlists, invitations, private join instructions, ciphertext, and arbitrary lobby fields. It is an interface only; no Discord outbox or webhook delivery is activated.
- Existing JSON `serial()` queue protects mutations within one Node process. It is not a multi-process or multi-instance transactional guarantee.

## Tests and verification
- Added `node x-integration/bridge-contracts.test.mjs` coverage for disabled operation, verified-author checks, mention deduplication, reply approval/expiry/deduplication, and lifecycle payload privacy/idempotency.
- This GitHub editing environment does not provide a shell, Node runtime, npm, or Docker execution. Therefore no tests, syntax checks, or Docker build are claimed as run. See `TEST_RESULTS.txt`.

## Overlap and deployment notes
- Draft PR #12 (`grok/lobby-storage`) proposes SQLite storage but is not merged/wired. Current JSON queue remains single-process only; concurrent deployments require transactional storage before claiming durable race guarantees.
- Draft PR #16 (`grok/public-lobby-feed`) proposes `GET /api/lobbies`. It is not merged, so this handoff documents it as a pending extension and does not add a competing implementation.
- Draft PR #21 (`grok/x-discord-announcements`) proposes an opt-in outbox. It is not merged; this change adds no active enqueue or webhook code and should be adapted to that reviewed outbox if integrated.
- Official X OAuth/API access, approved billing/plan, callback configuration, production origin, and policy review are later deployment prerequisites. None are configured by these changes.
- No Railway deployment, Discord bot changes, X API polling, X posts, or real game-provider integrations were performed.
