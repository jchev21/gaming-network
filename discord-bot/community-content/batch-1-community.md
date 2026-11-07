# XYZ.HUB — Batch 1: COMMUNITY

Official X handle: @_xyzhub_.

This file supplies content only. It does not change Discord, permissions,
roles, bot behavior or existing messages.

## Operator publishing notes

Existing destinations:
- #dashboard
- #announcements
- Stage

Preserve their current identities and message history. Do not create replacement
channels or duplicate Rules Accepted or Member roles.

Publishing status:
- READY_TEXT: complete copy with no unresolved fields. Publish only through
  the authorized operator and existing channel permissions.
- FILL_BEFORE_PUBLISHING: resolve every {{PLACEHOLDER}} and confirm the facts.
- CONFIRM_STAGE_SURFACE: copy is prepared, but confirm where the existing
  Stage supports this content. Use an existing associated text destination
  if appropriate; do not assume Stage supports pins or create a duplicate.

Permission expectations below are proposed publishing boundaries, not a claim
that the actual Discord permissions have been inspected or configured.

Confirmed onboarding status supplied for this handoff:
- Rules Accepted exists.
- Restricted #verify-x exists.
- Rules and X sign-in instructions have been published.
- Automatic Member grants remain disabled until backend verification is complete.

No message should describe sign-in, rules acceptance or a screenshot as proof
that Member access was granted.

---

# #dashboard

## community.dashboard.description

Content type: channel description
Destination: #dashboard
Status: READY_TEXT
Permissions expectation: authorized staff maintain navigation; visibility follows
existing server permissions.

Discord copy:

Your XYZ.HUB command dashboard: approved navigation, public game information and community updates. Start with the pinned guide. Feature labels and current permissions—not previews—determine what is available.

## community.dashboard.pin

Content type: pinned navigation message
Destination: #dashboard
Status: READY_TEXT
Permissions expectation: staff-published reference; members use existing access.

Discord copy:

# Your next move starts here

Welcome to **XYZ.HUB**.

Use this dashboard to find the community’s approved destinations without
hunting through every channel.

## Find your direction

- Games: use the approved game-feed links posted here.
- Community updates: read #announcements.
- Events: check the confirmed event notice before joining Stage.
- Learning and research: follow the approved section links and their labels.
- Feedback: use the existing bug and suggestion destinations.

Only destinations confirmed by the team belong in this dashboard.
If a link has not been provided or a feature is unfinished, it should remain
unavailable or clearly labelled—not replaced with a guessed destination.

## Read the labels

AVAILABLE means the team has confirmed the stated feature is available.
It does not override your account, role or game eligibility requirements.

COMING SOON means planned or unfinished. It is not an access promise.

DEMO / CONCEPT means illustrative content, not a real player queue, account,
financial result or completed workflow.

## Check your onboarding status

Read the published rules and use the existing instructions in #verify-x
when that channel is available to your current roles.

Automatic Member grants are currently disabled while backend verification
is completed. Accepting rules or signing in does not, by itself, confirm
that Member access has been assigned.

If your status is unclear, ask an authorized moderator. Never post passwords,
cookies, tokens, private joining instructions or redemption codes.

Official X account: @_xyzhub_.

## community.dashboard.links_template

Content type: navigation link block
Destination: #dashboard
Status: FILL_BEFORE_PUBLISHING
Permissions expectation: staff-maintained links only.

Discord copy:

# Approved destinations

Public game feed:
{{APPROVED_PUBLIC_GAME_FEED_URL}}

Current game instructions:
{{APPROVED_GAME_INSTRUCTIONS_DESTINATION}}

Community calendar:
{{APPROVED_CALENDAR_DESTINATION}}

Education:
{{APPROVED_EDUCATION_DESTINATION}}

Algo Lab:
{{APPROVED_ALGO_LAB_DESTINATION}}

Bug reports:
{{EXISTING_BUGS_CHANNEL_MENTION}}

Suggestions:
{{EXISTING_SUGGESTIONS_CHANNEL_MENTION}}

Last checked by the team: {{ACTUAL_REVIEW_DATE}}

Only retain entries that genuinely exist and have been approved.
Remove unresolved entries before publishing; do not invent URLs.

## community.dashboard.onboarding_status

Content type: operational status notice
Destination: #dashboard
Status: READY_TEXT
Permissions expectation: staff publish and revise when the actual status changes.

Discord copy:

# Member access update

Rules and X sign-in instructions are published.

Automatic Member grants remain disabled until backend verification is complete.

Please follow the existing instructions rather than repeating submissions
or posting private proof in chat. The team will announce any confirmed change
to the access process in #announcements.

This notice does not grant or confirm a role.

---

# #announcements

