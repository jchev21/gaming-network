"""Batch F: safe onboarding content ops — no privileged role grants."""
from __future__ import annotations

ALLOWED_ONBOARDING_CHANNELS = frozenset({
    "welcome", "rules", "how-to-start", "roles-and-interests", "announcements", "support",
})


def is_safe_onboarding_publish(channel_name: str, *, grant_roles: bool = False) -> tuple:
    if grant_roles:
        return False, "role grants are not allowed via change bridge"
    if channel_name.lower() not in ALLOWED_ONBOARDING_CHANNELS:
        return False, f"channel {channel_name!r} not in onboarding allowlist"
    return True, "ok"
