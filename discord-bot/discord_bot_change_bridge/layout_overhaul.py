"""Owner-reviewed XYZ.HUB channel moves — no Discord API calls.

Discord supports a category → channels hierarchy, not nested categories.
This maps existing *public* channel IDs to appropriate public headings; refuses
to touch private channels or a channel inside any private parent category.
Never delete/merge channels: duplicate named channels remain distinct IDs.
"""
from __future__ import annotations

from .preflight import TARGET_GUILD_ID

# Exact IDs from the read-only live public snapshot, with name verification.
# Updating a wrong/renamed ID must fail closed rather than move another channel.
TARGETS = (
    (1568331098239537274, "start-here", "Gaming Network — Start Here"),
    (1568085615722111117, "rules", "Gaming Network — Start Here"),
    # First three Community slots: existing text dashboard and announcements;
    # native Stage channel is a separately reviewed create operation.
    (1567827003414159365, "dashboard", "COMMUNITY"),
    (1567328326169796608, "announcements", "COMMUNITY"),
    (1566290428079374539, "hub", "COMMUNITY"),
    (1566984686998261761, "channels", "COMMUNITY"),
    (1567328327524548712, "calendar", "COMMUNITY"),
    (1567328333031538879, "alerts", "COMMUNITY"),
    (1567328330917748798, "giveaways", "COMMUNITY"),
    (1567328336894492682, "rewards-and-points", "COMMUNITY"),
    (1567328334298222602, "games-and-events", "GAMES & X"),
    (1567827004928036964, "games-and-events", "GAMES & X"),
    (1566290771387093152, "codes", "GAMES & X"),
    (1566982323763810305, "promo-codes", "GAMES & X"),
    (1567328329713852476, "promo-codes", "GAMES & X"),
    (1567328335258980433, "code-drops", "GAMES & X"),
    (1568331258705219705, "gaming-videos", "GAMES & X"),
    (1567328368645644501, "algo-lab", "ALGO LAB"),
    (1568331311750578396, "algo-lab-videos", "ALGO LAB"),
    (1567328365281808435, "education", "EDUCATION"),
    (1568331344021561465, "education-videos", "EDUCATION"),
    (1567328370562433074, "payout-reports", "ALL FIRMS"),
    (1567328371929645126, "scaling-vs-payouts", "ALL FIRMS"),
    (1567328378690740265, "suggestions", "FEEDBACK"),
    (1568331283401154580, "dashboard-videos", "DISCORD STUDIO"),
    (1567328338232614978, "affiliate-help", "AFFILIATES & MANAGERS"),
)

# The bot's existing native /hubview and /dashboard channels remain intact.
# Trading channels under a non-public category are intentionally not listed.

def _safe_public_destinations(inventory):
    result = {}
    for category in inventory.categories:
        if not category.private and category.id not in inventory.protected_category_ids:
            key = category.name.strip().casefold()
            if key in result:
                # Two categories with the same heading: ambiguous, refuse both.
                result[key] = None
            else:
                result[key] = category.id
    return result


def build_move_batch(inventory, *, now_unix: int, batch_number: int = 1, max_moves: int = 18):
    """Return a strict, fresh-snapshot proposal or None if no moves in batch.

    Batches are bounded and ephemeral; after any apply, take a fresh inventory
    before generating the next plan because the digest intentionally changes.
    """
    if inventory.guild_id != TARGET_GUILD_ID:
        raise ValueError("Guild mismatch")
    if not isinstance(batch_number, int) or not 1 <= batch_number <= 9:
        raise ValueError("Invalid batch number")
    if not 1 <= max_moves <= 20:
        raise ValueError("Invalid maximum move count")
    destinations = _safe_public_destinations(inventory)
    by_id = inventory.channel_by_id()
    category_by_id = inventory.category_by_id()
    moves = []
    for channel_id, expected_name, destination in TARGETS:
        channel = by_id.get(channel_id)
        if channel is None or channel.name != expected_name or channel.private:
            continue
        if channel.id in inventory.protected_channel_ids:
            continue
        if channel.category_id is not None:
            old_parent = category_by_id.get(channel.category_id)
            if old_parent is None or old_parent.private or old_parent.id in inventory.protected_category_ids:
                continue
        parent_id = destinations.get(destination.casefold())
        if parent_id is None or parent_id == channel.category_id:
            continue
        if channel.type != "text":
            continue
        moves.append({
            "op_id": "move-" + str(channel_id),
            "op": "move_channel",
            "channel_id": channel_id,
            "parent_category_id": parent_id,
        })
    start = (batch_number - 1) * max_moves
    ops = moves[start:start + max_moves]
    if not ops:
        return None
    return {
        "schema_version": "1.0.0",
        "guild_id": inventory.guild_id,
        "proposal_id": "xyz-hub-public-channel-moves-" + str(batch_number),
        "idempotency_token": "xyz-hub-move-" + str(batch_number) + "-" + inventory.digest()[:40],
        "snapshot_digest": inventory.digest(),
        "created_at_unix": int(now_unix),
        "expires_at_unix": int(now_unix) + 3600,
        "requester_note": (
            "Public-to-public channel moves preserving IDs and history; "
            "NO sync_permissions, deletes, role changes, or private parents."
        ),
        "operations": ops,
    }


def build_stage_proposal(inventory, *, now_unix: int, community_enabled: bool):
    """One reviewed native Stage channel under COMMUNITY, never a voice clone."""
    if inventory.guild_id != TARGET_GUILD_ID:
        raise ValueError("Guild mismatch")
    if not community_enabled:
        return None  # Community feature required for Discord Stage
    destinations = _safe_public_destinations(inventory)
    community_id = destinations.get("community")
    if community_id is None:
        return None
    if any(ch.name.strip().casefold() == "stage" and ch.category_id == community_id
           for ch in inventory.channels):
        return None
    return {
        "schema_version": "1.0.0",
        "guild_id": inventory.guild_id,
        "proposal_id": "xyz-hub-community-stage",
        "idempotency_token": "xyz-hub-community-stage-" + inventory.digest()[:40],
        "snapshot_digest": inventory.digest(),
        "created_at_unix": int(now_unix),
        "expires_at_unix": int(now_unix) + 3600,
        "requester_note": "Create native #stage audio Stage under COMMUNITY. No channel/role edits.",
        "operations": [
            {"op_id": "create-community-stage", "op": "create_stage_channel",
             "name": "stage", "parent_category_id": community_id},
        ],
    }
