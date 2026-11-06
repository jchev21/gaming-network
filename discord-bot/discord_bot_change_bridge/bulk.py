"""Batch C helpers: bounded bulk execution receipts. No destructive ops."""
from __future__ import annotations
from dataclasses import dataclass, field

MAX_OPS_PER_PROPOSAL = 25
MAX_CREATES_PER_PROPOSAL = 15


@dataclass
class OpReceipt:
    op_id: str
    op: str
    ok: bool
    detail: str = ""
    discord_id: int | None = None


@dataclass
class BulkReceipt:
    proposal_id: str
    plan_hash: str
    receipts: list = field(default_factory=list)
    partial: bool = False

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "plan_hash": self.plan_hash,
            "partial": self.partial,
            "receipts": [
                {"op_id": r.op_id, "op": r.op, "ok": r.ok, "detail": r.detail, "discord_id": r.discord_id}
                for r in self.receipts
            ],
        }


def validate_bulk_bounds(operations: list) -> list:
    flags = []
    if len(operations) > MAX_OPS_PER_PROPOSAL:
        flags.append(f"too_many_ops:{len(operations)}>{MAX_OPS_PER_PROPOSAL}")
    creates = sum(1 for o in operations if getattr(o, "op", "") in ("create_category", "create_text_channel"))
    if creates > MAX_CREATES_PER_PROPOSAL:
        flags.append(f"too_many_creates:{creates}>{MAX_CREATES_PER_PROPOSAL}")
    return flags
