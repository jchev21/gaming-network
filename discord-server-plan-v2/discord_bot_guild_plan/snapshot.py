from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


class SnapshotError(ValueError):
    """Fail closed: snapshot is unusable for planning."""


@dataclass(frozen=True)
class OverwriteRecord:
    target_id: int
    target_type: str
    allow: int = 0
    deny: int = 0


@dataclass(frozen=True)
class ChannelRecord:
    id: int
    name: str
    type: str
    category_id: int | None = None
    topic: str = ""
    overwrites: tuple = ()


@dataclass(frozen=True)
class CategoryRecord:
    id: int
    name: str
    overwrites: tuple = ()


@dataclass(frozen=True)
class RoleRecord:
    id: int
    name: str
    permissions: int = 0


@dataclass
class GuildSnapshot:
    guild_id: int
    guild_name: str = ""
    categories: list = field(default_factory=list)
    channels: list = field(default_factory=list)
    roles: list = field(default_factory=list)
    everyone_role_id: int | None = None

    def channel_by_id(self) -> dict:
        return {c.id: c for c in self.channels}

    def category_by_id(self) -> dict:
        return {c.id: c for c in self.categories}


def _as_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        try:
            if isinstance(value, str) and value.isdigit():
                return int(value)
        except Exception:
            pass
        raise SnapshotError(f"{field_name} must be an int id, got {type(value).__name__}")
    if value <= 0:
        raise SnapshotError(f"{field_name} must be a positive int")
    return value


def parse_snapshot(raw: dict) -> GuildSnapshot:
    if not isinstance(raw, dict):
        raise SnapshotError("snapshot must be a JSON object")
    if "guild_id" not in raw:
        raise SnapshotError("guild_id is required")
    guild_id = _as_int(raw["guild_id"], "guild_id")

    categories = []
    seen_cat_ids: set = set()
    for i, item in enumerate(raw.get("categories") or []):
        if not isinstance(item, dict):
            raise SnapshotError(f"categories[{i}] must be an object")
        cid = _as_int(item.get("id"), f"categories[{i}].id")
        if cid in seen_cat_ids:
            raise SnapshotError(f"duplicate category id {cid}")
        seen_cat_ids.add(cid)
        name = str(item.get("name") or "").strip()
        if not name:
            raise SnapshotError(f"categories[{i}].name is required")
        categories.append(CategoryRecord(id=cid, name=name, overwrites=_parse_overwrites(item.get("overwrites"), f"categories[{i}]")))

    channels = []
    seen_ch_ids: set = set()
    for i, item in enumerate(raw.get("channels") or []):
        if not isinstance(item, dict):
            raise SnapshotError(f"channels[{i}] must be an object")
        cid = _as_int(item.get("id"), f"channels[{i}].id")
        if cid in seen_ch_ids:
            raise SnapshotError(f"duplicate channel id {cid}")
        seen_ch_ids.add(cid)
        name = str(item.get("name") or "").strip()
        if not name:
            raise SnapshotError(f"channels[{i}].name is required")
        ctype = str(item.get("type") or "text").lower()
        cat_id = item.get("category_id")
        cat_id_i = _as_int(cat_id, f"channels[{i}].category_id") if cat_id is not None else None
        channels.append(
            ChannelRecord(
                id=cid,
                name=name,
                type=ctype,
                category_id=cat_id_i,
                topic=str(item.get("topic") or ""),
                overwrites=_parse_overwrites(item.get("overwrites"), f"channels[{i}]"),
            )
        )

    roles = []
    for i, item in enumerate(raw.get("roles") or []):
        if not isinstance(item, dict):
            raise SnapshotError(f"roles[{i}] must be an object")
        rid = _as_int(item.get("id"), f"roles[{i}].id")
        rname = str(item.get("name") or "").strip() or f"role-{rid}"
        perms = item.get("permissions", 0)
        if not isinstance(perms, int) or isinstance(perms, bool):
            perms = 0
        roles.append(RoleRecord(id=rid, name=rname, permissions=perms))

    everyone = raw.get("everyone_role_id")
    everyone_i = _as_int(everyone, "everyone_role_id") if everyone is not None else guild_id

    return GuildSnapshot(
        guild_id=guild_id,
        guild_name=str(raw.get("guild_name") or ""),
        categories=categories,
        channels=channels,
        roles=roles,
        everyone_role_id=everyone_i,
    )


def _parse_overwrites(raw, prefix: str) -> tuple:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise SnapshotError(f"{prefix}.overwrites must be a list")
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise SnapshotError(f"{prefix}.overwrites[{i}] must be an object")
        tid = _as_int(item.get("id", item.get("target_id")), f"{prefix}.overwrites[{i}].id")
        ttype = str(item.get("type", item.get("target_type", "role"))).lower()
        if ttype not in ("role", "member"):
            raise SnapshotError(f"{prefix}.overwrites[{i}].type must be role|member")
        allow = item.get("allow", 0)
        deny = item.get("deny", 0)
        if not isinstance(allow, int) or isinstance(allow, bool):
            allow = 0
        if not isinstance(deny, int) or isinstance(deny, bool):
            deny = 0
        out.append(OverwriteRecord(target_id=tid, target_type=ttype, allow=allow, deny=deny))
    return tuple(out)
