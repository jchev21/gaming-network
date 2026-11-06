"""Idempotent Discord guild structure planner (dry-run by default).

No Discord API calls. Operator supplies a guild snapshot dict (from /channelids
export or a future read-only audit). Apply is a separate, explicit step that
must be wired to discord.py only after owner approval — not by this package alone.
"""
from .plan import (
    TARGET_CATEGORIES,
    COMING_SOON_TOPICS,
    GuildSnapshot,
    PlanAction,
    PlanResult,
    build_plan,
    plan_to_markdown,
)
from .config import PlanConfig, default_config

__all__ = [
    "TARGET_CATEGORIES",
    "COMING_SOON_TOPICS",
    "GuildSnapshot",
    "PlanAction",
    "PlanResult",
    "build_plan",
    "plan_to_markdown",
    "PlanConfig",
    "default_config",
]
