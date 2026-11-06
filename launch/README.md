# Launch Readiness Kit

Offline-first tools and operator documentation for the Gaming Network Discord Hub.

## Quick start (no token required)

```bash
# Preflight — layout, intents, env names, schema
python launch/preflight.py

# Dry-run guild structure plan
python launch/guild_planner.py --format both --out launch/plan-output

# Unit tests
python -m unittest discover -s launch/tests -v
```

## Contents

| Path | Purpose |
|------|---------|
| `desired_guild_structure.json` | Desired categories, channels, roles |
| `guild_planner.py` | Idempotent dry-run planner (JSON + Markdown) |
| `preflight.py` | Offline launch preflight CLI |
| `tests/` | Unit tests (no network, no credentials) |
| `ONBOARDING_PLAN.md` | Roles/channels matrix and setup preview |
| `LAUNCH_RUNBOOK.md` | Staged rollout with hold points |
| `SECURITY_CHECKLIST.md` | Permissions, secrets, anti-raid |
| `SMOKE_TESTS.md` | Manual verification including Add Event modal |
| `ROLLBACK.md` | Data-preserving rollback |
| `ENVIRONMENT_TEMPLATE.md` | Env **names** only |

## Safety rules

- Default is dry-run. Apply is a disabled stub.
- Never mutates live Discord guilds from CI or tests.
- Does not deploy, merge, or change Railway settings.
- Existing channel/role IDs take precedence over names.
- Dashboard remains loopback-only (`127.0.0.1:8765`).

See root `HANDOFF.md` for status and PR details.
