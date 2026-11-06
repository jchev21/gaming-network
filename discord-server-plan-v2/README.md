# Discord guild dry-run planner v2 (#22)

**Independently usable. No live Discord edits.**

## Requirements met
- Explicit `guild_id` required (config + snapshot)
- Channel/category **reuse by explicit numeric id** when inventory provides them
- **Fail closed** on ambiguous name→id mappings (duplicate channel names)
- **Effective member visibility** report from overwrites (view/send/connect) — read-only, no permission changes
- Offline unit tests (13) + CLI

## Usage
```bash
cd discord-server-plan-v2
python3 -m unittest test_guild_plan_v2.py -v
python3 dry_run_cli.py --guild-id 1566290427366080612
python3 dry_run_cli.py --snapshot snapshot.json
```

### snapshot.json shape
```json
{
  "guild_id": 1566290427366080612,
  "everyone_role_id": 1566290427366080612,
  "categories": [{"id": 50, "name": "START HERE"}],
  "channels": [{
    "id": 501,
    "name": "welcome",
    "type": "text",
    "category_id": 50,
    "topic": "",
    "overwrites": [{"id": 1566290427366080612, "type": "role", "allow": 1024, "deny": 0}]
  }]
}
```

Obtain ids via `/channelids` or `channel_ids.txt` from the live bot — not from this agent.

## Prior package
Name-only planner remains on `grok/discord-server-structure-dry-run-22`. Prefer **v2** for apply-quality dry-runs.
