"""Effective member visibility — report only, never mutates permissions.

Distinguishes category_overwrite vs channel_overwrite vs effective member view.
"""
from __future__ import annotations

from dataclasses import dataclass

from .snapshot import GuildSnapshot

VIEW_CHANNEL = 1 << 10
SEND_MESSAGES = 1 << 11
CONNECT = 1 << 20


@dataclass(frozen=True)
class ChannelVisibility:
    channel_id: int
    channel_name: str
    channel_type: str
    view: bool | None
    send: bool | None
    connect: bool | None
    source: str
    category_view: bool | None = None
    category_send: bool | None = None
    category_connect: bool | None = None
    channel_view: bool | None = None
    channel_send: bool | None = None
    channel_connect: bool | None = None


@dataclass
class VisibilityReport:
    guild_id: int
    everyone_role_id: int | None
    channels: list

    def member_visible_ids(self) -> list:
        return [c.channel_id for c in self.channels if c.view is True]

    def member_hidden_ids(self) -> list:
        return [c.channel_id for c in self.channels if c.view is False]


def _bits_for(overwrites, everyone_id):
    if everyone_id is None:
        return None
    for ow in overwrites:
        if ow.target_type == "role" and ow.target_id == everyone_id:
            return ow.allow, ow.deny
    return None


def _effective_bool(allow, deny, bit):
    """Report explicit @everyone overwrite only; absent bit is unknown."""
    if deny & bit:
        return False
    if allow & bit:
        return True
    return None


def _triple(allow, deny):
    return (
        _effective_bool(allow, deny, VIEW_CHANNEL),
        _effective_bool(allow, deny, SEND_MESSAGES),
        _effective_bool(allow, deny, CONNECT),
    )


def effective_member_visibility(snapshot: GuildSnapshot) -> VisibilityReport:
    everyone = snapshot.everyone_role_id
    cat_by_id = snapshot.category_by_id()
    rows = []

    for ch in snapshot.channels:
        cat_view = cat_send = cat_connect = None
        ch_view = ch_send = ch_connect = None

        if ch.category_id is not None and ch.category_id in cat_by_id:
            cat_bits = _bits_for(cat_by_id[ch.category_id].overwrites, everyone)
            if cat_bits is not None:
                cat_view, cat_send, cat_connect = _triple(*cat_bits)

        ch_bits = _bits_for(ch.overwrites, everyone)
        if ch_bits is not None:
            ch_view, ch_send, ch_connect = _triple(*ch_bits)

        # Resolve each bit separately: channel SEND cannot erase category VIEW.
        # Guild base and non-@everyone role access are not inferred here.
        view = ch_view if ch_view is not None else cat_view
        send = ch_send if ch_send is not None else cat_send
        connect = ch_connect if ch_connect is not None else cat_connect
        if ch_bits is not None:
            source = "channel_overwrite"
        elif any(bit is not None for bit in (cat_view, cat_send, cat_connect)):
            source = "category_overwrite"
        else:
            source = "unknown_default_deny_closed"

        rows.append(
            ChannelVisibility(
                channel_id=ch.id,
                channel_name=ch.name,
                channel_type=ch.type,
                view=view,
                send=send,
                connect=connect,
                source=source,
                category_view=cat_view,
                category_send=cat_send,
                category_connect=cat_connect,
                channel_view=ch_view,
                channel_send=ch_send,
                channel_connect=ch_connect,
            )
        )

    return VisibilityReport(
        guild_id=snapshot.guild_id,
        everyone_role_id=everyone,
        channels=rows,
    )
