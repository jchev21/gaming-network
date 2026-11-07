OAuth Errors and Recovery

Status

These are proposed XYZ.HUB messages and support procedures.

They are not a record of observed errors or successful tests.

Member grant: Pending — not independently verified.

Keep the stages separate

For an embedded Activity, Discord's example flow:

Initializes the Embedded App SDK.

Requests authorization.

Exchanges the returned code through a backend.

Authenticates the Activity with the resulting access token.

A failure at one stage must not be reported as success at a later stage. The client secret belongs on the backend, not in public frontend code.

<a href="https://docs.discord.com/developers/activities/building-an-activity">

discord

</a>

Proposed error catalog

The identifiers below are internal proposed labels, not official Discord error codes.

<table><tr><th>Internal label</th><th>Member-facing message</th><th>Member recovery</th><th>Engineering investigation</th></tr><tr><td>AUTH-CANCELED</td><td>“Sign-in was canceled. Nothing has been confirmed.”</td><td>Retry when ready; review permissions</td><td>Distinguish explicit cancellation from transport failure</td></tr><tr><td>AUTH-ACCOUNT</td><td>“Check which Discord account you are using.”</td><td>Stop, switch to the intended account, reopen</td><td>Verify identity/session binding</td></tr><tr><td>AUTH-REDIRECT</td><td>“Sign-in could not return to XYZ.HUB.”</td><td>Close and report; do not repeatedly retry</td><td>Check the actual OAuth flow and registered redirect</td></tr><tr><td>AUTH-CODE</td><td>“Your sign-in request could not be completed. Start a new sign-in.”</td><td>Begin a fresh flow</td><td>Investigate invalid, expired, or reused code and exchange parameters</td></tr><tr><td>AUTH-CONFIG</td><td>“Sign-in is temporarily unavailable.”</td><td>Report and wait for a configuration fix</td><td>Check application ID, backend secret, and environment alignment</td></tr><tr><td>AUTH-SCOPE</td><td>“This request asks for permissions that could not be approved.”</td><td>Stop and report unexpected permissions</td><td>Check supported/approved scopes and least-privilege requirements</td></tr><tr><td>AUTH-SESSION</td><td>“Your session is no longer valid. Please sign in again.”</td><td>Reopen the sign-in flow</td><td>Check token/session validation and revocation handling</td></tr><tr><td>AUTH-NETWORK</td><td>“We could not reach the sign-in service.”</td><td>Check connection; retry once</td><td>Check backend reachability, proxy mapping, timeout, and upstream response</td></tr><tr><td>AUTH-RATE</td><td>“Too many requests. Please wait before trying again.”</td><td>Wait as instructed</td><td>Respect retry guidance; prevent repeated requests</td></tr><tr><td>AUTH-SDK</td><td>“XYZ.HUB could not connect to Discord.”</td><td>Close and relaunch once</td><td>Check SDK initialization and client compatibility</td></tr><tr><td>AUTH-STATE</td><td>“This sign-in request could not be verified.”</td><td>Start again from the approved entry point</td><td>For browser redirects, validate request/session binding and state</td></tr><tr><td>MEMBER-PENDING</td><td>“Discord sign-in does not confirm Member access. Member grant remains pending verification.”</td><td>Do not repeat OAuth to force access</td><td>Investigate the separate entitlement workflow</td></tr></table>

OAuth redirect URIs must match the registered flow, token requests use form-encoded bodies, and application contexts must match configured support. Do not diagnose solely from a generic visible error; inspect the sanitized upstream response.

<a href="https://docs.discord.com/developers/topics/oauth2">

discord

</a>

Redirect configuration: important distinction

Discord's embedded-only tutorial registers a placeholder redirect because the SDK handles returning to the Activity. A separate browser-based onboarding flow needs its own correctly registered callback.

Do not copy the embedded tutorial's placeholder into a website callback implementation or assume the two flows are interchangeable.

discord

+1

Member recovery sequence

Read the visible message.

If canceled intentionally, stop or retry when ready.

If the request expired or the session ended, start a fresh sign-in.

If the problem appears network-related, check connectivity and retry once.

If the message indicates configuration or permission problems, stop repeated retries and contact support.

Report membership problems separately from sign-in problems.

Never ask a user to:

Paste a token or authorization code into chat.

Send a Discord password or two-factor authentication code.

Grant Administrator permission as a general sign-in fix.

Disable account security.

Repeatedly authorize to obtain an unverified Member grant.

Support report template

Issue:

Visible message:

Internal error reference, if shown:

Approximate time and timezone:

Device:

OS version:

Discord version:

Launch context: text / voice / DM / group DM

Environment:

Build identifier, if visible:

Was authorization accepted, canceled, or never shown?

Did the Activity return after authorization?

Did the failure occur before or after the lobby?

Redacted screenshot, if available:

Do not include credentials, cookies, tokens, or full callback URLs containing codes.

Proposed logging requirements

Record:

Correlation ID.

Build/environment.

Failing stage.

Sanitized status/error category.

Platform and supported client metadata.

Retry count and timing.

Exclude secrets and bearer credentials. Discord treats client secrets, access tokens, and refresh tokens as sensitive credentials.

<a href="https://docs.discord.com/developers/activities/building-an-activity">

discord

</a>
