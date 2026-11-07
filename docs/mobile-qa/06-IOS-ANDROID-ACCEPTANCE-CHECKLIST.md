iOS and Android Acceptance Checklist

Initial status

All cases: NOT RUN.

No test success is implied by inclusion.

Member-grant availability: PENDING — not independently verified.

Execution rules

Run each applicable case on both iOS and Android.

Allowed results:

PASS: expected result observed with evidence.

FAIL: expected result not met.

BLOCKED: cannot execute; record the dependency.

NOT RUN: no execution evidence.

N/A: owner-approved exclusion with written rationale.

A blank checkbox means NOT RUN, not PASS.

Each execution record must include:

Case ID.

Tester.

Date/time and timezone.

Device and OS version.

Discord version.

Build identifier and environment.

Launch context.

Expected and actual result.

Evidence reference.

Defect reference, if applicable.

Device and environment coverage

<button aria-label="Toggle task"></button>

ENV-01: Supported OS minimums are explicitly defined.

<button aria-label="Toggle task"></button>

ENV-02: Supported Discord client requirements are defined.

<button aria-label="Toggle task"></button>

ENV-03: Compact and large iPhones tested.

<button aria-label="Toggle task"></button>

ENV-04: Android devices with different screen sizes tested.

<button aria-label="Toggle task"></button>

ENV-05: At least one constrained Android device tested.

<button aria-label="Toggle task"></button>

ENV-06: Display cutout/home-indicator configurations covered.

<button aria-label="Toggle task"></button>

ENV-07: Wi-Fi and cellular connections covered.

<button aria-label="Toggle task"></button>

ENV-08: Slow/interrupted network conditions covered.

<button aria-label="Toggle task"></button>

ENV-09: Test and production environments cannot be confused.

<button aria-label="Toggle task"></button>

ENV-10: Test account roles and entitlements are recorded.

Discovery and launch

<button aria-label="Toggle task"></button>

LCH-01: Authorized tester can discover the app.

<button aria-label="Toggle task"></button>

LCH-02: Unauthorized account follows the intended access boundary.

<button aria-label="Toggle task"></button>

LCH-03: Text-channel launch opens the correct build.

<button aria-label="Toggle task"></button>

LCH-04: Voice-channel launch opens the correct build.

<button aria-label="Toggle task"></button>

LCH-05: DM launch works if in scope.

<button aria-label="Toggle task"></button>

LCH-06: Group DM launch works if in scope.

<button aria-label="Toggle task"></button>

LCH-07: Existing Activity join opens the intended instance.

<button aria-label="Toggle task"></button>

LCH-08: Application name and identity are unambiguous.

<button aria-label="Toggle task"></button>

LCH-09: Initial loading ends in success or actionable failure.

<button aria-label="Toggle task"></button>

LCH-10: Closing and relaunching does not create stale sessions.

Discord documents mobile text and voice launch flows; supported contexts must still be verified for this application.

<a href="https://support.discord.com/hc/en-us/articles/21334461140375-Using-Apps-on-Discord">

support.discord

</a>

Authorization and authentication

<button aria-label="Toggle task"></button>

AUT-01: First-time authorization shows expected identity/scopes.

<button aria-label="Toggle task"></button>

AUT-02: Consent acceptance reaches authenticated application state.

<button aria-label="Toggle task"></button>

AUT-03: Consent cancellation is handled without false success.

<button aria-label="Toggle task"></button>

AUT-04: Returning user follows the intended session behavior.

<button aria-label="Toggle task"></button>

AUT-05: Wrong-account path cannot bind unintended membership.

<button aria-label="Toggle task"></button>

AUT-06: Expired/invalid code fails safely.

<button aria-label="Toggle task"></button>

AUT-07: Reused authorization code fails safely.

<button aria-label="Toggle task"></button>

AUT-08: Revoked/invalid session requires appropriate reauthentication.

<button aria-label="Toggle task"></button>

AUT-09: Backend timeout produces a recoverable message.

<button aria-label="Toggle task"></button>

AUT-10: Invalid configuration does not expose secrets.

<button aria-label="Toggle task"></button>

AUT-11: Unsupported/unapproved scope fails clearly.

<button aria-label="Toggle task"></button>

AUT-12: Browser callback validates state/session binding, if used.

<button aria-label="Toggle task"></button>

