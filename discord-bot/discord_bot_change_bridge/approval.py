"""Short-lived owner approval bound to exact plan hash. Single use."""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

from .schema import ChangeProposal, plan_hash


class ApprovalError(ValueError):
    pass


@dataclass(frozen=True)
class ApprovalRecord:
    approval_id: str
    guild_id: int
    proposal_id: str
    plan_hash: str
    owner_user_id: int
    approved_at_unix: int
    expires_at_unix: int
    consumed: bool = False


def approve_plan(
    proposal: ChangeProposal,
    *,
    owner_user_id: int,
    owner_allowlist: set[int],
    now_unix: int | None = None,
    approval_ttl_seconds: int = 900,
) -> ApprovalRecord:
    if owner_user_id not in owner_allowlist:
        raise ApprovalError("owner_user_id not in allowlist")
    now = int(now_unix if now_unix is not None else time.time())
    if now > proposal.expires_at_unix:
        raise ApprovalError("proposal expired")
    if approval_ttl_seconds <= 0 or approval_ttl_seconds > 3600:
        raise ApprovalError("approval_ttl_seconds out of range")
    exp = min(now + approval_ttl_seconds, proposal.expires_at_unix)
    return ApprovalRecord(
        approval_id=secrets.token_hex(16),
        guild_id=proposal.guild_id,
        proposal_id=proposal.proposal_id,
        plan_hash=plan_hash(proposal),
        owner_user_id=owner_user_id,
        approved_at_unix=now,
        expires_at_unix=exp,
        consumed=False,
    )


def verify_approval(
    approval: ApprovalRecord,
    proposal: ChangeProposal,
    *,
    now_unix: int | None = None,
) -> None:
    now = int(now_unix if now_unix is not None else time.time())
    if approval.consumed:
        raise ApprovalError("approval already consumed (idempotent reject)")
    if now > approval.expires_at_unix:
        raise ApprovalError("approval expired")
    if approval.guild_id != proposal.guild_id:
        raise ApprovalError("guild_id mismatch")
    if approval.proposal_id != proposal.proposal_id:
        raise ApprovalError("proposal_id mismatch")
    expected = plan_hash(proposal)
    if approval.plan_hash != expected:
        raise ApprovalError("plan_hash mismatch — owner must re-approve exact plan")
