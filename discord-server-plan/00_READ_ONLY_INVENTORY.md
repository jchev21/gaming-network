# Read-only guild inventory status

**Date:** 2026-11-06  
**Issue:** #22  
**Agent access:** **No live Discord API or bot token in this session.**  
Grok cannot enumerate the real guild’s channels, roles, or overwrites from here.

## What is known from prior verified logs (not a live inventory)
| Field | Value | Source |
|-------|--------|--------|
| Observed guild name | `Hub.XYZ waitlist` | Railway `discord-hub-bot` startup logs (issue #17 / #22) |
| Observed guild ID | `1566290427366080612` | Same logs — **configurable**, treat as default only |
| Bot service | `discord-hub-bot` ONLINE | Railway status comments on #17 |
| Commands | ~22–23 guild slash commands synced | Deploy logs |
| Persistent data | `/data` volume (`config.json`, `hub_data.json`) | README-DEPLOY.md |

## Missing access (required for a true inventory)
To produce an authoritative channel/role/permission inventory the **owner or ChatGPT with bot runtime** must run one of:

1. In Discord (Manage Server): `/channelids` (already implemented — ephemeral list of channel IDs).
2. On the Railway bot host: collect `channel_ids.txt` written by `export_channel_ids()` on ready.
3. Export via Discord UI, or a **read-only** audit script using the existing bot token **locally** (never paste the token into GitHub).

Until that dump exists, all apply plans use **configurable IDs** and **name-based matching**, never private channel contents.

## Safety posture
- No live guild edits from Grok.
- No reading of private channel message history.
- No role elevation, token rotation, or Railway variable changes.
- Planner is dry-run by default; apply requires explicit operator action after owner approval.
