"""Human-readable Gaming Network onboarding guidance.

Rules acceptance is enforced by Discord native Community Rules Screening,
NOT by this helper or any local website checkbox. X authentication proves
only the X identity; automatic Discord role assignment requires a separate
verified Discord+X dual-identity linking service.
"""
from urllib.parse import urlparse, parse_qs

X_OAUTH_ENTRY = "https://x-game-intake-production.up.railway.app/auth/x/start?next=%2Fmy-games"

COMMUNITY_RULES = (
    "Be respectful. No harassment, hate, threats or bullying.",
    "No scams, spam, phishing links or unsolicited promotional DMs.",
    "No cheating, stolen accounts, exploits or unauthorized redemption codes.",
    "Never post private game codes, passwords, tokens or personal information.",
    "Use the appropriate channels and follow Discord/X rules and age requirements.",
    "Only moderators can confirm events, rewards or giveaways. No prizes are guaranteed.",
    "Follow moderator instructions and report suspicious activity privately.",
)

def validate_oauth_entry(url=X_OAUTH_ENTRY):
    """Check that the public instructions point to the approved login endpoint."""
    value = urlparse(url)
    return (
        value.scheme == "https"
        and value.netloc == "x-game-intake-production.up.railway.app"
        and value.path == "/auth/x/start"
        and value.username is None
        and value.password is None
        and value.fragment == ""
        and parse_qs(value.query) == {"next": ["/my-games"]}
    )

def public_onboarding_instructions():
    """No custom code, invite, account identifier or secret may appear here."""
    return (
        "**Gaming Network — Start Here**\n"
        "1. Read and accept the **Discord Rules Screening** prompt displayed when you join. "
        "This is required before chatting.\n"
        "2. Use the button to sign in to your X account on the official Gaming Network X service. "
        "Never share your X password or OTP with a moderator or bot.\n"
        "3. **X sign-in and Discord account linking are separate steps.** "
        "X login alone does not give you any Discord role. "
        "A moderator will announce when automatic X Verified linking is available.\n"
        "4. For tonight's friends-and-family preview, explore approved community channels; "
        "games requiring verified X account links remain supervised or coming soon.\n"
        "5. Report any role/access issues to a moderator. Do not post private codes in chat."
    )
