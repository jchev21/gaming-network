App Tester and Developer Portal Configuration Checklist

Status

Configuration checklist only.

No portal inspection or configuration change has been performed.

Real Member-grant availability: Pending — not independently verified.

Application identity and ownership

<button aria-label="Toggle task"></button>

Confirm the correct existing Discord application.

<button aria-label="Toggle task"></button>

Record the application ID in the internal release record.

<button aria-label="Toggle task"></button>

Confirm authorized team ownership and operator access.

<button aria-label="Toggle task"></button>

Confirm the public name, icon, and description.

<button aria-label="Toggle task"></button>

Confirm development and production identities cannot be confused.

<button aria-label="Toggle task"></button>

Use @_xyzhub_ wherever an official X handle is required.

<button aria-label="Toggle task"></button>

Do not expose secrets in evidence captures.

App Tester access

Portal labels and tester access mechanisms must be checked in the current application. Do not assume that a tester invitation alone grants access to every private Activity.

<button aria-label="Toggle task"></button>

Identify whether the current portal exposes an App Testers control.

<button aria-label="Toggle task"></button>

Record the actual tester mechanism and eligibility rules.

<button aria-label="Toggle task"></button>

Add/invite only approved accounts using the available mechanism.

<button aria-label="Toggle task"></button>

Confirm invitation acceptance where required.

<button aria-label="Toggle task"></button>

Confirm each tester is signed into the invited account.

<button aria-label="Toggle task"></button>

Verify actual launch access; do not infer it from invitation status.

<button aria-label="Toggle task"></button>

Confirm Developer Mode where required for development testing.

<button aria-label="Toggle task"></button>

Test at least one intended non-owner account.

<button aria-label="Toggle task"></button>

Test an account outside the allowed audience.

<button aria-label="Toggle task"></button>

Remove temporary elevated access after testing.

<button aria-label="Toggle task"></button>

Keep tester identifiers private.

Discord's build tutorial states that launching a non-distributed Activity is limited to the developer or members of the developer team. Resolve the actual access rules for the chosen distribution state before relying on non-team testers; do not grant broad team access casually as a workaround.

<a href="https://docs.discord.com/developers/activities/building-an-activity">

discord

</a>

Installation and interaction contexts

<button aria-label="Toggle task"></button>

Decide whether Guild Install, User Install, or both are required.

<button aria-label="Toggle task"></button>

Configure only the intended contexts.

<button aria-label="Toggle task"></button>

Confirm the launch command's intended interaction contexts.

<button aria-label="Toggle task"></button>

Test server text, server voice, DM, and group DM separately where in scope.

<button aria-label="Toggle task"></button>

Verify installation permissions without asking all players for server-management access.

<button aria-label="Toggle task"></button>

Do not equate installation with membership entitlement.

Discord's tutorial recommends both installation contexts for its sample to support launch across servers, DMs, and group DMs. Server installation requires an appropriately authorized server member; ordinary participants should not be told to obtain administrative access merely to play.

<a href="https://docs.discord.com/developers/activities/building-an-activity">

discord

</a>

Activity settings

<button aria-label="Toggle task"></button>

Configure the Activity URL mapping.

<button aria-label="Toggle task"></button>

Enable Activities.

<button aria-label="Toggle task"></button>

Enable iOS support.

<button aria-label="Toggle task"></button>

Enable Android support.

<button aria-label="Toggle task"></button>

Preserve intended web support.

<button aria-label="Toggle task"></button>

Save changes and record the configuration.

<button aria-label="Toggle task"></button>

Verify actual mobile launch after saving.

A URL mapping is required before Activities can be enabled. Mobile platform checkboxes are configured under Activities → Settings.

discord

+1

Entry Point command

<button aria-label="Toggle task"></button>

Confirm the intended Launch Entry Point exists.

<button aria-label="Toggle task"></button>

Confirm its handler matches the implementation.

<button aria-label="Toggle task"></button>

Confirm supported contexts.

<button aria-label="Toggle task"></button>