## community.announcements.description

Content type: channel description
Destination: #announcements
Status: READY_TEXT
Permissions expectation: authorized announcement publishers; readers retain
their existing visibility permissions.

Discord copy:

Official XYZ.HUB updates: confirmed releases, changes, game events and community news. Coming Soon and demo content stay labelled. Only approved notices establish availability, schedules or access requirements.

## community.announcements.pin

Content type: pinned publishing standard
Destination: #announcements
Status: READY_TEXT
Permissions expectation: staff publish official notices; discussion follows
the existing server arrangement.

Discord copy:

# Confirmed updates. Clear expectations.

This is the reference point for official XYZ.HUB announcements.

Each notice should explain:
- What changed or is being announced.
- Whether it is available, Coming Soon or a demo/concept.
- Who can participate under the actual rules.
- Any confirmed timing, including the time zone.
- The approved destination or next step.

A polished preview is not a release.
An announcement is not a permission override.
A submitted report is not a verified fix.
A sign-in is not proof that Member access has been assigned.

Never publish private joining codes, tokens, account secrets or unapproved
personal information.

Official X account: @_xyzhub_.

## community.announcements.release_template

Content type: release or change announcement
Destination: #announcements
Status: FILL_BEFORE_PUBLISHING
Permissions expectation: owner-approved release information.

Discord copy:

# {{CONFIRMED_UPDATE_TITLE}}

Status: {{AVAILABLE_OR_COMING_SOON_OR_DEMO}}

What changed:
{{CONFIRMED_CHANGE_SUMMARY}}

Who this applies to:
{{ACTUAL_AUDIENCE_AND_REQUIREMENTS}}

Where to go:
{{APPROVED_DESTINATION}}

Known limitations:
{{CONFIRMED_LIMITATIONS_OR_NOT_APPLICABLE}}

Effective time, if relevant:
{{CONFIRMED_DATE_TIME_AND_TIME_ZONE_OR_OMIT}}

This notice does not override existing permissions or game eligibility.

Operator note:
Do not select AVAILABLE without verified release information.
Omit unsupported timing rather than estimating it.

## community.announcements.game_event_template

Content type: confirmed game-event announcement
Destination: #announcements
Status: FILL_BEFORE_PUBLISHING
Permissions expectation: authorized host/event approval before publication.

Discord copy:

# {{CONFIRMED_GAME_EVENT_NAME}}

Game / platform:
{{CONFIRMED_GAME_AND_PLATFORM}}

When:
{{CONFIRMED_DATE_TIME_AND_TIME_ZONE}}

Hosted by:
{{APPROVED_PUBLIC_HOST_NAME}}

Entry:
{{CONFIRMED_FCFS_LOTTERY_OR_MANUAL_ENTRY_RULE}}

Eligibility and capacity:
{{ACTUAL_REQUIREMENTS_AND_CAPACITY}}

Public details:
{{APPROVED_PUBLIC_EVENT_OR_LOBBY_DESTINATION}}

Please follow the actual entry process. An announcement does not reserve
a seat, select a lottery winner or make someone an approved host.

Private joining instructions must remain in their authorized destination,
not in this announcement.

## community.announcements.service_notice_template

Content type: maintenance, incident or recovery notice
Destination: #announcements
Status: FILL_BEFORE_PUBLISHING
Permissions expectation: authorized operational communication.

Discord copy:

# {{SERVICE_NOTICE_TITLE}}

Status:
{{INVESTIGATING_OR_LIMITED_SERVICE_OR_RECOVERED}}

Affected experience:
{{CONFIRMED_MEMBER_VISIBLE_IMPACT}}

What members should do:
{{SAFE_ACTION_OR_NO_ACTION_REQUIRED}}

What is not yet confirmed:
{{UNVERIFIED_ITEMS_OR_NOT_APPLICABLE}}

Next update:
{{CONFIRMED_UPDATE_PLAN_WITHOUT_INVENTED_DEADLINE}}

Do not post credentials or repeatedly submit private verification material.
Use the existing approved help route if your account needs individual review.

Operator note:
Use RECOVERED only after the relevant recovery has actually been verified.

---

# Stage

## community.stage.description

Content type: Stage description or existing associated text description
Destination: existing Stage
Status: CONFIRM_STAGE_SURFACE
Permissions expectation: preserve existing visibility, hosting and participation
controls; confirm the actual destination type before publishing.

Discord copy:

XYZ.HUB events and conversations. Check the confirmed event notice for timing, format and participation instructions. Hosts manage speaker order; existing server rules apply. This description does not announce a live session.

## community.stage.pin

Content type: event-information reference
Destination: existing Stage information surface or existing associated text
Status: CONFIRM_STAGE_SURFACE
Permissions expectation: authorized hosts maintain event guidance.

