# XYZ.HUB server overhaul — Phase 1 owner review

**Status:** READ-ONLY PROPOSAL. This document and JSON do not change Discord.

## Verified Discord snapshot

- Guild: `Hub.XYZ waitlist`, ID `1566290427366080612`.
- Snapshot digest: `ac90b51f3d592173deff0fd5c19df42b2e191dbcd85e135d48d0ae7365941a68` (all current categories/channels; any change invalidates this proposal).
- Current public categories: **7**; public channels: **39**.
- Private/non-public: **1 category and 1 channel**, names deliberately excluded.
- Bot effective permissions: Manage Channels **true**; Manage Server **false**; Send Messages **true**.
- Server owner ID was obtained from Discord's live guild metadata and allowlisted in Railway, not guessed. No owner ID is stored in this proposal.
- Production env `CHANGE_BRIDGE_APPLY_ENABLED=false`; cannot execute the plan.

### Existing public category names (preserved)

- `AFFILIATES & MANAGERS` (category ID `1567328351385948312`; 4 public channels)
- `BOT COMMANDS` (category ID `1567328373129220106`; 2 public channels)
- `EDUCATION` (category ID `1567328363620733042`; 4 public channels)
- `Gaming Network — Start Here` (category ID `1568330862465122324`; 0 public channels)
- `PERSONAL HUB` (category ID `1567328324454326342`; 10 public channels)
- `Text Channels` (category ID `1566290428079374537`; 5 public channels)
- `Voice Channels` (category ID `1566290428079374538`; 2 public channels)

Visible public channels outside any category: `algo-lab-videos`, `dashboard-videos`, `education-videos`, `gaming-videos`, `rules`, `start-here`, `Test`.

5 otherwise-public channel(s) have a parent category that is not visible to `@everyone`. **Do not relocate these in Phase 1 or Phase 2 until an access review.** No private names or content are included in this file.

## Proposed Phase 1: create six missing PUBLIC categories only

| New public category | Proposed contents for future Phase 2 (no moves yet) |
|---|---|
| COMMUNITY | #hub, #channels, public discussion / announcements |
| GAMES & X | #games-and-events, #gaming-videos, codes and hosted-game information |
| ALGO LAB | #algo-lab, #algo-lab-videos |
| ALL FIRMS | Public firm directory, comparison and information — do not touch private trading records |
| FEEDBACK | #suggestions, public bug reports, support triage |
| DISCORD STUDIO | #dashboard-videos, multiview and activity help |

Keep existing **Gaming Network — Start Here**, **EDUCATION**, **AFFILIATES & MANAGERS**, **BOT COMMANDS**, **PERSONAL HUB**, **Text Channels**, and **Voice Channels**. Do not create a duplicate START HERE.

**Precisely six operations** in `xyz-hub-phase1-categories-20261106.json`; each uses `create_category` and has no channel ID, message, overwrite, deletion, role or external post.

## Phase 2, separate fresh-snapshot approval after Phase 1

Propose to move existing `start-here` and `rules` to **Gaming Network — Start Here**; `hub` and `channels` to **COMMUNITY**; `games-and-events` and `gaming-videos` to **GAMES & X**; `algo-lab` and `algo-lab-videos` to **ALGO LAB**; `education-videos` to **EDUCATION**; `suggestions` to **FEEDBACK**; and `dashboard-videos` to **DISCORD STUDIO**.

**No moves have been applied or approved.** Recheck each destination's public effective permissions before any move, ensure no disruption to bot commands or activity routes, and review duplicate channel names under PERSONAL HUB. Do not remove or merge existing messages.

**Separate access review:** Public effective permissions currently appear to include management-labeled channels under AFFILIATES & MANAGERS. The owner should decide whether those belong in protected/private areas; permission changes are outside this plan and cannot be automated by the current safe operation set.

## How to inspect without changing anything

1. Open Discord `Hub.XYZ waitlist` as the account that **owns the server** (the allowlisted Discord guild owner).
2. In a normal text channel, invoke `/change-preview`. Paste the complete JSON from `discord-bot/review-plans/xyz-hub-phase1-categories-20261106.json` into the `proposal_json` argument.
3. The bot replies **ephemerally** with plan hash, inventory digest, blockers and the six proposed operations. **Do not use `/change-apply`.** Execution remains disabled.
4. If the guild changed or the proposal expired, re-export a new snapshot and regenerate the JSON; never defeat the stale-snapshot guard.
5. Only after the owner reviews this specific plan should a separate approval of any actual change be considered.

No X paid polling, social publishing, new bot, moderation role changes or Discord channel deletions are part of this proposal.
