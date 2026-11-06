"""Live Discord mutator — only after owner approval + plan hash verification."""
from __future__ import annotations

from typing import Any


class DiscordGuildMutator:
    def __init__(self, guild: Any, *, reason: str = "owner-approved change bridge"):
        self.guild = guild
        self.reason = reason

    async def create_category_async(self, name: str) -> int:
        cat = await self.guild.create_category(name, reason=self.reason)
        return int(cat.id)

    async def create_text_channel_async(self, name: str, parent_category_id: int | None, topic: str | None) -> int:
        category = self.guild.get_channel(int(parent_category_id)) if parent_category_id is not None else None
        ch = await self.guild.create_text_channel(name, category=category, topic=topic or None, reason=self.reason)
        return int(ch.id)

    async def rename_channel_async(self, channel_id: int, name: str) -> None:
        ch = self.guild.get_channel(int(channel_id))
        if ch is None:
            raise RuntimeError(f"channel {channel_id} not found")
        await ch.edit(name=name, reason=self.reason)

    async def update_topic_async(self, channel_id: int, topic: str) -> None:
        ch = self.guild.get_channel(int(channel_id))
        if ch is None:
            raise RuntimeError(f"channel {channel_id} not found")
        await ch.edit(topic=topic, reason=self.reason)

    async def move_channel_async(self, channel_id: int, parent_category_id: int) -> None:
        ch = self.guild.get_channel(int(channel_id))
        cat = self.guild.get_channel(int(parent_category_id))
        if ch is None:
            raise RuntimeError(f"channel {channel_id} not found")
        if cat is None:
            raise RuntimeError(f"category {parent_category_id} not found")
        await ch.edit(category=cat, reason=self.reason)

    async def publish_message_async(self, channel_id: int, content: str | None,
                                    embed_title: str | None, embed_description: str | None,
                                    embed_color: str | None) -> int:
        import discord
        ch = self.guild.get_channel(int(channel_id))
        if ch is None:
            raise RuntimeError(f"channel {channel_id} not found")
        embed = None
        if embed_title or embed_description:
            color = 0xa78bfa
            if embed_color:
                try:
                    color = int(str(embed_color).replace("#", ""), 16)
                except ValueError:
                    pass
            embed = discord.Embed(title=embed_title or None, description=embed_description or None, color=color)
        msg = await ch.send(
            content=content or None,
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return int(msg.id)

    def create_category(self, name: str) -> int:
        raise RuntimeError("use async methods on DiscordGuildMutator")

    def create_text_channel(self, name, parent_category_id, topic):
        raise RuntimeError("use async methods on DiscordGuildMutator")

    def rename_channel(self, channel_id, name):
        raise RuntimeError("use async methods on DiscordGuildMutator")

    def update_topic(self, channel_id, topic):
        raise RuntimeError("use async methods on DiscordGuildMutator")

    def move_channel(self, channel_id, parent_category_id):
        raise RuntimeError("use async methods on DiscordGuildMutator")

    def publish_message(self, channel_id, content, embed_title, embed_description, embed_color):
        raise RuntimeError("use async methods on DiscordGuildMutator")
