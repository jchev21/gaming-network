# Batch 2 — Host/player authorization, public feed privacy, live-test runbook

**Deliverable type:** Operator runbook + verification notes (no production code change required for the checklist itself).

## Source inspection (read-only)
- `x-integration/public-feed.mjs` + `PUBLIC-FEED.md` on `launch/public-lobby-feed-integration` @ `68c36414…`
  - Public index is deliberately count-only; strips identities and secrets.
- `x-integration/MODERATION.md`
  - Moderator gate is numeric `X_MODERATOR_USER_ID`; invitations bound to original mention author.
- Existing offline coverage: `public-feed.test.mjs`, `lobby-api.test.mjs`, `moderation.test.mjs`, two-account flow tests on related branches (PR #39 etc.). These are **not** live human acceptance.

## Gaps / human-only
All authorization and privacy claims for real X accounts remain open until the runbook steps are executed and recorded under #17.

## Files
- `LIVE_TEST_RUNBOOK.md` — the checklist
- This MANIFEST

## Next after Batch 2
Remaining unchecked sections from #2 / #17 in order, still excluding paid X polling and frontend onboarding.
