# Smoke Tests — Gaming Network Hub

**All items below are MANUAL.** This package does not run live Discord interactions or create invites.

Mark each result: PASS / FAIL / SKIPPED / BLOCKED.

## Preconditions

- [ ] Bot online on Railway (`Hub connected as ...` in logs)
- [ ] Operator has a test Discord account that is **not** an admin
- [ ] Operator has an admin account for privileged checks
- [ ] Guild is the existing Hub.XYZ waitlist (do not create a second bot or guild)

## 1. Invite and join

| # | Step | Expected | Result |
|---|------|----------|--------|
| 1.1 | Owner generates a temporary invite (manual) | Invite works | |
| 1.2 | Test user joins | Receives Guest/New or default role | |
| 1.3 | Test user can see START HERE channels | Visible per plan | |
| 1.4 | Test user cannot see restricted channels | Denied | |

## 2. Onboarding

| # | Step | Expected | Result |
|---|------|----------|--------|
| 2.1 | Read #rules | Content present | |
| 2.2 | Assign Member (manual or reaction if configured) | Access expands | |
| 2.3 | Optional interest roles (Gamer / Trader/Learner) | Channels unlock as designed | |

## 3. Slash commands (admin + member)

| # | Command / path | Expected | Result |
|---|--------------|----------|--------|
| 3.1 | `/hubpanel` | Ephemeral control panel | |
| 3.2 | `/points` | Ephemeral points card | |
| 3.3 | `/leaderboard` | Leaderboard embed | |
| 3.4 | `/feed` | Feed or empty state | |
| 3.5 | `/dashboard` or hub summary | Summary embed | |
| 3.6 | `/game` (trivia/poll/hunt) | Game prompt without crash | |
| 3.7 | Challenge commands if present (`/challenge_create`, `/challenge_join`) | Host/player flow works or clear error | |

## 4. Dashboard & Add Event modal (critical)

A prior production log showed Discord error **10062 Unknown interaction** on the Add Event modal path. Verify acknowledgment timing.

| # | Step | Expected | Result |
|---|------|----------|--------|
| 4.1 | Open live dashboard message (button UI) | Components respond | |
| 4.2 | Trigger **Add Event** (modal) | Modal appears; interaction acknowledged within 3s | |
| 4.3 | Submit modal with valid data | Event recorded / confirmation | |
| 4.4 | Submit empty / invalid | Graceful validation message | |
| 4.5 | Rapid double-click | No unhandled 10062; defer or lock UI if needed | |

**Fallback if 10062 persists:** Document the exact click path, capture interaction ID/timestamps from logs, and fix acknowledgment (respond/defer immediately) in a follow-up PR on `fix/discord-dashboard-response`. Do not claim this smoke test passed if the modal still times out.

## 5. Roles and permissions

| # | Step | Expected | Result |
|---|------|----------|--------|
| 5.1 | Member cannot run manage_* commands | Permission denied | |
| 5.2 | Moderator can manage messages in scoped channels | Allowed | |
| 5.3 | Guest/New cannot post in Member-only channels | Denied | |
| 5.4 | Affiliate cannot read restricted affiliate-reports | Denied | |

## 6. Codes, giveaways, privacy

| # | Step | Expected | Result |
|---|------|----------|--------|
| 6.1 | `/code-drop` as staff | Code posted with terms reminder | |
| 6.2 | Promo code not auto-redeemed by bot | Bot does not claim redemption authority | |
| 6.3 | Giveaway post + reaction | Message stable; winner selection remains manual | |

## 7. Persistence

| # | Step | Expected | Result |
|---|------|----------|--------|
| 7.1 | Award points, restart bot process | Points still present (volume `/data`) | |
| 7.2 | config.json not overwritten by deploy | Existing config preserved | |

## 8. Negative / safety

| # | Step | Expected | Result |
|---|------|----------|--------|
| 8.1 | Dashboard port not publicly reachable | Connection refused / not exposed | |
| 8.2 | No second bot instance with same token | Only one connected session | |
| 8.3 | X polling remains off | No unexpected X traffic | |

## Sign-off

| Tester | Date | Overall | Notes |
|--------|------|---------|-------|
| | | | |

Status values for handoff: `READY FOR MANUAL SMOKE TEST`, `BLOCKED`, or `NOT VERIFIED`.
