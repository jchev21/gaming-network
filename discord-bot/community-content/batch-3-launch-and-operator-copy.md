# XYZ.HUB — Batch 3: launch announcement and moderator templates

Official handle: **@_xyzhub_**. No part of this document is automatically posted to Discord.

## Announcement — current setup (READY_FOR_OWNER_REVIEW)
> **XYZ.HUB onboarding is being prepared.** Rules are available in #rules. Discord's Rules Accepted role and the restricted #verify-x channel are configured. Automated Member assignment after X + Discord identity linking is still being completed. Game hosting permissions, Activity access and public release dates will be announced only after real-account testing. Never share login credentials or private joining codes.

## Announcement — X verification release (BLOCKED_UNTIL_VERIFIED)
> **X + Discord verification is now available.** Visit the approved #verify-x instructions, sign in using the official XYZ.HUB flow, and verify your Discord identity. The bot assigns Member only after both identities and Rules Accepted status are verified. If you cannot access a feature, use /onboarding-status and contact staff through the approved route.

**Do not publish this second template until server-side role grants are actually deployed, secret/config acceptance is complete, and owner-run issue #79 tests have passed.**

## Announcement — public activity (BLOCKED_UNTIL_VERIFIED)
> **XYZ.HUB Discord Activity is ready for members.** From an eligible voice channel, open Talk → Activity → Hub. Use the live controls to select public feeds and dashboards; any inaccessible channels stay private under Discord permissions.

**Do not publish this as live until the Developer Portal URL mappings and the owner-run D1–D9 Activity tests pass.**

## Game announcement template (FILL_BEFORE_PUBLISHING)
> 🎮 **{{VERIFIED_GAME_TITLE}}** · {{CONFIRMED_PLATFORM}}
>
> Host: {{CONFIRMED_PUBLIC_HOST}}
>
> Format: {{CONFIRMED_FIRST_COME_OR_LOTTERY}}
>
> Open time: {{ACTUAL_START_TIME_AND_ZONE}}
>
> Approved sign-up: {{CONFIRMED_GAME_URL}}
>
> Member and game eligibility rules apply. Never post private codes or joining instructions in public.

## Stage event template (FILL_BEFORE_PUBLISHING)
> 🎙️ **XYZ.HUB Stage — {{CONFIRMED_EVENT_TITLE}}**
>
> Host: {{APPROVED_HOST}}
>
> Date and time: {{CONFIRMED_DATE_TIME_ZONE}}
>
> Audience and speaking rules: {{CONFIRMED_EVENT_RULES}}
>
> Confirmed Stage/event link: {{APPROVED_URL}}
>
> Recording: {{ACTUAL_RECORDING_POLICY}}. Do not assume a recording is made.

## Moderation checklist (READY_FOR_OWNER_REVIEW)
- Apply the existing server rules consistently; neither bots nor AI grant moderator authority.
- Keep private credentials, code-redemption details, Discord tokens, OAuth cookies and financial-account records out of public channels.
- Verify game host/participant eligibility in the backend before sending private joining instructions.
- Forward abuse/security concerns to the existing authorized moderator contact; avoid publicly reposting sensitive evidence.
- Prefer factual status labels: **Available**, **Coming Soon**, **Demo**, or **Temporarily Disabled**.
- Handle mistaken role assignments with the existing Discord role audit and owner instructions, not unreviewed mass changes.
- Preserve existing messages and channel IDs in the overhaul; post each approved pin only once.

## Pinned onboarding walkthrough (READY_FOR_OWNER_REVIEW)
1. Join the XYZ.HUB Discord server.
2. Read #rules and complete native Discord Rules Screening.
3. Use the published acknowledgment control; verify Rules Accepted using `/onboarding-status`.
4. Only when authorized, open the restricted #verify-x instructions. Never share login tokens.
5. Sign in to X through the official approved link; when a verified Discord account-link flow is enabled, finish it in the same protected browser session.
6. Member is not automatically granted just because you completed rules or X sign-in. The secure cross-account grant is pending real-account validation.
7. Use the channels visible to your existing roles; game host/join actions require backend authorization.

## Operator release checks
- [ ] Community/Start Here channel map and any duplicate channel IDs reviewed.
- [ ] Stage channel and events exist before posting schedules.
- [ ] Role visibility and native screening tested with a second account (issue #79, deferred).
- [ ] X OAuth callback/session/Member role grant deployed and verified with two separate accounts (issue #78).
- [ ] Activity Portal / and /sdk mappings and D1–D9 tested in Discord (issue #67).
- [ ] X paid API mention reads remain OFF unless explicitly budget-approved.
- [ ] Exact approved templates and targets signed off before publishing.

**Do not mark unchecked acceptance items as passed just because code builds or demos look finished.**
