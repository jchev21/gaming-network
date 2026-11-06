"""Effective member visibility — report only, never mutates permissions."""
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
    if deny & bit:
        return False
    if allow & bit:
        return True
    return False


def effective_member_visibility(snapshot: GuildSnapshot) -> VisibilityReport:
    """Report whether @everyone can view/send/connect per channel. Read-only."""
    everyone = snapshot.everyone_role_id
    cat_by_id = snapshot.category_by_id()
    rows = []

    for ch in snapshot.channels:
        source = "unknown_default_deny_closed"
        found = _bits_for(ch.overwrites, everyone)
        allow = deny = 0
        if found is not None:
            allow, deny = found
            source = "overwrite"
        elif ch.category_id is not None and ch.category_id in cat_by_id:
            found = _bits_for(cat_by_id[ch.category_id].overwrites, everyone)
            if found is not None:
                allow, deny = found
                source = "category_overwrite"

        if source == "unknown_default_deny_closed":
            rows.append(
                ChannelVisibility(
                    channel_id=ch.id,
                    channel_name=ch.name,
                    channel_type=ch.type,
                    view=None,
                    send=None,
                    connect=None,
                    source=source,
                )
            )
        else:
            rows.append(
                ChannelVisibility(
                    channel_id=ch.id,
                    channel_name=ch.name,
                    channel_type=ch.type,
                    view=_effective_bool(allow, deny, VIEW_CHANNEL),
                    send=_effective_bool(allow, deny, SEND_MESSAGES),
                    connect=_effective_bool(allow, deny, CONNECT),
                    source=source,
                )
            )

    return VisibilityReport(guild_id=snapshot.guild_id, everyone_role_id=everyone, channels=rows)
