"""Strict versioned change-set schema. Unknown keys fail closed."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0.0"

ALLOWED_OPS = frozenset({
    "create_category",
    "create_text_channel",
    "rename_channel",
    "update_topic",
    "move_channel",
})

_CHANNEL_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,98}[a-z0-9])?$")
_CATEGORY_NAME_RE = re.compile(r"[^\x00-\x1f]{1,100}")


class ProposalError(ValueError):
    """Fail closed: proposal is invalid or unsafe."""


@dataclass(frozen=True)
class Operation:
    op_id: str
    op: str
    channel_id: int | None = None
    category_id: int | None = None
    name: str | None = None
    topic: str | None = None
    parent_category_id: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChangeProposal:
    schema_version: str
    guild_id: int
    proposal_id: str
    idempotency_token: str
    snapshot_digest: str
    operations: tuple
    created_at_unix: int
    expires_at_unix: int
    requester_note: str = ""
    canonical_json: str = ""


def _require_int(obj: dict, key: str, *, positive: bool = True) -> int:
    if key not in obj:
        raise ProposalError(f"missing required field: {key}")
    val = obj[key]
    if isinstance(val, bool) or not isinstance(val, int):
        raise ProposalError(f"{key} must be int")
    if positive and val <= 0:
        raise ProposalError(f"{key} must be positive")
    return val


def _require_str(obj: dict, key: str, *, max_len: int = 200) -> str:
    if key not in obj:
        raise ProposalError(f"missing required field: {key}")
    val = obj[key]
    if not isinstance(val, str) or not val.strip():
        raise ProposalError(f"{key} must be non-empty string")
    if len(val) > max_len:
        raise ProposalError(f"{key} too long")
    return val.strip()


_KNOWN_TOP = frozenset({
    "schema_version", "guild_id", "proposal_id", "idempotency_token",
    "snapshot_digest", "operations", "created_at_unix", "expires_at_unix",
    "requester_note",
})
_KNOWN_OP = frozenset({
    "op_id", "op", "channel_id", "category_id", "name", "topic",
    "parent_category_id",
})


def parse_proposal(raw: Any) -> ChangeProposal:
    if not isinstance(raw, dict):
        raise ProposalError("proposal must be a JSON object")
    unknown = set(raw.keys()) - _KNOWN_TOP
    if unknown:
        raise ProposalError(f"unknown top-level keys (fail closed): {sorted(unknown)}")

    version = _require_str(raw, "schema_version", max_len=16)
    if version != SCHEMA_VERSION:
        raise ProposalError(f"unsupported schema_version {version!r}; need {SCHEMA_VERSION}")

    guild_id = _require_int(raw, "guild_id")
    proposal_id = _require_str(raw, "proposal_id", max_len=64)
    idem = _require_str(raw, "idempotency_token", max_len=128)
    digest = _require_str(raw, "snapshot_digest", max_len=128)
    created = _require_int(raw, "created_at_unix", positive=False)
    expires = _require_int(raw, "expires_at_unix", positive=False)
    if expires <= created:
        raise ProposalError("expires_at_unix must be after created_at_unix")

    note = raw.get("requester_note", "") or ""
    if not isinstance(note, str) or len(note) > 500:
        raise ProposalError("requester_note must be string <= 500 chars")

    ops_raw = raw.get("operations")
    if not isinstance(ops_raw, list) or not ops_raw:
        raise ProposalError("operations must be a non-empty list")
    if len(ops_raw) > 25:
        raise ProposalError("too many operations (max 25)")

    ops = []
    seen_op_ids: set = set()
    for i, item in enumerate(ops_raw):
        if not isinstance(item, dict):
            raise ProposalError(f"operations[{i}] must be object")
        unk = set(item.keys()) - _KNOWN_OP
        if unk:
            raise ProposalError(f"operations[{i}] unknown keys: {sorted(unk)}")
        op_id = _require_str(item, "op_id", max_len=64)
        if op_id in seen_op_ids:
            raise ProposalError(f"duplicate op_id: {op_id}")
        seen_op_ids.add(op_id)
        op = _require_str(item, "op", max_len=32)
        if op not in ALLOWED_OPS:
            raise ProposalError(f"operations[{i}] op {op!r} not allowed")

        channel_id = item.get("channel_id")
        category_id = item.get("category_id")
        parent_category_id = item.get("parent_category_id")
        name = item.get("name")
        topic = item.get("topic")

        if channel_id is not None:
            if isinstance(channel_id, bool) or not isinstance(channel_id, int) or channel_id <= 0:
                raise ProposalError(f"operations[{i}].channel_id invalid")
        if category_id is not None:
            if isinstance(category_id, bool) or not isinstance(category_id, int) or category_id <= 0:
                raise ProposalError(f"operations[{i}].category_id invalid")
        if parent_category_id is not None:
            if isinstance(parent_category_id, bool) or not isinstance(parent_category_id, int) or parent_category_id <= 0:
                raise ProposalError(f"operations[{i}].parent_category_id invalid")
        if name is not None and not isinstance(name, str):
            raise ProposalError(f"operations[{i}].name must be string")
        if topic is not None and not isinstance(topic, str):
            raise ProposalError(f"operations[{i}].topic must be string")
        if topic is not None and len(topic) > 1024:
            raise ProposalError(f"operations[{i}].topic too long")

        if op == "create_category":
            if not name or not _CATEGORY_NAME_RE.match(name):
                raise ProposalError(f"operations[{i}] create_category needs valid name")
            if channel_id is not None:
                raise ProposalError(f"operations[{i}] create_category must not set channel_id")
        elif op == "create_text_channel":
            if not name or not _CHANNEL_NAME_RE.match(name):
                raise ProposalError(f"operations[{i}] create_text_channel needs valid discord channel name")
            if channel_id is not None:
                raise ProposalError(f"operations[{i}] create_text_channel must not set channel_id")
        elif op == "rename_channel":
            if channel_id is None:
                raise ProposalError(f"operations[{i}] rename_channel requires channel_id")
            if not name or not _CHANNEL_NAME_RE.match(name):
                raise ProposalError(f"operations[{i}] rename_channel needs valid name")
        elif op == "update_topic":
            if channel_id is None:
                raise ProposalError(f"operations[{i}] update_topic requires channel_id")
            if topic is None:
                raise ProposalError(f"operations[{i}] update_topic requires topic")
        elif op == "move_channel":
            if channel_id is None:
                raise ProposalError(f"operations[{i}] move_channel requires channel_id")
            if parent_category_id is None:
                raise ProposalError(f"operations[{i}] move_channel requires parent_category_id")

        ops.append(Operation(
            op_id=op_id, op=op, channel_id=channel_id, category_id=category_id,
            name=name, topic=topic, parent_category_id=parent_category_id,
        ))

    canonical_obj = {
        "schema_version": version,
        "guild_id": guild_id,
        "proposal_id": proposal_id,
        "idempotency_token": idem,
        "snapshot_digest": digest,
        "created_at_unix": created,
        "expires_at_unix": expires,
        "requester_note": note,
        "operations": [
            {k: v for k, v in {
                "op_id": o.op_id, "op": o.op, "channel_id": o.channel_id,
                "category_id": o.category_id, "name": o.name, "topic": o.topic,
                "parent_category_id": o.parent_category_id,
            }.items() if v is not None}
            for o in ops
        ],
    }
    canonical_json = json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"))

    return ChangeProposal(
        schema_version=version, guild_id=guild_id, proposal_id=proposal_id,
        idempotency_token=idem, snapshot_digest=digest, operations=tuple(ops),
        created_at_unix=created, expires_at_unix=expires, requester_note=note,
        canonical_json=canonical_json,
    )


def plan_hash(proposal: ChangeProposal) -> str:
    return hashlib.sha256(proposal.canonical_json.encode("utf-8")).hexdigest()
