"""Optional registration helper for Hub bot start_web() — issue #78.

Import and call from bot.py only after owner review. Grants remain
gated by GN_MEMBER_GRANT_ENABLED (default false).
"""
from __future__ import annotations

from pathlib import Path

from member_grant_api import (
    BotCapability, MemberSnapshot, ReplayStore, RoleSnapshot,
    register_member_grant_routes, RULES_ROLE_NAME, MEMBER_ROLE_NAME,
    TARGET_GUILD_ID,
)


def build_discord_resolver(bot):
    """bot is the live discord.Client / commands.Bot instance."""

    class Ctx:
        def rules_role(self):
            guild = bot.get_guild(TARGET_GUILD_ID)
            if not guild:
                return None
            roles = [r for r in guild.roles if r.name == RULES_ROLE_NAME]
            if len(roles) != 1:
                return None
            r = roles[0]
            return RoleSnapshot(str(r.id), r.name, r.position, {})

        def member_role(self):
            guild = bot.get_guild(TARGET_GUILD_ID)
            if not guild:
                return None
            roles = [r for r in guild.roles if r.name == MEMBER_ROLE_NAME]
            if len(roles) != 1:
                return None
            r = roles[0]
            flags = {
                "administrator": r.permissions.administrator,
                "manage_guild": r.permissions.manage_guild,
                "manage_roles": r.permissions.manage_roles,
                "manage_channels": r.permissions.manage_channels,
                "manage_webhooks": r.permissions.manage_webhooks,
                "manage_messages": r.permissions.manage_messages,
                "ban_members": r.permissions.ban_members,
                "kick_members": r.permissions.kick_members,
                "moderate_members": r.permissions.moderate_members,
            }
            return RoleSnapshot(str(r.id), r.name, r.position, flags)

        def bot_capability(self):
            guild = bot.get_guild(TARGET_GUILD_ID)
            if not guild or not guild.me:
                return BotCapability(False, -1)
            return BotCapability(
                bool(guild.me.guild_permissions.manage_roles),
                int(guild.me.top_role.position),
            )

        async def fetch_member(self, discord_user_id: str):
            guild = bot.get_guild(TARGET_GUILD_ID)
            if not guild:
                return None
            try:
                m = await guild.fetch_member(int(discord_user_id))
            except Exception:
                return None
            return MemberSnapshot(
                user_id=str(m.id),
                pending=bool(m.pending) if m.pending is not None else None,
                role_ids=[str(r.id) for r in m.roles],
                bot=bool(m.bot),
            )

        async def add_member_role(self, discord_user_id: str, role_id: str):
            guild = bot.get_guild(TARGET_GUILD_ID)
            member = await guild.fetch_member(int(discord_user_id))
            role = guild.get_role(int(role_id))
            await member.add_roles(role, reason="XYZ.HUB verified X+Discord Member grant")

    return Ctx()


def attach_member_grant(app, bot, data_dir: Path):
    """Call from start_web after app routes are created."""
    store = ReplayStore(Path(data_dir) / "member_grant_bindings.json")
    register_member_grant_routes(app, store=store, guild_resolver=lambda: build_discord_resolver(bot))
    return store
