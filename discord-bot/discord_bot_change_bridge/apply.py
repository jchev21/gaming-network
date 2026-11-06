"""Apply only approved allowlisted ops via an injected adapter (mockable).

Real Discord adapter is ChatGPT/integration owned. This module never imports
discord.py and never touches tokens.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from .approval import ApprovalRecord, verify_approval, ApprovalError
from .diff import PlanDiff, GuildInventory, build_plan_diff
from .journal import Journal, JournalEntry
from .schema import ChangeProposal, plan_hash, Operation


class GuildMutator(Protocol):
    def create_category(self, name: str) -> int: ...
    def create_text_channel(self, name: str, parent_category_id: int | None, topic: str | None) -> int: ...
    def rename_channel(self, channel_id: int, name: str) -> None: ...
    def update_topic(self, channel_id: int, topic: str) -> None: ...
    def move_channel(self, channel_id: int, parent_category_id: int) -> None: ...
    def publish_message(self, channel_id: int, content: str | None,
                        embed_title: str | None, embed_description: str | None,
                        embed_color: str | None) -> int: ...


@dataclass
class ApplyResult:
    ok: bool
    plan_hash: str
    applied_op_ids: list = field(default_factory=list)
    skipped_idempotent: bool = False
    error: str = ""
    created_ids: dict = field(default_factory=dict)


@dataclass
class RollbackPreview:
    reversible: list = field(default_factory=list)
    irreversible_notes: list = field(default_factory=list)


def apply_approved_plan(
    proposal: ChangeProposal,
    approval: ApprovalRecord,
    inventory: GuildInventory,
    mutator: GuildMutator,
    journal: Journal,
    *,
    now_unix: int | None = None,
) -> ApplyResult:
    now = int(now_unix if now_unix is not None else time.time())
    ph = plan_hash(proposal)

    if journal.is_idempotency_applied(proposal.idempotency_token):
        return ApplyResult(ok=True, plan_hash=ph, skipped_idempotent=True)

    # Ambiguous partial completion must never auto-replay a Discord operation.
    for old in journal.entries():
        if old.get("kind") == "operation_attempt" and (
            old.get("detail") or {}
        ).get("idempotency_token") == proposal.idempotency_token:
            return ApplyResult(
                ok=False, plan_hash=ph,
                error="prior operation attempt requires manual reconciliation; refusing replay",
            )

    if journal.is_approval_consumed(approval.approval_id):
        return ApplyResult(ok=False, plan_hash=ph, error="approval already consumed")

    try:
        verify_approval(approval, proposal, now_unix=now)
    except ApprovalError as e:
        return ApplyResult(ok=False, plan_hash=ph, error=str(e))

    diff = build_plan_diff(proposal, inventory, ph)
    if diff.blocked:
        return ApplyResult(
            ok=False,
            plan_hash=ph,
            error="plan blocked: " + "; ".join(diff.risk_flags or ["blocked line"]),
        )

    applied = []
    created = {}
    try:
        for op in proposal.operations:
            # The attempt record is durable BEFORE the external operation.
            journal.append(JournalEntry(
                kind="operation_attempt", at_unix=now, guild_id=proposal.guild_id,
                proposal_id=proposal.proposal_id, plan_hash=ph,
                detail={"op_id": op.op_id, "op": op.op,
                        "idempotency_token": proposal.idempotency_token},
            ))
            _apply_one(op, mutator, created)
            applied.append(op.op_id)
            journal.append(JournalEntry(
                kind="apply", at_unix=now, guild_id=proposal.guild_id,
                proposal_id=proposal.proposal_id, plan_hash=ph,
                detail={"op_id": op.op_id, "op": op.op},
            ))
    except Exception as e:
        return ApplyResult(
            ok=False, plan_hash=ph, applied_op_ids=applied, created_ids=created,
            error=f"partial failure after {applied}: {e}",
        )

    journal.mark_approval_consumed(approval.approval_id)
    journal.mark_idempotency_applied(proposal.idempotency_token)
    journal.append(JournalEntry(
        kind="apply", at_unix=now, guild_id=proposal.guild_id,
        proposal_id=proposal.proposal_id, plan_hash=ph,
        detail={"status": "complete", "applied": applied},
    ))
    return ApplyResult(ok=True, plan_hash=ph, applied_op_ids=applied, created_ids=created)


def _apply_one(op: Operation, mutator: GuildMutator, created: dict) -> None:
    if op.op == "create_category":
        created[op.op_id] = mutator.create_category(op.name or "")
    elif op.op == "create_text_channel":
        created[op.op_id] = mutator.create_text_channel(op.name or "", op.parent_category_id, op.topic)
    elif op.op == "rename_channel":
        mutator.rename_channel(op.channel_id or 0, op.name or "")
    elif op.op == "update_topic":
        mutator.update_topic(op.channel_id or 0, op.topic or "")
    elif op.op == "move_channel":
        mutator.move_channel(op.channel_id or 0, op.parent_category_id or 0)
    elif op.op == "publish_message":
        created[op.op_id] = mutator.publish_message(
            op.channel_id or 0, op.content, op.embed_title, op.embed_description, op.embed_color
        )
    else:
        raise RuntimeError(f"refusing unsupported op {op.op}")


def rollback_preview(diff: PlanDiff) -> RollbackPreview:
    preview = RollbackPreview()
    for line in diff.lines:
        if line.blocked:
            continue
        if line.op in ("rename_channel", "update_topic", "move_channel"):
            preview.reversible.append({"op_id": line.op_id, "op": line.op, "restore": line.before})
        elif line.op in ("create_category", "create_text_channel"):
            preview.irreversible_notes.append(
                f"{line.op_id}: create cannot be auto-deleted (no deletions allowed); manual archive only"
            )
        else:
            preview.irreversible_notes.append(f"{line.op_id}: no automatic rollback")
    return preview
