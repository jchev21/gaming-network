"""Async apply path for DiscordGuildMutator (Batch A/B)."""
from __future__ import annotations

import time
from typing import Any

from .approval import ApprovalRecord, verify_approval, ApprovalError
from .diff import GuildInventory, build_plan_diff
from .journal import Journal, JournalEntry
from .schema import ChangeProposal, plan_hash, Operation
from .apply import ApplyResult


async def apply_approved_plan_async(
    proposal: ChangeProposal,
    approval: ApprovalRecord,
    inventory: GuildInventory,
    mutator: Any,
    journal: Journal,
    *,
    now_unix: int | None = None,
    apply_enabled: bool = True,
) -> ApplyResult:
    now = int(now_unix if now_unix is not None else time.time())
    ph = plan_hash(proposal)

    if not apply_enabled:
        return ApplyResult(ok=False, plan_hash=ph, error="apply disabled (CHANGE_BRIDGE_APPLY_ENABLED=false)")

    if journal.is_idempotency_applied(proposal.idempotency_token):
        return ApplyResult(ok=True, plan_hash=ph, skipped_idempotent=True)

    # A crash after Discord accepts an operation but before a receipt is stored
    # must never permit an automatic replay of that operation.
    # A completed batch is handled by the idempotency check above.
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
        return ApplyResult(ok=False, plan_hash=ph, error="plan blocked: " + "; ".join(diff.risk_flags or ["blocked line"]))

    applied: list = []
    created: dict = {}
    try:
        for op in proposal.operations:
            # Persist intent BEFORE the outbound Discord API call. Even if a
            # process dies after the send but before the receipt, retry fails
            # closed rather than duplicating a message or channel.
            journal.append(JournalEntry(
                kind="operation_attempt", at_unix=now, guild_id=proposal.guild_id,
                proposal_id=proposal.proposal_id, plan_hash=ph,
                detail={"op_id": op.op_id, "op": op.op,
                        "idempotency_token": proposal.idempotency_token},
            ))
            new_id = await _apply_one_async(op, mutator)
            if new_id is not None:
                created[op.op_id] = new_id
            applied.append(op.op_id)
            journal.append(JournalEntry(
                kind="apply", at_unix=now, guild_id=proposal.guild_id,
                proposal_id=proposal.proposal_id, plan_hash=ph,
                detail={"op_id": op.op_id, "op": op.op},
            ))
    except Exception as e:
        return ApplyResult(ok=False, plan_hash=ph, applied_op_ids=applied, created_ids=created,
                           error=f"partial failure after {applied}: {e}")

    journal.mark_approval_consumed(approval.approval_id)
    journal.mark_idempotency_applied(proposal.idempotency_token)
    journal.append(JournalEntry(
        kind="apply", at_unix=now, guild_id=proposal.guild_id,
        proposal_id=proposal.proposal_id, plan_hash=ph,
        detail={"status": "complete", "applied": applied},
    ))
    return ApplyResult(ok=True, plan_hash=ph, applied_op_ids=applied, created_ids=created)


async def _apply_one_async(op: Operation, mutator: Any):
    if op.op == "create_category":
        return await mutator.create_category_async(op.name or "")
    if op.op == "create_text_channel":
        return await mutator.create_text_channel_async(op.name or "", op.parent_category_id, op.topic)
    if op.op == "rename_channel":
        await mutator.rename_channel_async(op.channel_id or 0, op.name or "")
        return None
    if op.op == "update_topic":
        await mutator.update_topic_async(op.channel_id or 0, op.topic or "")
        return None
    if op.op == "move_channel":
        await mutator.move_channel_async(op.channel_id or 0, op.parent_category_id or 0)
        return None
    if op.op == "publish_message":
        return await mutator.publish_message_async(
            op.channel_id or 0, op.content, op.embed_title, op.embed_description, op.embed_color
        )
    raise RuntimeError(f"refusing unsupported op {op.op}")
