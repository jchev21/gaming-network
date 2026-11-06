from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlanConfig:
    """Configurable IDs — never hard-require a single production guild."""

    guild_id: int = 1566290427366080612  # observed default; override freely
    guild_name_hint: str = "Hub.XYZ waitlist"
    lock_coming_soon: bool = True
    ensure_category_voice: bool = True
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


def default_config(**overrides) -> PlanConfig:
    cfg = PlanConfig()
    for k, v in overrides.items():
        if not hasattr(cfg, k):
            raise AttributeError(k)
        setattr(cfg, k, v)
    return cfg
