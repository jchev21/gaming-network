"""Owner-approved AI → Discord bot channel/category change bridge.

LLM proposes structured change-sets only. Bot applies after explicit owner
approval of an exact plan hash. No live Discord calls in unit tests.
No token disclosure. No deletions. No permission escalation.
"""
from .schema import (
    SCHEMA_VERSION,
    ALLOWED_OPS,
    ChangeProposal,
    Operation,
    ProposalError,
    parse_proposal,
    plan_hash,
)
from .diff import PlanDiff, build_plan_diff, DiffError
from .approval import ApprovalRecord, ApprovalError, approve_plan, verify_approval
from .journal import Journal, JournalError
from .apply import ApplyResult, apply_approved_plan, RollbackPreview, rollback_preview

__all__ = [
    "SCHEMA_VERSION",
    "ALLOWED_OPS",
    "ChangeProposal",
    "Operation",
    "ProposalError",
    "parse_proposal",
    "plan_hash",
    "PlanDiff",
    "build_plan_diff",
    "DiffError",
    "ApprovalRecord",
    "ApprovalError",
    "approve_plan",
    "verify_approval",
    "Journal",
    "JournalError",
    "ApplyResult",
    "apply_approved_plan",
    "RollbackPreview",
    "rollback_preview",
]
