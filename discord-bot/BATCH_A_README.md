# Batch A — Connect the real bot (#66 / PR #71)

**Commit series on** `grok/ai-discord-change-proposals-1106`

## Commands (owner allowlist only)
| Command | Behavior |
|---------|----------|
| `/change-preview` | Parse proposal JSON, live inventory diff, plan hash — **no mutations** |
| `/change-approve` | Bind exact plan hash; short-lived single-use approval |
| `/change-apply` | Apply once if `CHANGE_BRIDGE_APPLY_ENABLED=true` + fresh snapshot |
| `/change-status` | Journal tail |
| `/change-rollback-preview` | Reversible ops only; **no auto-delete** |

## Env
```
CHANGE_BRIDGE_OWNER_IDS=<discord_user_id>   # required; empty = all denied
CHANGE_BRIDGE_GUILD_ID=1566290427366080612
CHANGE_BRIDGE_APPLY_ENABLED=false           # default; owner must enable for live mutates
```

## bot.py wire
```python
try:
    from change_commands import register_change_commands
except Exception as e:
    register_change_commands = None

# after tree = bot.tree
if register_change_commands is not None:
    register_change_commands(tree, config=config, data_dir=DATA_DIR)
```

## Tests
```bash
cd discord-bot
PYTHONPATH=. python3 -m unittest tests.test_change_bridge tests.test_batch_a_commands -v
```

## Safety
- Members / AI / GitHub push cannot approve
- Private channels and protected IDs blocked in diff
- Stale snapshot fails apply
- No mass delete, no role escalation
