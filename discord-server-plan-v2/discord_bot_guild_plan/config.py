from __future__ import annotations
from dataclasses import dataclass


@dataclass
class PlanConfig:
    guild_id: int  # required — no silent default for apply-quality runs
    guild_name_hint: str = ""
    lock_coming_soon: bool = True
    ensure_category_voice: bool = True
    require_explicit_ids_for_reuse: bool = True
    private_name_blocklist: tuple = (
        "manager-controls",
        "moderation-log",
        "staff",
        "admin",
        "mod-only",
        "private",
    )
    public_category_names: tuple = (
        "START HERE",
        "GAMING NETWORK",
        "LIVE DASHBOARD",
        "EDUCATION",
        "AFFILIATES & PARTNERS",
        "COMMUNITY",
        "BOT COMMANDS",
    )


def default_config(guild_id: int, **overrides) -> PlanConfig:
    if not isinstance(guild_id, int) or guild_id <= 0:
        raise ValueError("guild_id must be a positive int")
    cfg = PlanConfig(guild_id=guild_id)
    for k, v in overrides.items():
        if not hasattr(cfg, k):
            raise AttributeError(k)
        setattr(cfg, k, v)
    return cfg
