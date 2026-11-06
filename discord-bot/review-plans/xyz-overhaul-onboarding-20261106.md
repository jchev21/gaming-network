# XYZ.HUB — channel overhaul and staged onboarding (owner directive, 2026-11-06)

**Status:** implementation PR #77, no live channel moves and no new roles yet.

## Platform constraint
Discord categories contain channels, not nested categories. "COMMUNITY" is an actual category; its first three **child destinations** are existing public text #dashboard, existing public text #announcements, and a newly approved native Stage channel #stage. Discord may group text and Stage/voice by type; literal nested section headings are not possible.

## Existing public channels to reuse (verified by live guild ID snapshot)

| Destination | Reuse source and channel IDs |
|---|---|
| Gaming Network — Start Here | #start-here 1568331098239537274; #rules 1568085615722111117 |
| COMMUNITY | #dashboard 1567827003414159365 (PERSONAL HUB); #announcements 1567328326169796608 (PERSONAL HUB); #hub 1566290428079374539; #channels 1566984686998261761; #calendar 1567328327524548712; #alerts 1567328333031538879; #giveaways 1567328330917748798; #rewards-and-points 1567328336894492682 |
| GAMES & X | #games-and-events 1567328334298222602 and 1567827004928036964 (two distinct existing channels; preserve both until owner decides consolidation); #codes 1566290771387093152; #promo-codes 1566982323763810305 and 1567328329713852476 (duplicates preserved); #code-drops 1567328335258980433; #gaming-videos 1568331258705219705 |
| ALGO LAB | #algo-lab 1567328368645644501; #algo-lab-videos 1568331311750578396 |
| EDUCATION | Existing #education 1567328365281808435; move #education-videos 1568331344021561465 |
| ALL FIRMS | #payout-reports 1567328370562433074; #scaling-vs-payouts 1567328371929645126. Existing trading channels in a non-public parent are NOT included. |
| FEEDBACK | #suggestions 1567328378690740265 |
| DISCORD STUDIO | #dashboard-videos 1568331283401154580 |
| AFFILIATES & MANAGERS | Keep existing affiliate channels; move #affiliate-help 1567328338232614978 |
| BOT COMMANDS | Keep existing #bot-commands and all current slash commands |
| Voice Channels | Preserve #General, #Test, and existing voice #dashboard; do not confuse with text #dashboard |

**No-delete policy:** Empty PERSONAL HUB / Text Channels / Voice Channels categories are not removed automatically; message histories and existing IDs are preserved. Public channels under a **non-public parent category** are excluded until a separate security/visibility review. `move_channel_async` explicitly passes `sync_permissions=False` to preserve existing channel role overwrites.

## Two-phase channel rollout
1. `/change-layout-preview` creates owner review of missing main public categories. Strict plan hash and fresh inventory digest; apply is disabled by default. Do not duplicate existing Start Here and EDUCATION.
2. After an owner-approved Phase 1, `/change-moves-preview` uses current inventory to propose the next max-18 public channel moves. Approve and apply separately; repeat preview from a **new snapshot** after each approved move batch. `/change-stage-preview` separately proposes native Stage under COMMUNITY only if Discord Community is enabled. No mass role/permission changes, private moves, or destructive operations.

## Native Rules Screening + progressive roles

### Level 0 — @everyone
Read existing #rules and #start-here; native Discord Membership Screening is authoritative.

### Level 1 — Rules Accepted
Only after Discord actually reports `member.pending == False` and Membership Screening is enabled can the bot grant **Rules Accepted** via a persistent acknowledgment button in #rules or an optional guarded `on_member_update` transition. Bot must have Manage Roles and sit above this role. The new #verify-x channel, created only by an **owner-issued** `/onboarding-setup` command, is visible to Rules Accepted; it is explicitly hidden from @everyone. Existing public channel permissions are not silently rewritten.

### Level 2 — Member
After X OAuth sign-in **AND** Discord OAuth proof of the same real Discord guild member, with role check and pending false, a trusted backend may grant Member. **NOT IMPLEMENTED YET:** draft X Member gate PR #68 checks a pre-existing Member role and does not grant it; production lacks Discord OAuth client ID, client secret, redirect URI and role ID. No Member role may be assigned from a self-reported X handle, X login alone, user-submitted JSON, or external site frontend.

### Owner control commands added
- `/onboarding-audit` — read-only preflight; report Rules Screening feature, Manage Roles and role names/IDs and hierarchy.
- `/onboarding-setup` — owner action creates zero-permission Rules Accepted / Member roles if missing and a new restricted #verify-x inside existing Start Here. Stops on missing screening, bot permission, duplicates or privileged Member role.
- `/onboarding-publish` — owner action posts a rules embed with persistent screened-member button and a **clearly labeled** X sign-in link in #verify-x.
- `/onboarding-status` — user-only ephemeral audit of current rules/Member status.
- `GN_RULES_AUTOGRANT` is **false** unless explicitly enabled after role/screening audit. It never grants Member.

## Remaining gates
- Native Community / Membership Screening enabled in Discord settings; confirm with `/onboarding-audit`.
- Bot Manage Roles permission and role hierarchy, confirmed from live audit.
- Owner explicitly executes setup and publishing commands; no automatic posting on Railway deployment.
- Secure cross-service X + Discord account link with server-side verified Member grant; separate PR and tests required.
- Enable X Member game gate PR #68 only after OAuth credentials, Member role ID and two-account tests; X paid polling remains OFF.
- Owner validates one real account through #rules, role assignment, then #verify-x.
