# Discord server overhaul plan (#22) — dry-run package

**No live Discord edits from Grok.** Add Event modal timing remains a separate batch.

## Contents
| Path | Purpose |
|------|---------|
| `00_READ_ONLY_INVENTORY.md` | Access limits + known guild ID from logs |
| `01_TARGET_STRUCTURE.md` | Start Here, voice-per-category, Coming Soon |
| `02_PERMISSION_MATRIX.md` | Member vs staff, read-only Coming Soon |
| `03_ROLLBACK.md` | Manifest-scoped rollback rules |
| `discord_bot_guild_plan/` | Idempotent planner library |
| `dry_run_cli.py` | Print plan from empty or JSON snapshot |
| `test_guild_plan.py` | Offline unit tests |

## Quick dry-run
```bash
cd discord-server-plan
python3 -m unittest test_guild_plan.py -v
python3 dry_run_cli.py --guild-id 1566290427366080612
```

## After real inventory
1. Owner runs `/channelids` in Discord (Manage Server) or collects `channel_ids.txt`.
2. Convert to `snapshot.json` (`categories`, `channels` maps).
3. Re-run `dry_run_cli.py --snapshot snapshot.json` — creates shrink to true gaps only.
4. Owner approves action list; separate operator applies with bot credentials (not this agent).

## Preserve
Existing channels, messages, roles, bot install, private overwrites, Railway `/data`.
