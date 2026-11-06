"""Owner-authorized one-shot Discord guild icon + bot avatar update (production)."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


async def apply_xyz_brand_icons(bot: Any, data_dir: Path) -> None:
    """Opt-in branding. No channel mutations. Fail closed without flags/permissions."""
    if not _truthy(os.environ.get("XYZ_APPLY_BRAND_ICONS")):
        return
    guild_id = int(os.environ.get("XYZ_BRAND_GUILD_ID") or os.environ.get("CHANGE_BRIDGE_GUILD_ID") or "0")
    if guild_id <= 0:
        print("xyz_brand_icons: no guild id")
        return
    marker = Path(data_dir) / ".xyz_brand_icons_done"
    if marker.exists() and not _truthy(os.environ.get("XYZ_BRAND_FORCE")):
        return
    await asyncio.sleep(2)
    guild = bot.get_guild(guild_id)
    if guild is None:
        print(f"xyz_brand_icons: guild {guild_id} not in cache")
        return
    me = guild.me
    if me is None or not me.guild_permissions.manage_guild:
        print("xyz_brand_icons: missing Manage Server — skip (fail closed)")
        return
    icon_path = os.environ.get("XYZ_GUILD_ICON_PATH")
    avatar_path = os.environ.get("XYZ_BOT_AVATAR_PATH")
    try:
        if icon_path and Path(icon_path).is_file():
            await guild.edit(icon=Path(icon_path).read_bytes(), reason="XYZ brand icon (owner-approved)")
            print("xyz_brand_icons: guild icon updated")
        if avatar_path and Path(avatar_path).is_file() and bot.user is not None:
            await bot.user.edit(avatar=Path(avatar_path).read_bytes())
            print("xyz_brand_icons: bot avatar updated")
        marker.write_text("done\n", encoding="utf-8")
    except Exception as e:
        print("xyz_brand_icons error:", e)
