"""Independently usable Discord guild dry-run planner.

- Explicit guild_id required
- Channel reuse by explicit channel id when provided
- Fail closed on ambiguous name to id mappings
- One member-visible voice channel per public category
- Reject private/hidden channel reuse for public targets
- Report effective member visibility WITHOUT changing permissions
- No Discord API calls; no live edits
"""
from .config import PlanConfig, default_config
from .snapshot import (
    ChannelRecord,
    CategoryRecord,
    RoleRecord,
    OverwriteRecord,
    GuildSnapshot,
    SnapshotError,
    parse_snapshot,
)
from .resolve import resolve_targets, AmbiguousMappingError, Resolution
from .visibility import effective_member_visibility, VisibilityReport
from .plan import (
    TARGET_CATEGORIES,
    COMING_SOON_TOPICS,
    PlanAction,
    PlanResult,
    build_plan,
    plan_to_markdown,
    voice_channels_per_category,
    assert_one_voice_per_public_category,
    is_private_channel_record,
)

__all__ = [
    "PlanConfig",
    "default_config",
    "ChannelRecord",
    "CategoryRecord",
    "RoleRecord",
    "OverwriteRecord",
    "GuildSnapshot",
    "SnapshotError",
    "parse_snapshot",
    "resolve_targets",
    "AmbiguousMappingError",
    "Resolution",
    "effective_member_visibility",
    "VisibilityReport",
    "TARGET_CATEGORIES",
    "COMING_SOON_TOPICS",
    "PlanAction",
    "PlanResult",
    "build_plan",
    "plan_to_markdown",
    "voice_channels_per_category",
    "assert_one_voice_per_public_category",
    "is_private_channel_record",
]