AUT-13: Repeated taps do not create parallel uncontrolled flows.

<button aria-label="Toggle task"></button>

AUT-14: Authentication is not reported complete before confirmation.

<button aria-label="Toggle task"></button>

AUT-15: Tokens/codes are absent from public logs and analytics.

The authorization, backend token exchange, and SDK authentication stages must be tested separately.

<a href="https://docs.discord.com/developers/activities/building-an-activity">

discord

</a>

Membership and entitlements

<button aria-label="Toggle task"></button>

MEM-01: Signed-in status is distinct from membership status.

<button aria-label="Toggle task"></button>

MEM-02: Pending copy remains visible until verification.

<button aria-label="Toggle task"></button>

MEM-03: UI does not promise a grant merely after consent.

<button aria-label="Toggle task"></button>

MEM-04: Unavailable grant service fails without false confirmation.

<button aria-label="Toggle task"></button>

MEM-05: Duplicate requests do not produce inconsistent grants.

<button aria-label="Toggle task"></button>

MEM-06: Wrong-account grant prevention is tested.

<button aria-label="Toggle task"></button>

MEM-07: Negative and ineligible cases are tested.

<button aria-label="Toggle task"></button>

MEM-08: Removal/revocation behavior matches the approved policy.

<button aria-label="Toggle task"></button>

MEM-09: Independent verifier observes an actual permitted grant.

<button aria-label="Toggle task"></button>

MEM-10: Independent verifier confirms access at the authoritative destination.

MEM-09 and MEM-10 remain BLOCKED until the real entitlement mechanism, permission to test it, and independent evidence are available.

Hosting and joining

<button aria-label="Toggle task"></button>

GAM-01: iOS host creates exactly one session.

<button aria-label="Toggle task"></button>

GAM-02: Android host creates exactly one session.

<button aria-label="Toggle task"></button>

GAM-03: iOS joins Android-hosted session.

<button aria-label="Toggle task"></button>

GAM-04: Android joins iOS-hosted session.

<button aria-label="Toggle task"></button>

GAM-05: Participants see consistent session identity.

<button aria-label="Toggle task"></button>

GAM-06: Concurrent joins preserve player limits.

<button aria-label="Toggle task"></button>

GAM-07: Full-session feedback is accurate.

<button aria-label="Toggle task"></button>

GAM-08: Invalid/expired join input fails clearly, if applicable.

<button aria-label="Toggle task"></button>

GAM-09: Readiness/start rules are enforced server-side.

<button aria-label="Toggle task"></button>

GAM-10: Repeated start actions do not duplicate a match.

<button aria-label="Toggle task"></button>

GAM-11: Late join follows the actual game policy.

<button aria-label="Toggle task"></button>

GAM-12: Host departure follows documented behavior.

<button aria-label="Toggle task"></button>

GAM-13: Participant departure updates remaining clients.

<button aria-label="Toggle task"></button>

GAM-14: Rejoin does not duplicate a participant.

<button aria-label="Toggle task"></button>

GAM-15: End-of-game state is consistent across devices.

<button aria-label="Toggle task"></button>

GAM-16: Unauthorized session access is rejected.

<button aria-label="Toggle task"></button>

GAM-17: All launch-advertised games complete a tested round.

Layout, input, and accessibility

<button aria-label="Toggle task"></button>

UI-01: Safe areas protect important controls.

<button aria-label="Toggle task"></button>

UI-02: Compact portrait has no blocked primary action.

<button aria-label="Toggle task"></button>

UI-03: Large portrait has no broken layout.

<button aria-label="Toggle task"></button>

UI-04: Landscape works or shows an accurate supported-orientation message.

<button aria-label="Toggle task"></button>

UI-05: Keyboard does not hide required fields/actions.

<button aria-label="Toggle task"></button>

UI-06: Long names and long error messages wrap safely.

<button aria-label="Toggle task"></button>

UI-07: Text scaling preserves essential functionality.

<button aria-label="Toggle task"></button>

UI-08: VoiceOver exposes meaningful labels and focus order.

<button aria-label="Toggle task"></button>

UI-09: TalkBack exposes meaningful labels and focus order.

<button aria-label="Toggle task"></button>

UI-10: Status is not conveyed by color alone.

<button aria-label="Toggle task"></button>

UI-11: Touch controls are usable without hover.

<button aria-label="Toggle task"></button>

