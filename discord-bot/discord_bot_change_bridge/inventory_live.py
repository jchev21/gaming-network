"""Build GuildInventory from a live discord.Guild — READ ONLY. No mutations."""
from __future__ import annotations

from typing import Any

from .diff import GuildInventory, ChannelSnap, CategorySnap

VIEW_CHANNEL = 1 << 10


def _everyone_view_denied(overwrites: dict, everyone_role: Any) -> bool | None:
    if everyone_role is None:
        return None
    ow = overwrites.get(everyone_role)
    if ow is None:
        eid = getattr(everyone_role, "id", None)
        if eid is not None:
            for target, o in (overwrites or {}).items():
                if getattr(target, "id", None) == eid:
                    ow = o
                    break
    if ow is None:
        return None
    try:
        allow, deny = ow.pair()
        deny_val = int(deny.value) if hasattr(deny, "value") else int(deny)
        allow_val = int(allow.value) if hasattr(allow, "value") else int(allow)
    except Exception:
        return None
    if deny_val & VIEW_CHANNEL:
        return True
    if allow_val & VIEW_CHANNEL:
        return False
    return None



def _visible_to_everyone(channel: Any, everyone_role: Any) -> bool:
    """Use effective View Channel permission. Unknown is private (fail closed).

    Looking only for explicit @everyone denies is unsafe: a channel can be
    hidden by inherited permissions or by the role's base guild permissions.
    discord.py's permissions_for() resolves the effective channel visibility.
    """
    if everyone_role is None:
        return False
    try:
        resolver = getattr(channel, "permissions_for", None)
        if callable(resolver):
            effective = resolver(everyone_role)
            view = getattr(effective, "view_channel", None)
            if isinstance(view, bool):
                return view
    except (TypeError, ValueError, AttributeError):
        pass
    # Synthetic inventory or incomplete SDK context: explicit allow/deny
    # can be inspected, but missing information must never imply "public".
    denied = _everyone_view_denied(getattr(channel, "overwrites", {}) or {}, everyone_role)
    return denied is False


def build_inventory_from_guild(
    guild: Any,
    *,
    protected_channel_ids: frozenset | None = None,
    protected_category_ids: frozenset | None = None,
) -> GuildInventory:
    everyone = getattr(guild, "default_role", None)
    categories = []
    channels = []

    for cat in getattr(guild, "categories", []) or []:
        categories.append(CategorySnap(
            id=int(cat.id), name=str(cat.name),
            private=not _visible_to_everyone(cat, everyone),
        ))

    for ch in getattr(guild, "channels", []) or []:
        if getattr(ch, "type", None) is not None:
            try:
                tname = str(getattr(ch.type, "name", ch.type)).lower()
            except Exception:
                tname = type(ch).__name__.lower()
        else:
            tname = type(ch).__name__.lower()
        if "category" in tname:
            continue
        ctype = "text"
        if "voice" in tname:
            ctype = "voice"
        elif "stage" in tname:
            ctype = "stage"
        elif "forum" in tname:
            ctype = "forum"
        parent = getattr(ch, "category_id", None) or getattr(getattr(ch, "category", None), "id", None)
        topic = str(getattr(ch, "topic", None) or "")
        channels.append(ChannelSnap(
            id=int(ch.id), name=str(ch.name), type=ctype,
            category_id=int(parent) if parent else None, topic=topic,
            private=not _visible_to_everyone(ch, everyone),
        ))

    return GuildInventory(
        guild_id=int(guild.id),
        categories=categories,
        channels=channels,
        protected_channel_ids=protected_channel_ids or frozenset(),
        protected_category_ids=protected_category_ids or frozenset(),
    )
