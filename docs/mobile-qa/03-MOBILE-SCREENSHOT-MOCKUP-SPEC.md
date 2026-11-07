Mobile Screenshot and Mockup Specifications

Deliverable status

This file specifies future assets.

No screenshots, mockups, or videos have been produced or verified.

Member grant: Pending — not independently verified.

Asset types

Real QA capture

Capture from an actual identified build on an identified device.

Record:

Platform and device model.

OS version.

Discord version.

Build identifier and environment.

Capture date.

Test case identifier.

Whether test data was used.

Redactions applied.

Designed mockup

Use the visible label:

“MOCKUP — NOT A LIVE CAPTURE”

Do not imply the image proves:

Working OAuth.

Deployed code.

Public availability.

A successful Member grant.

A working multiplayer session.

Proposed design canvases

These are internal design targets, not claims about a specific device or store requirement.

<table><tr><th>Variant</th><th>Logical canvas</th><th>Purpose</th></tr><tr><td>Compact portrait</td><td>360 × 780</td><td>Narrow-layout stress case</td></tr><tr><td>Standard portrait</td><td>390 × 844</td><td>Primary onboarding layout</td></tr><tr><td>Large portrait</td><td>430 × 932</td><td>Large-screen layout</td></tr><tr><td>Landscape</td><td>844 × 390</td><td>Rotation and short-height layout</td></tr></table>

Real-device screenshots must retain their native capture dimensions. Record the usable Activity viewport separately from the full screenshot.

Required asset list

<table><tr><th>ID</th><th>View</th><th>Required content</th></tr><tr><td>M01</td><td>Entry</td><td>XYZ.HUB identity, approved next action, support route</td></tr><tr><td>M02</td><td>App Launcher</td><td>Verified application identity and launch path</td></tr><tr><td>M03</td><td>Authorization</td><td>Actual permission prompt, or clearly labeled conceptual placeholder</td></tr><tr><td>M04</td><td>Signing in</td><td>Visible progress, non-infinite recovery route</td></tr><tr><td>M05</td><td>Membership status</td><td>Pending notice clearly separated from sign-in status</td></tr><tr><td>M06</td><td>Game selection</td><td>Actual available games only; proposed options labeled as mockup content</td></tr><tr><td>M07</td><td>Host setup</td><td>Intended session settings and create action</td></tr><tr><td>M08</td><td>Lobby</td><td>Host identity, participants, readiness, session identity</td></tr><tr><td>M09</td><td>Join state</td><td>Intended join method and validation feedback</td></tr><tr><td>M10</td><td>Gameplay</td><td>Real tested gameplay or explicitly conceptual mockup</td></tr><tr><td>M11</td><td>OAuth failure</td><td>Plain explanation, retry and close actions</td></tr><tr><td>M12</td><td>Connection interruption</td><td>Reconnecting state and safe exit</td></tr><tr><td>M13</td><td>Permission/access failure</td><td>Explanation without suggesting excessive permissions</td></tr><tr><td>M14</td><td>Compact/landscape</td><td>Reachable actions and readable content</td></tr></table>

Produce iOS and Android variants where native Discord presentation differs.

Layout requirements

Keep essential actions clear of notches, cutouts, home indicators, and Discord controls.

Test visible content with the keyboard open.

Do not rely on hover interactions.

Keep loading, empty, denied, offline, full-room, and expired-room states distinguishable.

Preserve readable text at the supported text-scaling settings.

Do not represent status using color alone.

Proposed internal touch-target goal: at least 48 × 48 logical units; verify on actual devices.

Discord's mobile guidance provides safe-area variables named --discord-safe-area-inset-*, with environment-inset fallbacks. Treat safe-area handling as an implementation and capture requirement.

<a href="https://docs.discord.com/developers/activities/development-guides/mobile">

discord

</a>

Privacy and truthfulness

Redact:

Tokens, authorization codes, secrets, and session cookies.

Private invite links.

Personal email addresses.

Non-consenting users' identities.

Sensitive room codes and internal administrative data.

Do not alter failure captures to make them look successful.

Acceptance

<button aria-label="Toggle task"></button>

Every asset is identified as real capture or mockup.

<button aria-label="Toggle task"></button>

Every real capture includes device/build provenance.

<button aria-label="Toggle task"></button>

Pending Member-grant notice is legible where relevant.

<button aria-label="Toggle task"></button>

No invented games, results, users, or release dates appear as real.

<button aria-label="Toggle task"></button>

iOS and Android differences are accurately represented.

<button aria-label="Toggle task"></button>

Public-use permission and redaction review are complete.
