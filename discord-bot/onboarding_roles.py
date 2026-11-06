"""XYZ.HUB Rules Screening -> Rules Accepted -> verified X/Discord linking.

Never grants the Member role from a browser link or a claimed username.
Rules Accepted is granted only AFTER Discord-native Membership Screening
(`pending is False`) and after checking Manage Roles + role hierarchy.
All owner setup operations require an explicit owner slash command.
"""
from __future__ import annotations

import os
from pathlib import Path

import discord
from discord import app_commands

from community_onboarding import COMMUNITY_RULES, X_OAUTH_ENTRY, validate_oauth_entry
from discord_bot_change_bridge.preflight import TARGET_GUILD_ID

RULES_ROLE_NAME = "Rules Accepted"
MEMBER_ROLE_NAME = "Member"
RULES_CHANNEL_NAME = "rules"
VERIFY_CHANNEL_NAME = "verify-x"
START_CATEGORY_NAME = "Gaming Network — Start Here"
SCREENING_FEATURE = "MEMBER_VERIFICATION_GATE_ENABLED"


def screening_enabled(guild) -> bool:
    return SCREENING_FEATURE in (getattr(guild, "features", ()) or ())


def roles_named(guild, name: str):
    return [r for r in (getattr(guild, "roles", ()) or ())
            if getattr(r, "name", "").strip().casefold() == name.casefold()]


def get_unique_role(guild, name: str):
    roles = roles_named(guild, name)
    return roles[0] if len(roles) == 1 else None


def dangerous_member_role(role) -> bool:
    permissions = getattr(role, "permissions", None)
    if permissions is None:
        return True
    return any(bool(getattr(permissions, flag, False)) for flag in (
        "administrator", "manage_guild", "manage_roles", "manage_channels",
        "manage_webhooks", "manage_messages", "ban_members", "kick_members",
        "moderate_members",
    ))


def can_assign(guild, role) -> bool:
    bot = getattr(guild, "me", None)
    if bot is None or role is None:
        return False
    perms = getattr(bot, "guild_permissions", None)
    top = getattr(bot, "top_role", None)
    return bool(
        perms is not None
        and getattr(perms, "manage_roles", False)
        and top is not None
        and int(getattr(top, "position", -1)) > int(getattr(role, "position", 999999))
    )


def member_passed_rules(member) -> bool:
    return (
        member is not None
        and getattr(member, "bot", False) is False
        and getattr(member, "pending", None) is False
        and screening_enabled(member.guild)
        and int(member.guild.id) == TARGET_GUILD_ID
    )


async def give_rules_accepted_if_screened(member) -> str:
    """Idempotent, fail-closed assignment. NEVER grants Member."""
    if not member_passed_rules(member):
        return "Native Discord Membership Screening incomplete or unavailable."
    role = get_unique_role(member.guild, RULES_ROLE_NAME)
    if role is None:
        return "Rules Accepted role missing or ambiguous; owner setup required."
    if not can_assign(member.guild, role):
        return "Bot lacks Manage Roles or hierarchy to assign Rules Accepted."
    if role in member.roles:
        return "Rules Accepted already granted."
    try:
        await member.add_roles(role, reason="XYZ.HUB native Membership Screening completed")
    except (discord.Forbidden, discord.HTTPException):
        return "Discord refused role assignment; staff must inspect permissions."
    return "Rules Accepted granted; open #verify-x to continue."


async def on_screening_update(before, after):
    """Only act on Discord's actual pending True -> False transition."""
    if os.getenv("GN_RULES_AUTOGRANT", "false").lower() != "true":
        return None
    if not (getattr(before, "pending", None) is True
            and getattr(after, "pending", None) is False):
        return None
    return await give_rules_accepted_if_screened(after)


