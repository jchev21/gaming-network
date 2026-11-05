# Member Onboarding Plan — Gaming Network Discord Hub

**Mode:** Preview / planning only. No live role or channel mutations are performed by this package.

**Guild:** Hub.XYZ waitlist (ID `1566290427366080612`) — existing IDs always take precedence over names.

## Goals

1. Give every new member a clear START HERE path.
2. Use least-privilege roles; never silently grant Administrator.
3. Support interest-based access (Gamer, Trader/Learner, Affiliate) without raid exposure.
4. Keep restricted channels (e.g. affiliate-reports) staff-only.
5. Remain idempotent: re-running the planner with the same current state does not schedule deletes or duplicates.

## Role matrix (desired)

| Role | Purpose | Key permissions (desired) | Notes |
|------|---------|---------------------------|-------|
| Guest/New | Default join | view_channel, read_message_history | Limited send until onboarding |
| Member | Accepted rules | send_messages, use_application_commands, reactions | Standard access |
| Gamer | Gaming interest | + connect/speak for voice if used | Self-assign or reaction role |
| Trader/Learner | Education track | Standard member + education channels | Self-assign |
| Affiliate | Program participant | Affiliate channel access | No restricted log access |
| Instructor | Education staff | manage_messages in education | Trusted content creators |
| Moderator | Day-to-day mod | kick, timeout, manage_messages | No Manage Guild / Admin |
| Manager | Program managers | manage_channels (scoped), mod tools | Elevated, still least-privilege |
| Admin | Owners | administrator | Assign sparingly |

## Category / channel access (high level)

- **START HERE** — visible to Guest/New+; welcome & rules readable; announcements typically read-only for members.
- **GAMING** — Member + Gamer (and above).
- **LIVE DASHBOARD** — Member+; promo-codes and giveaways follow partner terms (no auto-redemption claims).
- **EDUCATION** — Member + Trader/Learner (and instructors/staff).
- **AFFILIATES** — Affiliate+ for public affiliate channels; **affiliate-reports** restricted to Manager/Admin/Moderator as decided by owner.
- **COMMUNITY** — Member+.

Exact Discord permission overwrites must be reviewed on the live guild. The planner only proposes structure; it does not push overwrites.

## Safe setup preview instructions

1. Export or manually build a current-state JSON snapshot of categories, channels, and roles (IDs + names). Example shape is documented in `guild_planner.py`.
2. Run offline:

   ```bash
   python launch/guild_planner.py --current path/to/current_snapshot.json --format both --out launch/plan-output
   ```

3. Review the Markdown/JSON plan:
   - `preserve` actions confirm existing IDs are kept.
   - `create` actions list only missing names.
   - `conflict` actions block any apply path until resolved.
4. Do **not** run apply. Apply is a disabled stub. Create missing channels/roles manually in Discord after owner approval, or use a future owner-approved tool.
5. After manual changes, re-export current state and re-run the planner to confirm idempotency (zero new creates for matched names).

## Interest-based onboarding flow (recommended, manual)

1. Member joins → Guest/New.
2. Read #rules → reaction or button → Member.
3. Optional: pick Gamer / Trader/Learner / Affiliate in #roles-and-interests (reaction roles or slash command — implement only with owner approval).
4. Moderators handle support tickets in #support; escalate to Manager/Admin as needed.

## Anti-raid and safety

- Prefer Medium+ verification level.
- Slowmode on #general and high-traffic channels.
- AutoMod for spam/invite floods where available.
- New accounts remain Guest/New until rules acceptance.
- Never grant Administrator via automated onboarding.

## Related files

- `launch/desired_guild_structure.json` — source of truth for names and role intent
- `launch/guild_planner.py` — dry-run planner
- `launch/SECURITY_CHECKLIST.md` — permissions and threat model
- `launch/SMOKE_TESTS.md` — post-setup verification
