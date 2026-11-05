# Environment Variable Template — Gaming Network

**No credential values belong in this file or in git.**

Documented names only. Set values in Railway Variables (or local `.env` that is gitignored).

## Required / expected names

| Name | Secret? | Purpose |
|------|---------|---------|
| `DISCORD_TOKEN` | **Yes** | Discord bot token. Rotate if ever exposed. |
| `DATA_DIR` | No | Persistence root. Production: `/data` (Railway volume). |
| `PYTHONUNBUFFERED` | No | Prefer `1` so logs appear promptly. |
| `GAMING_API_URL` | No | Base URL for gaming-network-api (example production host only — confirm current value in Railway). |
| `API_SERVICE_TOKEN` | **Yes** | Shared service token for API auth (Railway reference preferred). |

## Optional / feature flags (do not enable without owner approval)

| Name | Secret? | Purpose |
|------|---------|---------|
| `APPLY_GUILD_CHANGES` | No | Must be unset or not `1` in CI and normal ops. Enables apply stub only when combined with interactive confirmation. |
| X / polling related vars | Varies | X intake remains **disabled** for this task. Do not set or document live X secrets here. |

## Local development (optional)

```bash
# Example shape only — do not commit real values
export DATA_DIR="./data"
export PYTHONUNBUFFERED=1
# export DISCORD_TOKEN=...   # local only, never commit
```

## CI

GitHub Actions for this package run **without** Discord or Railway secrets. Preflight and planner tests are offline.

## Dashboard

The embedded dashboard binds to loopback (`127.0.0.1:8765`). There is no public `PORT` env requirement for external HTTP exposure of the bot service. Do not add a public domain to `discord-hub-bot`.