class AcceptRulesView(discord.ui.View):
    """Persistent rules acknowledgment button; cannot bypass screening."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="I completed Rules Screening",
        custom_id="xyz:rules-accepted:after-screening:v1",
        style=discord.ButtonStyle.success,
    )
    async def acknowledge(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        if interaction.guild is None or int(interaction.guild.id) != TARGET_GUILD_ID:
            return await interaction.response.send_message("Wrong server.", ephemeral=True)
        # Resolve authoritative member status from Discord instead of trusting
        # an arbitrary interaction payload that might omit the pending field.
        try:
            member = await interaction.guild.fetch_member(int(interaction.user.id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return await interaction.response.send_message(
                "Could not verify your Rules Screening status. Contact staff.", ephemeral=True
            )
        message = await give_rules_accepted_if_screened(member)
        await interaction.response.send_message(message, ephemeral=True)


def _owner_authorized(interaction) -> bool:
    if interaction.guild is None or int(interaction.guild.id) != TARGET_GUILD_ID:
        return False
    if int(interaction.user.id) != int(getattr(interaction.guild, "owner_id", 0)):
        return False
    allowlist = {
        int(x.strip())
        for x in (os.getenv("CHANGE_BRIDGE_OWNER_IDS", "") or "").split(",")
        if x.strip().isdigit()
    }
    return int(interaction.user.id) in allowlist


def onboarding_audit(guild) -> dict:
    if guild is None or int(guild.id) != TARGET_GUILD_ID:
        raise ValueError("Target guild required")
    bot = getattr(guild, "me", None)
    permissions = getattr(bot, "guild_permissions", None)
    rules_role = get_unique_role(guild, RULES_ROLE_NAME)
    member_role = get_unique_role(guild, MEMBER_ROLE_NAME)
    return {
        "screening_enabled": screening_enabled(guild),
        "bot_manage_roles": bool(getattr(permissions, "manage_roles", False)),
        "rules_role": None if rules_role is None else str(rules_role.id),
        "rules_assignable": can_assign(guild, rules_role),
        "member_role": None if member_role is None else str(member_role.id),
        "member_assignable": can_assign(guild, member_role),
        "member_role_safe": member_role is not None and not dangerous_member_role(member_role),
        "rules_channel_exists": any(
            getattr(ch, "name", "") == RULES_CHANNEL_NAME
            for ch in getattr(guild, "text_channels", ())
        ),
        "verify_channel_exists": any(
            getattr(ch, "name", "") == VERIFY_CHANNEL_NAME
            for ch in getattr(guild, "text_channels", ())
        ),
        "rules_autogrant_enabled": os.getenv("GN_RULES_AUTOGRANT", "false").lower() == "true",
        "x_to_discord_member_grant_enabled": False,
        "note": "Member role requires server-verified X + Discord identity; X login alone never grants it.",
    }


def register_onboarding_commands(tree: app_commands.CommandTree, data_dir: Path):
    @tree.command(name="onboarding-audit", description="Owner: read-only audit of Rules/Member role readiness")
    async def onboarding_audit_command(interaction: discord.Interaction):
        if not _owner_authorized(interaction):
            return await interaction.response.send_message("Owner-only.", ephemeral=True)
        state = onboarding_audit(interaction.guild)
        lines = ["**XYZ.HUB onboarding security audit (read only)**"]
        lines.extend(f"{k}: `{v}`" for k, v in state.items())
        await interaction.response.send_message(
            "\n".join(lines)[:1950], ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none()
        )

    @tree.command(name="onboarding-setup", description="Owner: create minimal Rules Accepted / Member roles and gated X channel")
    async def onboarding_setup(interaction: discord.Interaction):
        if not _owner_authorized(interaction):
            return await interaction.response.send_message("Owner-only.", ephemeral=True)
        guild = interaction.guild
        if not screening_enabled(guild):
            return await interaction.response.send_message(
                "Discord native Rules Screening must be enabled first. No changes made.", ephemeral=True
            )
        bot_member = getattr(guild, "me", None)
        bot_permissions = getattr(bot_member, "guild_permissions", None)
        if not bot_permissions or not bot_permissions.manage_roles or not bot_permissions.manage_channels:
            return await interaction.response.send_message(
                "Bot needs Manage Roles and Manage Channels. No changes made.", ephemeral=True
            )
        if any(len(roles_named(guild, name)) > 1 for name in (RULES_ROLE_NAME, MEMBER_ROLE_NAME)):
            return await interaction.response.send_message(
                "Duplicate Rules Accepted or Member roles exist. Resolve manually first.", ephemeral=True
            )
        member_role = get_unique_role(guild, MEMBER_ROLE_NAME)
        if member_role is not None and dangerous_member_role(member_role):
            return await interaction.response.send_message(
                "Existing Member role is privileged. Refusing setup.", ephemeral=True
            )
        start_categories = [c for c in guild.categories
                            if c.name.strip().casefold() == START_CATEGORY_NAME.casefold()]
        if len(start_categories) != 1:
            return await interaction.response.send_message(
                "Start Here category missing or duplicated. No changes made.", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True, thinking=True)
        changes = []
        try:
            rules_role = get_unique_role(guild, RULES_ROLE_NAME)
            if rules_role is None:
                rules_role = await guild.create_role(
                    name=RULES_ROLE_NAME, permissions=discord.Permissions.none(),
                    hoist=False, mentionable=False, reason="Owner-requested two-step onboarding"
                )
                changes.append("Created Rules Accepted role")
            if not can_assign(guild, rules_role):
                raise RuntimeError("Rules Accepted role is above bot; owner must adjust role hierarchy")
            if member_role is None:
                member_role = await guild.create_role(
                    name=MEMBER_ROLE_NAME, permissions=discord.Permissions.none(),
                    hoist=False, mentionable=False, reason="Owner-requested verified X member role"
                )
                changes.append("Created Member role (unassigned)")
            if not can_assign(guild, member_role):
                raise RuntimeError("Member role is above bot; owner must adjust hierarchy")
            existing = [c for c in guild.text_channels if c.name == VERIFY_CHANNEL_NAME]
            if len(existing) > 1:
                raise RuntimeError("Duplicate verify-x channels; manual review required")
            if not existing:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    rules_role: discord.PermissionOverwrite(view_channel=True, read_message_history=True,
                                                              send_messages=False),
                    bot_member: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                                             read_message_history=True),
                }
                await guild.create_text_channel(
                    VERIFY_CHANNEL_NAME, category=start_categories[0],
                    overwrites=overwrites, reason="Owner-requested X verification after rules",
                    topic="Next step after Rules Accepted: connect X and Discord. No automatic Member role until server verification.",
                )
                changes.append("Created restricted #verify-x under Start Here")
            else:
                changes.append("Kept existing #verify-x; review its permissions manually")
        except (discord.Forbidden, discord.HTTPException, RuntimeError) as exc:
            return await interaction.followup.send(
                "Setup partially completed: " + ", ".join(changes)
                + ". Error: " + type(exc).__name__
                + ". Review roles/channels before retry.",
                ephemeral=True
            )
        await interaction.followup.send(
            "Onboarding setup: " + "; ".join(changes)
            + ". No roles were granted to members. Post rules with /onboarding-publish.",
            ephemeral=True
        )

    @tree.command(name="onboarding-publish", description="Owner: post rules and X link in their intended channels")
    async def onboarding_publish(interaction: discord.Interaction):
        if not _owner_authorized(interaction):
            return await interaction.response.send_message("Owner-only.", ephemeral=True)
        guild = interaction.guild
        if not screening_enabled(guild):
            return await interaction.response.send_message(
                "Enable native Rules Screening before publishing.", ephemeral=True
            )
        rules = [c for c in guild.text_channels if c.name == RULES_CHANNEL_NAME]
        verify = [c for c in guild.text_channels if c.name == VERIFY_CHANNEL_NAME]
        if len(rules) != 1 or len(verify) != 1 or not validate_oauth_entry():
            return await interaction.response.send_message(
                "Exactly one #rules and #verify-x plus approved X URL are required.", ephemeral=True
            )
        # Owner must publish from the command intentionally. Do not auto-post on restart.
        await interaction.response.defer(ephemeral=True, thinking=True)
        embed = discord.Embed(
            title="XYZ.HUB · Community Rules",
            description="\n".join(f"{i}. {rule}" for i, rule in enumerate(COMMUNITY_RULES, 1))
            + "\n\nAccept Discord's native Rules Screening, then confirm below to receive Rules Accepted.",
            color=discord.Color.from_str("#a78bfa"),
        )
        await rules[0].send(
            embed=embed, view=AcceptRulesView(),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(
            label="Connect X account — official sign in",
            url=X_OAUTH_ENTRY, style=discord.ButtonStyle.link
        ))
        await verify[0].send(
            "Step 2: sign in on XYZ.HUB using X, then link the same Discord identity. "
            "**X login alone does not grant Member.** Member access activates only after a "
            "trusted server-side dual-account verification is connected.",
            view=view, allowed_mentions=discord.AllowedMentions.none()
        )
        await interaction.followup.send(
            "Published rules and X sign-in instructions. Check #verify-x visibility "
            "with a test account. Member role automation is not enabled.",
            ephemeral=True,
        )

    @tree.command(name="onboarding-status", description="Check Rules Accepted and X onboarding progress")
    async def onboarding_status(interaction: discord.Interaction):
        if interaction.guild is None or int(interaction.guild.id) != TARGET_GUILD_ID:
            return await interaction.response.send_message("Run inside XYZ.HUB.", ephemeral=True)
        try:
            member = await interaction.guild.fetch_member(int(interaction.user.id))
        except (discord.NotFound, discord.HTTPException, discord.Forbidden):
            return await interaction.response.send_message(
                "Cannot verify your Discord screening status.", ephemeral=True
            )
        rules_role = get_unique_role(interaction.guild, RULES_ROLE_NAME)
        member_role = get_unique_role(interaction.guild, MEMBER_ROLE_NAME)
        state = (
            "Rules screening: " + ("accepted" if member_passed_rules(member) else "incomplete")
            + "\nRules Accepted role: " + ("yes" if rules_role and rules_role in member.roles else "no")
            + "\nMember role: " + ("yes" if member_role and member_role in member.roles else "no")
            + "\nNext: complete Rules Screening and #rules, then open #verify-x. "
              "X + Discord linking must be verified server-side."
        )
        await interaction.response.send_message(state, ephemeral=True)