Discord copy:

# Before you join the conversation

Check the current event notice for:
- Confirmed date, time and time zone.
- Topic and format.
- Host and moderator information.
- How participation works.
- Any recording notice or event-specific requirements.

Do not assume an event is live because Stage exists.
Do not assume attendance includes permission to speak.

Follow the host’s instructions and the existing server rules.
Keep private account details and joining codes out of the conversation.

If no event has been confirmed, do not publish a guessed schedule.

## community.stage.schedule_template

Content type: event schedule
Destination: existing Stage information surface or approved announcement
Status: FILL_BEFORE_PUBLISHING
Permissions expectation: host/owner approves schedule and destination.

Discord copy:

# Upcoming on XYZ.HUB Stage

Event:
{{CONFIRMED_EVENT_TITLE}}

Date:
{{CONFIRMED_DATE}}

Time and time zone:
{{CONFIRMED_TIME_AND_TIME_ZONE}}

Format:
{{CONFIRMED_FORMAT}}

Host:
{{APPROVED_PUBLIC_HOST_NAME}}

Participation:
{{ACTUAL_REQUEST_OR_INVITATION_PROCESS}}

Destination:
{{APPROVED_EXISTING_STAGE_DESTINATION}}

Recording status:
{{CONFIRMED_RECORDING_NOTICE}}

Schedule changes will be announced through the approved event notice.

## community.stage.speaker_instructions

Content type: speaker briefing
Destination: existing Stage information surface
Status: CONFIRM_STAGE_SURFACE
Permissions expectation: hosts/moderators apply only permissions they
actually possess; this copy grants none.

Discord copy:

# Speaker briefing

- Read the event topic and current server rules before participating.
- Use the participation process announced by the host.
- If a request-to-speak control is available, follow the host’s guidance.
- Wait until the host invites or recognizes you.
- Keep your contribution relevant and allow others time to speak.
- Avoid interruptions, harassment, private information and promotional spam.
- Follow instructions about microphones and speaker order.
- Do not assume the session is private or being recorded; check the host’s
  actual recording notice before sharing.

An invitation to one session does not create an ongoing speaker, moderator
or Member entitlement.

## community.stage.host_opening_template

Content type: host opening announcement or spoken script
Destination: existing Stage/event surface
Status: FILL_BEFORE_PUBLISHING
Permissions expectation: confirmed host or authorized event publisher.

Discord copy:

Welcome to {{CONFIRMED_EVENT_TITLE}} on XYZ.HUB.

I’m {{APPROVED_PUBLIC_HOST_NAME}}.
Today we’re discussing {{CONFIRMED_TOPIC}}.

Our format is {{CONFIRMED_FORMAT}}.
To participate, {{ACTUAL_PARTICIPATION_INSTRUCTIONS}}.

Please let the recognized speaker finish, keep comments relevant and
follow the server rules. Do not share passwords, tokens, private account
details or joining codes.

Recording notice: {{CONFIRMED_RECORDING_NOTICE}}.

We’ll begin with {{CONFIRMED_OPENING_SEGMENT}}.

## community.stage.host_closing_template

Content type: host closing announcement or spoken script
Destination: existing Stage/event surface
Status: FILL_BEFORE_PUBLISHING
Permissions expectation: confirmed host or authorized event publisher.

Discord copy:

Thanks for joining {{CONFIRMED_EVENT_TITLE}}.

Confirmed follow-up information:
{{APPROVED_RECAP_OR_FOLLOW_UP_DESTINATION_OR_OMIT}}

For future events, watch #announcements.
Official X account: @_xyzhub_.

Any replay, resource or next event will be shared only when approved.
Please do not assume a recording or follow-up session exists.

## community.stage.moderation_template

Content type: moderation reminder
Destination: existing Stage/event surface
Status: CONFIRM_STAGE_SURFACE
Permissions expectation: authorized moderator/host communication only.

Discord copy:

# Conversation reminder

Please stay on topic, let the recognized speaker finish and follow the
server rules.

Do not share private information, account credentials or joining codes.
No harassment, impersonation, scams or repeated promotional interruptions.

The host will explain speaker order and any event-specific limits.
Only authorized moderators may take moderation actions within their
actual permissions.

For a sensitive concern, use the server’s existing approved moderator-contact
route rather than posting private evidence publicly.

---

# Handoff status

Batch 1 content complete.

READY_TEXT means the copy has no unresolved fields; it does not certify
permissions or authorize posting.

Do not publish unresolved templates or assume Stage supports message pins.
No channel, role, permission, bot, verification gate or deployment was changed.

Next file:
xyz-server-content/batch-2-remaining-sections.md
