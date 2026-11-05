# HANDOFF — AI #7 Launch Readiness

**Branch:** `ai/launch-readiness`  
**PR target:** `fix/discord-dashboard-response` (draft only)  
**Base commit:** `81a82378e8056815131f44431df94196b35eb44d`  
**Repository:** `jchev21/gaming-network`

## Deliverables status

| Deliverable | Status | Notes |
|-------------|--------|-------|
| A. Onboarding plan + dry-run guild configurator | **Done** | `launch/desired_guild_structure.json`, `launch/guild_planner.py`, `launch/ONBOARDING_PLAN.md` |
| B. Deployment safety / preflight | **Done** | `launch/preflight.py`, offline checks, owner-action flags for privileged intents |
| C. Automated tests + CI | **Done** | `launch/tests/*`, `.github/workflows/launch-readiness.yml`; existing `discord-dashboard-check.yml` left intact |
| D. Operator launch kit | **Done** | Runbook, security, smoke tests, rollback, env template |
| E. Integration guidance | **Done** | No production mutations; X intake left disabled; frontend repo untouched |

## Files added / changed

### New

- `launch/desired_guild_structure.json`
- `launch/guild_planner.py`
- `launch/preflight.py`
- `launch/README.md`
- `launch/ONBOARDING_PLAN.md`
- `launch/LAUNCH_RUNBOOK.md`
- `launch/SECURITY_CHECKLIST.md`
- `launch/SMOKE_TESTS.md`
- `launch/ROLLBACK.md`
- `launch/ENVIRONMENT_TEMPLATE.md`
- `launch/tests/test_guild_planner.py`
- `launch/tests/test_preflight.py`
- `.github/workflows/launch-readiness.yml`
- `HANDOFF.md`
- `TEST_RESULTS.txt`

### Unchanged (intentionally)

- `discord-bot/bot.py` and all existing bot code
- `.github/workflows/discord-dashboard-check.yml`
- Railway configuration and live env
- Live Discord guild structure
- `ai/games-x` and frontend repo `gaming-network-hub`

## Tests actually run (local)

See `TEST_RESULTS.txt`. Summary:

- `python -m unittest discover -s launch/tests -v` → **15 passed**
- `python launch/guild_planner.py` → dry-run plan generated (`READY_FOR_MANUAL_SMOKE_TEST`)
- `python launch/preflight.py` → expects full repo tree (bot files); CI checkout includes them
- Apply path correctly **refused** without `APPLY_GUILD_CHANGES=1`

## Overall readiness

**READY FOR MANUAL SMOKE TEST**

Offline planner and preflight are ready for a developer with no token. Live Discord interactions, Railway deploy, and guild mutations were **not** performed.

## Owner actions required

1. Review draft PR; do not merge until satisfied.
2. Confirm Discord Developer Portal privileged intents (Message Content, Server Members).
3. Export current guild categories/channels/roles snapshot and re-run planner against it.
4. Execute `launch/SMOKE_TESTS.md`, especially Add Event modal (watch for 10062).
5. Complete `SECURITY_CHECKLIST.md` before expanding public invites.
6. Decide whether/when to manually create any missing channels/roles from the plan.

## Gaps / not in scope

- Live apply of guild changes (intentionally stubbed)
- Authenticated public dashboard API (documented as future work; loopback panel stays private)
- MFP / prop-firm live adapters and Lovable frontend (separate repos/tasks)
- Enabling X intake
- Actual Railway deploy or token rotation

## Next owner step

Open the draft PR, run GitHub Actions on the branch, review plan output against the real guild, then schedule manual smoke tests on the existing bot.
