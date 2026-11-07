Launch XYZ.HUB as a Discord Activity on Mobile

Status

Platform instructions are based on Discord documentation.

XYZ.HUB-specific launch availability remains unverified.

Member grant: Pending — not independently verified.

Launch from a text conversation

Open the approved Discord text channel, DM, or group DM.

Tap the App Launcher beside the message bar.

Select the verified XYZ.HUB application, or search for its approved app name.

Select Launch if the application presents that option.

Review and approve the authorization request only if you trust the application.

Wait for the Activity to load.

Discord documents this mobile App Launcher workflow. Availability in a particular conversation depends on the application's configuration and permitted access; do not promise every context for XYZ.HUB before testing.

support.discord

+1

Launch from a voice call

Join the approved voice channel or start the permitted DM/group call.

Reveal the call controls if they are hidden.

Open the App Launcher in the call.

Select the verified XYZ.HUB application.

Review any first-use authorization request.

Wait for the Activity to load.

Discord documents launching Activities from voice calls. Friends joining a voice-call Activity need to be in the same voice channel and may need to authorize the application individually.

<a href="https://support.discord.com/hc/en-us/articles/21334461140375-Using-Apps-on-Discord">

support.discord

</a>

Join an Activity already in progress

Open the same approved conversation or voice channel as the host.

Find the active Activity's join control.

Join that existing Activity rather than launching an unrelated new session.

Complete your own authorization if prompted.

Confirm the in-app session identity with the host before playing.

The Discord Activity instance and an in-app game room are separate concepts. Whether XYZ.HUB uses one room per Activity, multiple rooms, codes, or another design must be verified.

If XYZ.HUB is missing from the launcher

For members:

Confirm that you are using the approved account and destination.

Search for the approved application name.

Follow any private-testing access instructions supplied by the project.

Report the device, OS version, Discord version, and launch context.

Do not install a similarly named application as a workaround.

For the release owner:

Check that Activities are enabled.

Check the Activity URL mappings.

Check iOS or Android support settings.

Check the intended installation and interaction contexts.

Check the account's actual access to the development/private application.

Discord requires an Activity URL mapping before enabling Activities, and mobile platform support is configured separately in Activities → Settings.

discord

+1

If the Activity opens but remains blank

Close the Activity and reopen it once.

Check whether the phone has a working network connection.

Record the time, launch path, device, Discord version, and any visible error.

Report persistent failures through [SUPPORT_DESTINATION].

The engineering investigation should distinguish loading/proxy errors, SDK initialization errors, authentication errors, and game-service errors. Do not describe all blank screens as OAuth failures.