UI-12: Reduced-motion preference is respected where applicable.

<button aria-label="Toggle task"></button>

UI-13: Loading and modal states do not trap focus.

<button aria-label="Toggle task"></button>

UI-14: Back/close behavior is safe and understandable.

<button aria-label="Toggle task"></button>

UI-15: Audio controls match actual functionality.

Discord documents mobile safe-area handling; it also exposes thermal-state updates for adaptive behavior, with Android availability described for Android 10 and higher.

<a href="https://docs.discord.com/developers/activities/development-guides/mobile">

discord

</a>

Lifecycle and resilience

<button aria-label="Toggle task"></button>

RES-01: App switch and return preserve or clearly end the session.

<button aria-label="Toggle task"></button>

RES-02: Screen lock and unlock produce an accurate state.

<button aria-label="Toggle task"></button>

RES-03: Incoming-call interruption is handled.

<button aria-label="Toggle task"></button>

RES-04: Wi-Fi/cellular transition avoids silent divergence.

<button aria-label="Toggle task"></button>

RES-05: Temporary disconnect reconnects or fails clearly.

<button aria-label="Toggle task"></button>

RES-06: Long disconnect does not show a false live session.

<button aria-label="Toggle task"></button>

RES-07: Reconnect resynchronizes authoritative game state.

<button aria-label="Toggle task"></button>

RES-08: Backend error gives a safe retry/exit route.

<button aria-label="Toggle task"></button>

RES-09: Rate limiting does not create retry storms.

<button aria-label="Toggle task"></button>

RES-10: Sustained play meets approved performance targets.

<button aria-label="Toggle task"></button>

RES-11: Low-memory conditions do not corrupt state.

<button aria-label="Toggle task"></button>

RES-12: Thermal behavior is evaluated on supported devices.

<button aria-label="Toggle task"></button>

RES-13: Repeated open/close cycles do not accumulate participants.

Security and privacy

<button aria-label="Toggle task"></button>

SEC-01: Client secret and bot token absent from public assets.

<button aria-label="Toggle task"></button>

SEC-02: Server checks user identity and session authorization.

<button aria-label="Toggle task"></button>

SEC-03: Client-supplied host/role claims are not trusted blindly.

<button aria-label="Toggle task"></button>

SEC-04: Least-privilege OAuth scopes reviewed.

<button aria-label="Toggle task"></button>

SEC-05: Sensitive credentials excluded from telemetry.

<button aria-label="Toggle task"></button>

SEC-06: External destinations are intentional and reviewed.

<button aria-label="Toggle task"></button>

SEC-07: User data collection matches published disclosures.

<button aria-label="Toggle task"></button>

SEC-08: Test evidence is redacted before public use.

<button aria-label="Toggle task"></button>

SEC-09: Error messages do not reveal internal secrets.

<button aria-label="Toggle task"></button>

SEC-10: No general Administrator-permission workaround is required.

Content and release

<button aria-label="Toggle task"></button>

REL-01: Tutorials match observed UI labels.

<button aria-label="Toggle task"></button>

REL-02: Public links are approved and tested.

<button aria-label="Toggle task"></button>

REL-03: All official X references use @_xyzhub_.

<button aria-label="Toggle task"></button>

REL-04: No invented screenshots, videos, or test results.

<button aria-label="Toggle task"></button>

REL-05: No unsupported release date or distribution claim.

<button aria-label="Toggle task"></button>

REL-06: Existing COMMUNITY/server batches are not duplicated.

<button aria-label="Toggle task"></button>

REL-07: Support route and incident owner are assigned.

<button aria-label="Toggle task"></button>

REL-08: Mobile rollback/disable plan is documented.

<button aria-label="Toggle task"></button>

REL-09: Release owner reviews defects and exclusions.

<button aria-label="Toggle task"></button>

REL-10: Independent Member-grant verification is tracked separately.

Proposed release gate

Before enabling a public mobile launch:

All in-scope critical launch, authentication, security, and advertised gameplay cases pass on both platforms.

No unresolved defect prevents access, corrupts identity/session state, or exposes sensitive data.

Any exclusion is approved and reflected in public copy.

Evidence identifies the exact release build.

Distribution/access configuration is verified.

Member grant remains labeled pending unless separately independently verified.

A mobile release may only omit a Member-grant feature if the owner explicitly approves that scope and all public copy accurately states the limitation.
