"""Read-only plan/diff against a guild snapshot. No mutations."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .schema import ChangeProposal, Operation


class DiffError(ValueError):
    pass


@dataclass(frozen=True)
class ChannelSnap:
    id: int
    name: str
    type: str
    category_id: int | None = None
    topic: str = ""
    private: bool = False


@dataclass(frozen=True)
class CategorySnap:
    id: int
    name: str
    private: bool = False


@dataclass
class GuildInventory:
    guild_id: int
    categories: list = field(default_factory=list)
    channels: list = field(default_factory=list)
    protected_channel_ids: frozenset = field(default_factory=frozenset)
    protected_category_ids: frozenset = field(default_factory=frozenset)

    def channel_by_id(self) -> dict:
        return {c.id: c for c in self.channels}

    def category_by_id(self) -> dict:
        return {c.id: c for c in self.categories}

    def digest(self) -> str:
        payload = {
            "guild_id": self.guild_id,
            "categories": sorted(
                [{"id": c.id, "name": c.name, "private": c.private} for c in self.categories],
                key=lambda x: x["id"],
            ),
            "channels": sorted(
                [{
                    "id": c.id, "name": c.name, "type": c.type,
                    "category_id": c.category_id, "topic": c.topic, "private": c.private,
                } for c in self.channels],
                key=lambda x: x["id"],
            ),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class DiffLine:
    op_id: str
    op: str
    summary: str
    risk: str
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    blocked: bool = False
    block_reason: str = ""


@dataclass
class PlanDiff:
    guild_id: int
    proposal_id: str
    plan_hash: str
    snapshot_digest_expected: str
    snapshot_digest_actual: str
    stale: bool
    lines: list = field(default_factory=list)
    risk_flags: list = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.stale or any(l.blocked for l in self.lines) or bool(self.risk_flags)


def build_plan_diff(proposal: ChangeProposal, inventory: GuildInventory, plan_hash_value: str) -> PlanDiff:
    if proposal.guild_id != inventory.guild_id:
        raise DiffError(
            f"guild_id mismatch proposal={proposal.guild_id} inventory={inventory.guild_id}"
        )

    actual = inventory.digest()
    stale = actual != proposal.snapshot_digest
    lines = []
    flags = []
    ch = inventory.channel_by_id()
    cat = inventory.category_by_id()

    if stale:
        flags.append("stale_snapshot: inventory changed since proposal was built")

    for op in proposal.operations:
        line = _diff_one(op, ch, cat, inventory)
        lines.append(line)
        if line.blocked:
            flags.append(f"blocked:{op.op_id}:{line.block_reason}")

    return PlanDiff(
        guild_id=proposal.guild_id,
        proposal_id=proposal.proposal_id,
        plan_hash=plan_hash_value,
        snapshot_digest_expected=proposal.snapshot_digest,
        snapshot_digest_actual=actual,
        stale=stale,
        lines=lines,
        risk_flags=flags,
    )


def _diff_one(op: Operation, ch: dict, cat: dict, inv: GuildInventory) -> DiffLine:
    if op.op == "create_category":
        return DiffLine(op_id=op.op_id, op=op.op, summary=f"Create category {op.name!r}",
                        risk="medium", after={"name": op.name})
    if op.op == "create_text_channel":
        parent = op.parent_category_id
        if parent is not None and parent not in cat:
            return DiffLine(op_id=op.op_id, op=op.op, summary=f"Create #{op.name}", risk="medium",
                            blocked=True, block_reason=f"parent_category_id {parent} not in inventory",
                            after={"name": op.name, "parent_category_id": parent})
        if parent is not None and parent in inv.protected_category_ids:
            return DiffLine(op_id=op.op_id, op=op.op, summary=f"Create #{op.name}", risk="high",
                            blocked=True, block_reason="parent category is protected",
                            after={"name": op.name, "parent_category_id": parent})
        if parent is not None and cat[parent].private:
            return DiffLine(op_id=op.op_id, op=op.op, summary=f"Create #{op.name}", risk="high",
                            blocked=True, block_reason="refuses create under private category (no private exposure)",
                            after={"name": op.name, "parent_category_id": parent})
        return DiffLine(op_id=op.op_id, op=op.op,
                        summary=f"Create text channel #{op.name}" + (f" under category {parent}" if parent else ""),
                        risk="medium", after={"name": op.name, "parent_category_id": parent, "topic": op.topic})
    if op.op == "rename_channel":
        cid = op.channel_id
        if cid not in ch:
            return DiffLine(op_id=op.op_id, op=op.op, summary=f"Rename channel {cid}", risk="low",
                            blocked=True, block_reason="channel_id not in inventory")
        if cid in inv.protected_channel_ids:
            return DiffLine(op_id=op.op_id, op=op.op, summary=f"Rename channel {cid}", risk="high",
                            blocked=True, block_reason="channel is protected")
        cur = ch[cid]
        if cur.private:
            return DiffLine(op_id=op.op_id, op=op.op, summary=f"Rename #{cur.name}", risk="high",
                            blocked=True, block_reason="channel is private; refuse mutate")
        return DiffLine(op_id=op.op_id, op=op.op, summary=f"Rename #{cur.name} → #{op.name}", risk="low",
                        before={"channel_id": cur.id, "name": cur.name},
                        after={"channel_id": cur.id, "name": op.name})
    if op.op == "update_topic":
        cid = op.channel_id
        if cid not in ch:
            return DiffLine(op_id=op.op_id, op=op.op, summary=f"Update topic {cid}", risk="low",
                            blocked=True, block_reason="channel_id not in inventory")
        if cid in inv.protected_channel_ids:
            return DiffLine(op_id=op.op_id, op=op.op, summary=f"Update topic {cid}", risk="high",
                            blocked=True, block_reason="channel is protected")
        cur = ch[cid]
        if cur.private:
            return DiffLine(op_id=op.op_id, op=op.op, summary=f"Update topic #{cur.name}", risk="high",
                            blocked=True, block_reason="channel is private; refuse mutate")
        return DiffLine(op_id=op.op_id, op=op.op, summary=f"Update topic on #{cur.name}", risk="low",
                        before={"channel_id": cur.id, "topic": cur.topic},
                        after={"channel_id": cur.id, "topic": op.topic})
    if op.op == "move_channel":
        cid, parent = op.channel_id, op.parent_category_id
        if cid not in ch:
            return DiffLine(op_id=op.op_id, op=op.op, summary=f"Move channel {cid}", risk="medium",
                            blocked=True, block_reason="channel_id not in inventory")
        if parent not in cat:
            return DiffLine(op_id=op.op_id, op=op.op, summary=f"Move channel {cid}", risk="medium",
                            blocked=True, block_reason="parent_category_id not in inventory")
        if cid in inv.protected_channel_ids or parent in inv.protected_category_ids:
            return DiffLine(op_id=op.op_id, op=op.op, summary=f"Move channel {cid}", risk="high",
                            blocked=True, block_reason="protected channel or category")
        cur, dest = ch[cid], cat[parent]
        if cur.private or dest.private:
            return DiffLine(op_id=op.op_id, op=op.op, summary=f"Move #{cur.name}", risk="high",
                            blocked=True, block_reason="refuses move involving private channel/category")
        return DiffLine(op_id=op.op_id, op=op.op,
                        summary=f"Move #{cur.name} → category {dest.name!r} ({dest.id})", risk="medium",
                        before={"channel_id": cur.id, "category_id": cur.category_id},
                        after={"channel_id": cur.id, "category_id": dest.id})
    if op.op == "publish_message":
        cid = op.channel_id
        if cid not in ch:
            return DiffLine(
                op_id=op.op_id, op=op.op, summary=f"Publish to channel {cid}",
                risk="high", blocked=True, block_reason="channel_id not in inventory",
            )
        if cid in inv.protected_channel_ids:
            return DiffLine(
                op_id=op.op_id, op=op.op, summary=f"Publish to channel {cid}",
                risk="high", blocked=True, block_reason="channel is protected",
            )
        cur = ch[cid]
        if cur.private:
            return DiffLine(
                op_id=op.op_id, op=op.op, summary=f"Publish in #{cur.name}",
                risk="high", blocked=True, block_reason="channel is private; refuse publish",
            )
        if cur.type != "text":
            return DiffLine(
                op_id=op.op_id, op=op.op, summary=f"Publish in #{cur.name}",
                risk="high", blocked=True, block_reason="destination is not a text channel",
            )
        return DiffLine(
            op_id=op.op_id, op=op.op, summary=f"Publish announcement in #{cur.name}",
            risk="medium",
            before={"channel_id": cur.id},
            after={"channel_id": cur.id, "content_length": len(op.content or ""),
                   "embed": bool(op.embed_title or op.embed_description)},
        )
    return DiffLine(op_id=op.op_id, op=op.op, summary="unknown op", risk="high",
                    blocked=True, block_reason="unsupported op")
