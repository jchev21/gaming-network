"""Read-only Discord guild rollout preflight.

Output contains only @everyone-visible category/channel names and IDs.
Private channels, topics, messages, tokens and role/member lists are never printed.
"""
from __future__ import annotations

from .inventory_live import build_inventory_from_guild

TARGET_GUILD_ID = 1566290427366080612
DESIRED_SECTIONS = (
    "START HERE", "COMMUNITY", "GAMES & X",
    "ALGO LAB", "EDUCATION", "ALL FIRMS", "FEEDBACK", "DISCORD STUDIO",
)

def make_public_preflight(guild, *, bot_id: int | None = None) -> dict:
    if guild is None or int(guild.id) != TARGET_GUILD_ID:
        raise ValueError("Target guild not connected; refusing report")

    snap = build_inventory_from_guild(guild)
    member = getattr(guild, "me", None)
    if member is None and bot_id is not None:
        try:
            member = guild.get_member(int(bot_id))
        except (ValueError, TypeError, AttributeError):
            pass

    perms = getattr(member, "guild_permissions", None)
    def perm(flag):
        value = getattr(perms, flag, None) if perms is not None else None
        return value if isinstance(value, bool) else None

    public_cats = sorted(
        ({"id": x.id, "name": x.name} for x in snap.categories if not x.private),
        key=lambda x: (x["name"].casefold(), x["id"]),
    )
    public_channels = sorted(
        ({"id": x.id, "name": x.name, "type": x.type, "category_id": x.category_id}
         for x in snap.channels if not x.private),
        key=lambda x: (x["category_id"] or 0, x["name"].casefold(), x["id"]),
    )
    existing = {x["name"].casefold() for x in public_cats}
    return {
        "mode": "READ_ONLY_NO_CHANGES",
        "guild_id": TARGET_GUILD_ID,
        # Directly from Discord's guild ownership metadata, not from a guess.
        "guild_owner_id": int(getattr(guild, "owner_id", 0) or 0) or None,
        "bot_permissions": {
            "manage_channels": perm("manage_channels"),
            "manage_guild": perm("manage_guild"),
            "manage_roles": perm("manage_roles"),
            "send_messages": perm("send_messages"),
            "view_channel": perm("view_channel"),
            "embed_links": perm("embed_links"),
        },
        "rules_screening_enabled": "MEMBER_VERIFICATION_GATE_ENABLED" in (
            getattr(guild, "features", ()) or ()
        ),
        "onboarding_roles": {
            label: [
                {"id": int(role.id), "bot_can_assign": bool(
                    perm("manage_roles") and member is not None
                    and getattr(getattr(member, "top_role", None), "position", -1) >
                        getattr(role, "position", 10**9)
                )}
                for role in (getattr(guild, "roles", ()) or ())
                if str(getattr(role, "name", "")).strip().casefold() == label.casefold()
            ]
            for label in ("Rules Accepted", "Member")
        },
        "snapshot_digest": snap.digest(),
        "category_counts": {"public": len(public_cats),
                            "not_public": len(snap.categories) - len(public_cats)},
        "channel_counts": {"public": len(public_channels),
                           "not_public": len(snap.channels) - len(public_channels)},
        "public_categories": public_cats,
        "public_channels": public_channels,
        "suggested_missing_categories": [
            name for name in DESIRED_SECTIONS if name.casefold() not in existing
        ],
    }


def make_phase1_category_proposal(inventory, *, now_unix: int):
    """Build safe public-category-only proposal using a FRESH live inventory.

    It never creates duplicates of existing public OR restricted categories
    and never mutates the Discord API. Missing sections are added as separate
    create_category ops; actual channel moves require a second owner review.
    """
    if inventory.guild_id != TARGET_GUILD_ID:
        raise ValueError("Unexpected guild for XYZ.HUB phase 1")
    present = {str(x.name).strip().casefold() for x in inventory.categories}
    # Reuse the existing real Gaming Network — Start Here and EDUCATION.
    desired = (
        ("COMMUNITY", "community"),
        ("GAMES & X", "games-x"),
        ("ALGO LAB", "algo-lab"),
        ("ALL FIRMS", "all-firms"),
        ("FEEDBACK", "feedback"),
        ("DISCORD STUDIO", "discord-studio"),
    )
    operations = []
    for name, slug in desired:
        if name.casefold() not in present:
            operations.append({
                "op_id": "create-" + slug,
                "op": "create_category",
                "name": name,
            })
    if not operations:
        return None
    return {
        "schema_version": "1.0.0",
        "guild_id": inventory.guild_id,
        "proposal_id": "xyz-hub-phase1-live-layout",
        "idempotency_token": "xyz-hub-phase1-" + inventory.digest()[:40],
        "snapshot_digest": inventory.digest(),
        "created_at_unix": now_unix,
        "expires_at_unix": now_unix + 3600,
        "requester_note": (
            "Owner preview of missing PUBLIC categories only; no moves, "
            "posts, deletes, permission grants or role changes."
        ),
        "operations": operations,
    }
