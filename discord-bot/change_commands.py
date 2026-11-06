"""Owner-only slash commands for AI → Discord change bridge (Batch A).

Registers on the existing bot.tree without replacing the bot.
Never lets Member role or AI approve. Apply requires explicit owner approval
of the exact plan hash and CHANGE_BRIDGE_APPLY_ENABLED gate.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import discord
from discord import app_commands

from discord_bot_change_bridge import (
    parse_proposal,
    plan_hash,
    ProposalError,
    build_plan_diff,
    approve_plan,
    ApprovalError,
    Journal,
    rollback_preview,
)
from discord_bot_change_bridge.inventory_live import build_inventory_from_guild
from discord_bot_change_bridge.preflight import make_phase1_category_proposal
from discord_bot_change_bridge.discord_mutator import DiscordGuildMutator
from discord_bot_change_bridge.async_apply import apply_approved_plan_async

DEFAULT_TARGET_GUILD_ID = 1566290427366080612
_PENDING: dict[int, dict[str, Any]] = {}


def _owner_ids() -> set[int]:
    raw = os.environ.get("CHANGE_BRIDGE_OWNER_IDS") or os.environ.get("DISCORD_OWNER_IDS") or ""
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def _target_guild_id(config: dict) -> int:
    return int(
        os.environ.get("CHANGE_BRIDGE_GUILD_ID")
        or config.get("hub_guild_id")
        or DEFAULT_TARGET_GUILD_ID
    )


def _apply_enabled() -> bool:
    return os.environ.get("CHANGE_BRIDGE_APPLY_ENABLED", "false").lower() in ("1", "true", "yes")


def _protected_ids(config: dict):
    ch, cat = set(), set()
    for x in config.get("change_bridge_protected_channel_ids") or []:
        try:
            ch.add(int(x))
        except (TypeError, ValueError):
            pass
    for x in config.get("change_bridge_protected_category_ids") or []:
        try:
            cat.add(int(x))
        except (TypeError, ValueError):
            pass
    return frozenset(ch), frozenset(cat)


def _journal(data_dir: Path) -> Journal:
    return Journal(data_dir / "change_bridge_journal.json")


def _is_owner(interaction: discord.Interaction) -> bool:
    # Both effective guild authority and an explicit operator allowlist are mandatory.
    owners = _owner_ids()
    guild = getattr(interaction, "guild", None)
    user = getattr(interaction, "user", None)
    if not owners or guild is None or user is None:
        return False
    try:
        uid = int(user.id)
        if uid not in owners:
            return False
        if uid == int(getattr(guild, "owner_id", 0) or 0):
            return True
        permissions = getattr(user, "guild_permissions", None)
        return bool(permissions and getattr(permissions, "manage_guild", False))
    except (TypeError, ValueError, AttributeError):
        return False


def _guild_ok(interaction: discord.Interaction, config: dict) -> str | None:
    if interaction.guild is None:
        return "Run inside the target server."
    target = _target_guild_id(config)
    if int(interaction.guild.id) != target:
        return f"Wrong guild. Expected {target}, got {interaction.guild.id}."
    return None


def register_change_commands(tree: app_commands.CommandTree, *, config: dict, data_dir: Path) -> None:
    @tree.command(name="change-preview", description="Owner: preview a change proposal JSON (no mutations)")
    @app_commands.describe(proposal_json="Full proposal JSON (schema 1.0.0)")
    async def change_preview(interaction: discord.Interaction, proposal_json: str):
        if not _is_owner(interaction):
            return await interaction.response.send_message(
                "Denied: owner allowlist only. Members and AI cannot approve or preview.", ephemeral=True
            )
        err = _guild_ok(interaction, config)
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            raw = json.loads(proposal_json)
            proposal = parse_proposal(raw)
        except (json.JSONDecodeError, ProposalError) as e:
            return await interaction.followup.send(f"Invalid proposal: {e}", ephemeral=True)
        if int(proposal.guild_id) != int(interaction.guild.id):
            return await interaction.followup.send(
                f"Proposal guild_id {proposal.guild_id} ≠ this guild {interaction.guild.id}", ephemeral=True
            )
        pch, pcat = _protected_ids(config)
        inv = build_inventory_from_guild(
            interaction.guild, protected_channel_ids=pch, protected_category_ids=pcat
        )
        ph = plan_hash(proposal)
        diff = build_plan_diff(proposal, inv, ph)
        _PENDING[int(interaction.guild.id)] = {
            "proposal_raw": raw,
            "plan_hash": ph,
            "snapshot_digest_actual": inv.digest(),
            "previewed_by": int(interaction.user.id),
            "previewed_at": int(time.time()),
        }
        from discord_bot_change_bridge.journal import JournalEntry
        _journal(data_dir).append(JournalEntry(
            kind="proposal", at_unix=int(time.time()), guild_id=proposal.guild_id,
            proposal_id=proposal.proposal_id, plan_hash=ph,
            detail={"stale": diff.stale, "blocked": diff.blocked, "ops": len(diff.lines)},
        ))
        lines = [
            f"**Plan hash:** `{ph[:16]}…`",
            f"**Proposal:** `{proposal.proposal_id}`",
            f"**Stale snapshot:** {diff.stale}",
            f"**Blocked:** {diff.blocked}",
            f"**Inventory digest:** `{inv.digest()[:16]}…`",
            "", "**Diff:**",
        ]
        for line in diff.lines[:20]:
            flag = "🚫" if line.blocked else "•"
            lines.append(f"{flag} `{line.op}` {line.summary}" + (f" — {line.block_reason}" if line.blocked else ""))
        if diff.risk_flags:
            lines.append("**Risk flags:** " + "; ".join(diff.risk_flags[:8]))
        lines.append("\nNext: `/change-approve plan_hash_value:<full hash>` (owner only).")
        await interaction.followup.send("\n".join(lines)[:1900], ephemeral=True)

    @tree.command(name="change-layout-preview", description="Owner: auto-preview XYZ.HUB missing PUBLIC categories, no changes")
    async def change_layout_preview(interaction: discord.Interaction):
        if not _is_owner(interaction):
            return await interaction.response.send_message(
                "Denied: verified guild owner allowlist required.", ephemeral=True
            )
        err = _guild_ok(interaction, config)
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        pch, pcat = _protected_ids(config)
        inventory = build_inventory_from_guild(
            interaction.guild,
            protected_channel_ids=pch,
            protected_category_ids=pcat,
        )
        raw = make_phase1_category_proposal(inventory, now_unix=int(time.time()))
        if raw is None:
            return await interaction.followup.send(
                "All six public Phase 1 sections already exist. No plan was created.",
                ephemeral=True,
            )
        proposal = parse_proposal(raw)
        digest = inventory.digest()
        ph = plan_hash(proposal)
        diff = build_plan_diff(proposal, inventory, ph)
        if diff.blocked:
            return await interaction.followup.send(
                "Preview blocked because the inventory changed or a restricted "
                "operation was detected. No Discord changes made.",
                ephemeral=True,
            )
        _PENDING[int(interaction.guild.id)] = {
            "proposal_raw": raw,
            "plan_hash": ph,
            "snapshot_digest_actual": digest,
            "previewed_by": int(interaction.user.id),
            "previewed_at": int(time.time()),
        }
        lines = [
            "**XYZ.HUB — PUBLIC CHANNEL OVERHAUL, PHASE 1**",
            "**READ ONLY. No Discord changes made.**",
            f"Public category creations: {len(diff.lines)}",
            f"Current snapshot digest: `{digest}`",
            "",
            "**Exact plan hash:**",
            f"`{ph}`",
            "",
            "**Proposed missing categories:**",
        ]
        lines += [
            f"• {line.summary}" for line in diff.lines
        ]
        lines += [
            "",
            "Existing Start Here, Education, staff/private and channel messages are preserved.",
            f"Apply enabled: **{_apply_enabled()}** (must remain false until separately authorized).",
            "Owner can request a new review after any server changes.",
        ]
        await interaction.followup.send("\n".join(lines)[:1900], ephemeral=True)

    @tree.command(name="change-approve", description="Owner: approve the exact plan hash from last preview")
    @app_commands.describe(plan_hash_value="Full SHA-256 plan hash from /change-preview")
    async def change_approve(interaction: discord.Interaction, plan_hash_value: str):
        if not _is_owner(interaction):
            return await interaction.response.send_message("Denied: only allowlisted owner may approve.", ephemeral=True)
        err = _guild_ok(interaction, config)
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        pending = _PENDING.get(int(interaction.guild.id))
        if not pending:
            return await interaction.response.send_message(
                "No preview in memory. Run `/change-preview` first in this session.", ephemeral=True
            )
        if pending["plan_hash"] not in (plan_hash_value.strip().lower(), plan_hash_value.strip()):
            return await interaction.response.send_message(
                "Plan hash mismatch. Re-preview and paste the exact hash.", ephemeral=True
            )
        try:
            proposal = parse_proposal(pending["proposal_raw"])
        except ProposalError as e:
            return await interaction.response.send_message(f"Stored proposal invalid: {e}", ephemeral=True)
        try:
            approval = approve_plan(
                proposal, owner_user_id=int(interaction.user.id),
                owner_allowlist=_owner_ids(), now_unix=int(time.time()),
            )
        except ApprovalError as e:
            return await interaction.response.send_message(f"Approval failed: {e}", ephemeral=True)
        pending["approval"] = {
            "approval_id": approval.approval_id, "plan_hash": approval.plan_hash,
            "owner_user_id": approval.owner_user_id, "approved_at_unix": approval.approved_at_unix,
            "expires_at_unix": approval.expires_at_unix, "proposal_id": approval.proposal_id,
            "guild_id": approval.guild_id,
        }
        from discord_bot_change_bridge.journal import JournalEntry
        _journal(data_dir).append(JournalEntry(
            kind="approval", at_unix=int(time.time()), guild_id=approval.guild_id,
            proposal_id=approval.proposal_id, plan_hash=approval.plan_hash,
            detail={"approval_id": approval.approval_id, "owner": approval.owner_user_id},
        ))
        await interaction.response.send_message(
            f"Approved plan `{approval.plan_hash[:16]}…`\napproval_id=`{approval.approval_id}`\n"
            f"Expires <t:{approval.expires_at_unix}:R>\nApply enabled env: `{_apply_enabled()}`\n"
            f"Next: `/change-apply` (owner only).",
            ephemeral=True,
        )

    @tree.command(name="change-apply", description="Owner: apply the approved plan once (gated)")
    async def change_apply(interaction: discord.Interaction):
        if not _is_owner(interaction):
            return await interaction.response.send_message("Denied: owner only.", ephemeral=True)
        err = _guild_ok(interaction, config)
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        pending = _PENDING.get(int(interaction.guild.id))
        if not pending or "approval" not in pending:
            return await interaction.response.send_message("No approved plan. Run preview → approve first.", ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            proposal = parse_proposal(pending["proposal_raw"])
        except ProposalError as e:
            return await interaction.followup.send(f"Proposal invalid: {e}", ephemeral=True)
        from discord_bot_change_bridge.approval import ApprovalRecord
        ad = pending["approval"]
        approval = ApprovalRecord(
            approval_id=ad["approval_id"], guild_id=ad["guild_id"], proposal_id=ad["proposal_id"],
            plan_hash=ad["plan_hash"], owner_user_id=ad["owner_user_id"],
            approved_at_unix=ad["approved_at_unix"], expires_at_unix=ad["expires_at_unix"], consumed=False,
        )
        pch, pcat = _protected_ids(config)
        inv = build_inventory_from_guild(
            interaction.guild, protected_channel_ids=pch, protected_category_ids=pcat
        )
        if inv.digest() != proposal.snapshot_digest:
            return await interaction.followup.send("Stale inventory since proposal — re-preview required.", ephemeral=True)
        mutator = DiscordGuildMutator(interaction.guild)
        result = await apply_approved_plan_async(
            proposal, approval, inv, mutator, _journal(data_dir),
            now_unix=int(time.time()), apply_enabled=_apply_enabled(),
        )
        if result.ok:
            _PENDING.pop(int(interaction.guild.id), None)
            msg = f"Applied plan `{result.plan_hash[:16]}…`\nops={result.applied_op_ids} idempotent={result.skipped_idempotent}\ncreated_ids={result.created_ids}"
        else:
            msg = f"Apply refused/failed: {result.error}"
        await interaction.followup.send(msg[:1900], ephemeral=True)

    @tree.command(name="change-status", description="Owner: show change-bridge journal tail")
    async def change_status(interaction: discord.Interaction):
        if not _is_owner(interaction):
            return await interaction.response.send_message("Denied: owner only.", ephemeral=True)
        entries = _journal(data_dir).entries()[-15:]
        if not entries:
            return await interaction.response.send_message("Journal empty.", ephemeral=True)
        lines = [f"`{e.get('kind')}` prop={e.get('proposal_id')} hash={(e.get('plan_hash') or '')[:12]}… {e.get('detail')}" for e in entries]
        await interaction.response.send_message("\n".join(lines)[:1900], ephemeral=True)

    @tree.command(name="change-rollback-preview", description="Owner: rollback preview (no destructive ops)")
    async def change_rollback_preview(interaction: discord.Interaction):
        if not _is_owner(interaction):
            return await interaction.response.send_message("Denied: owner only.", ephemeral=True)
        err = _guild_ok(interaction, config)
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        pending = _PENDING.get(int(interaction.guild.id))
        if not pending:
            return await interaction.response.send_message("No plan in memory for rollback preview.", ephemeral=True)
        try:
            proposal = parse_proposal(pending["proposal_raw"])
        except ProposalError as e:
            return await interaction.response.send_message(str(e), ephemeral=True)
        pch, pcat = _protected_ids(config)
        inv = build_inventory_from_guild(
            interaction.guild, protected_channel_ids=pch, protected_category_ids=pcat
        )
        rb = rollback_preview(build_plan_diff(proposal, inv, plan_hash(proposal)))
        lines = ["**Reversible:**"] + [f"• {r}" for r in rb.reversible[:15]]
        lines += ["**Notes (no auto-delete):**"] + [f"• {n}" for n in rb.irreversible_notes[:10]]
        await interaction.response.send_message("\n".join(lines)[:1900], ephemeral=True)
