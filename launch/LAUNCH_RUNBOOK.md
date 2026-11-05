# Launch Runbook — Gaming Network Discord Hub

Safe, staged rollout. **Hold points** require explicit owner approval before continuing.

## Status labels

- `READY FOR MANUAL SMOKE TEST` — offline checks green; live verification still required
- `BLOCKED` — conflicts or failures must be resolved first
- `NOT VERIFIED` — live path not exercised

## Stage 0 — Offline readiness (no Discord / Railway changes)

1. Checkout branch `ai/launch-readiness` (or the draft PR branch).
2. Run preflight:

   ```bash
   python launch/preflight.py
   ```

3. Run planner (empty current state or your snapshot):

   ```bash
   python launch/guild_planner.py --format both --out launch/plan-output
   ```

4. Run unit tests:

   ```bash
   python -m unittest discover -s launch/tests -v
   ```

5. Confirm compile:

   ```bash
   python -m compileall -q discord-bot launch
   ```

**Hold point A:** Owner reviews plan Markdown, security checklist, and CI results. No deploy yet.

## Stage 1 — Staging verification (existing bot, no public invite expansion)

1. Confirm Railway `discord-hub-bot` is the **existing** service (not a new project).
2. Confirm volume `discord-hub-data` mounted at `/data`.
3. Confirm env names present (values not printed here): `DISCORD_TOKEN`, `DATA_DIR=/data`, `PYTHONUNBUFFERED`, etc.
4. If a new code deploy is approved separately, pin the commit and watch logs for `Hub connected as ...` and guild command sync.
5. Execute `launch/SMOKE_TESTS.md` sections 3–5 with a **test account** (not a public audience).

**Hold point B:** Smoke tests signed off. Dashboard modal (Add Event) must not produce unresolved 10062 errors.

## Stage 2 — Guild structure alignment (manual)

1. Re-run planner against an exported current-state snapshot.
2. Create only the `create`-listed channels/roles **manually** in Discord (or via a future approved tool).
3. Preserve existing IDs; resolve any `conflict` rows first.
4. Apply permission overwrites carefully (see `ONBOARDING_PLAN.md` and `SECURITY_CHECKLIST.md`).
5. Re-run planner to confirm idempotency (no unexpected new creates).

**Hold point C:** Owner confirms restricted channels and role hierarchy.

## Stage 3 — Limited member onboarding

1. Invite a small trusted cohort only.
2. Walk through Guest/New → Member path.
3. Verify interest roles if enabled.
4. Monitor `#support` and `#bug-reports`.

**Hold point D:** Decision to expand invites.

## Stage 4 — Public rollout (owner only)

1. Complete remaining items in `SECURITY_CHECKLIST.md`.
2. Expand invite only after Hold points A–D.
3. Keep X intake disabled unless a dedicated task enables it.
4. Keep dashboard loopback-only; no public domain on the bot service.

## Abort criteria

- Token exposure → rotate immediately (see `ROLLBACK.md`)
- Data corruption on `/data` → restore from backup; do not "fix forward" blindly
- Persistent interaction failures (10062) on critical paths → pause feature use, fix on `fix/discord-dashboard-response`
- Unexpected second bot session → shut down the extra instance

## After launch

- Keep this runbook and `TEST_RESULTS.txt` updated with real outcomes.
- File follow-ups as GitHub issues rather than hot-fixing production without review.