Check launcher behavior using each tester account.

<button aria-label="Toggle task"></button>

Verify that a launch opens the correct environment.

Discord creates a default Launch Entry Point when Activities are enabled; customized handlers must be reviewed rather than assumed to behave like the default.

discord

+1

URL mappings and services

<button aria-label="Toggle task"></button>

Root mapping serves the intended frontend.

<button aria-label="Toggle task"></button>

Backend and external-resource routes work through the intended Activity proxy setup.

<button aria-label="Toggle task"></button>

Production mappings do not point to an expired development tunnel.

<button aria-label="Toggle task"></button>

Referenced services are reachable from real iOS and Android Discord clients.

<button aria-label="Toggle task"></button>

Mapping changes do not accidentally cross environments.

<button aria-label="Toggle task"></button>

Loading, authentication, and gameplay failures can be distinguished.

<button aria-label="Toggle task"></button>

Record sanitized mapping evidence.

Activities use Discord's sandbox/proxy model, and Discord's tutorial requires URL mapping for serving the app and making external requests.

<a href="https://docs.discord.com/developers/activities/building-an-activity">

discord

</a>

OAuth and credentials

<button aria-label="Toggle task"></button>

Frontend application ID matches the backend configuration.

<button aria-label="Toggle task"></button>

Client secret exists only in the secure backend environment.

<button aria-label="Toggle task"></button>

Bot token, if needed, remains private.

<button aria-label="Toggle task"></button>

Requested scopes are necessary and approved.

<button aria-label="Toggle task"></button>

Token exchange uses the expected request encoding.

<button aria-label="Toggle task"></button>

Embedded SDK flow and external browser flow are documented separately.

<button aria-label="Toggle task"></button>

Browser redirect URIs exactly match registered values where used.

<button aria-label="Toggle task"></button>

Browser flow validates state/session binding where applicable.

<button aria-label="Toggle task"></button>

Token expiration/revocation behavior is tested.

<button aria-label="Toggle task"></button>

Logs exclude tokens, codes, and secrets.

Discord's OAuth token endpoint accepts form-encoded requests. Its embedded tutorial uses backend code exchange and a special placeholder redirect setup for that embedded-only example; this is not a universal production callback URL.

discord

+1

Real Member-grant integration

<button aria-label="Toggle task"></button>

Define exactly what “Member” means.

<button aria-label="Toggle task"></button>

Identify the authoritative entitlement destination.

<button aria-label="Toggle task"></button>

Identify which service is responsible for granting it.

<button aria-label="Toggle task"></button>

Verify the required permissions and eligibility policy.

<button aria-label="Toggle task"></button>

If it is a Discord role, verify the intended server, role, bot permissions, and role hierarchy in the real setup.

<button aria-label="Toggle task"></button>

Test permitted, denied, duplicate, and removal cases.

<button aria-label="Toggle task"></button>

Independently verify the entitlement and resulting access.

<button aria-label="Toggle task"></button>

Keep availability marked pending until verification completes.

Do not add a guild-join scope or role-management permissions merely because the feature is called “Member.” First establish the actual integration design.

Distribution and public readiness

<button aria-label="Toggle task"></button>

Determine the application's actual private/public distribution state.

<button aria-label="Toggle task"></button>

Confirm the intended audience can discover or open it.

<button aria-label="Toggle task"></button>

Confirm any applicable platform requirements in the current portal.

<button aria-label="Toggle task"></button>

Verify public entry links using a non-owner account.

<button aria-label="Toggle task"></button>

Do not infer public readiness from a developer's successful launch.

<button aria-label="Toggle task"></button>

Approve the rollback/disable procedure.

<button aria-label="Toggle task"></button>

Publish only the announcement matching the verified release state.

Configuration sign-off

Application ID:

Environment:

Build:

Configuration reviewer:

Mobile QA reviewer:

Tester access verified:

iOS launch evidence:

Android launch evidence:

OAuth evidence:

Distribution evidence:

Member-grant independent evidence: PENDING

Release decision:

Approved limitations:
