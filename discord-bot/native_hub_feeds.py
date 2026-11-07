"""Privacy-minimal public feed formatting for native Discord hub components.

This module deliberately cannot access Discord bot tokens or private channels.
Only the existing *public* sanitized lobby fields are admitted.
"""
import re

VALID_MODES = {"first", "lottery"}
VALID_STATUS = {"open", "ready", "closed", "cancelled"}
LOBBY_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
SAFE_TEXT = re.compile(r"[^\w .,+:/()-]", re.UNICODE)
PUBLIC_ORIGIN = "https://x-game-intake-production.up.railway.app"


def safe_text(value, limit=90):
    if not isinstance(value, str):
        return ""
    # Strip Markdown control characters, angle brackets, mentions and URLs
    # from the human-visible title rather than copying user-controlled markup.
    return SAFE_TEXT.sub("", value).strip()[:limit]


def public_lobby_lines(data):
    """Emit bounded, sanitized *public* lobby summaries or an honest status."""
    if not isinstance(data, dict) or data.get("source") != "live":
        return "Public X game feed unavailable. No demo lobbies substituted."
    raw = data.get("games")
    if not isinstance(raw, list):
        return "Public X game feed unavailable. No demo lobbies substituted."
    lines = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        lid = item.get("id")
        name = safe_text(item.get("title"))
        mode = item.get("mode")
        status = item.get("status")
        if not isinstance(lid, str) or not LOBBY_ID.fullmatch(lid) or not name or mode not in VALID_MODES or status not in VALID_STATUS:
            continue
        try:
            seats = item.get("seats")
            confirmed = item.get("confirmedCount")
            if type(seats) is not int or type(confirmed) is not int or not (2 <= seats <= 100 and 0 <= confirmed <= seats):
                continue
        except (ValueError, TypeError):
            continue
        # Rebuild trusted destination from validated UUID, never a supplied URL.
        link = f"{PUBLIC_ORIGIN}/lobby?id={lid.lower()}"
        lines.append(f"• **{name}** — {status} · {confirmed}/{seats} seats · [Details]({link})")
    return "\n".join(lines) if lines else "No public game lobbies are currently available."
