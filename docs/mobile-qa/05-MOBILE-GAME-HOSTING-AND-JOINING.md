Mobile Game Hosting and Joining

Publication status

Provisional tutorials pending validation against the actual XYZ.HUB build.

Control names describe intended functions, not verified interface labels.

Do not publish unsupported room codes, invite links, game modes, player limits, or host-transfer features.

Member grant: Pending — not independently verified.

Host a game on iPhone or Android

Open the approved Discord conversation or voice channel.

Launch the verified XYZ.HUB Activity.

Complete sign-in if requested.

Open the intended game-selection view.

Select a game that is actually available in the build.

Select the control that creates a game session.

Review the available settings; do not promise settings the build does not expose.

Confirm creation once and wait for the lobby.

Use the build's verified invite/join method.

Confirm that participants appear in the same lobby.

Start only when the game's actual readiness requirements are satisfied.

For voice-call Activities, Discord documents joining the same voice channel and joining the host's Activity. Each first-time participant may need individual authorization.

<a href="https://support.discord.com/hc/en-us/articles/21334461140375-Using-Apps-on-Discord">

support.discord

</a>

Join a host's game

Confirm the host's approved Discord destination.

Join the existing Activity through Discord's available join control.

Complete your own authorization if prompted.

If XYZ.HUB presents a separate room-selection step, follow the host's verified instructions.

Check the displayed host/session identity before joining.

Wait for the lobby to confirm your participation.

Use the game's actual Ready action if one exists.

Do not assume that launching a second Activity automatically joins the host's room.

Hosting is not backend administration

Creating a game session must not be described as:

Deploying a server.

Opening phone ports.

Supplying a bot token.

Granting server administration.

Running the game's authoritative backend on the phone.

This pack does not establish XYZ.HUB's networking architecture.

Failure and recovery copy

Room is full

“This game is full. Ask the host about another session.”

Do not claim a queue or spectator mode exists unless tested.

Room has ended or cannot be found

“This session is no longer available. Ask the host for the current join instructions.”

Different session opened

“You may be in a different session. Return to the host's Activity and check the session identity.”

Connection interrupted

“Connection interrupted. Wait for the reconnect result before joining again.”

Show a clear failure or exit option if reconnection cannot complete.

Host leaves

“The host has left.”

Follow the implemented behavior: end the session, pause, or transfer hosting. Do not promise automatic host transfer until verified.

Duplicate action

“Your request is already being processed.”

The implementation should prevent repeated taps from creating duplicate sessions or duplicate participation.

Mobile-specific tutorial notes

Explain whether rotating the phone is optional or required only after testing.

Do not promise background play or uninterrupted reconnection after screen lock.

Warn before actions that leave a current session.

Keep exit and help actions reachable when the keyboard is open.

Explain any audio permission only when the actual feature needs it.

Verification before publication

<button aria-label="Toggle task"></button>

Host creates a session on iPhone.

<button aria-label="Toggle task"></button>

Host creates a session on Android.

<button aria-label="Toggle task"></button>

iPhone user joins Android host.

<button aria-label="Toggle task"></button>

Android user joins iPhone host.

<button aria-label="Toggle task"></button>

Session identity is consistent across devices.

<button aria-label="Toggle task"></button>

Full, ended, unavailable, and duplicate-join states tested.

<button aria-label="Toggle task"></button>

Host departure behavior documented from observation.

<button aria-label="Toggle task"></button>

Tutorial labels match the actual build.
