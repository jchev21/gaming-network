"""Apply owner-approved temporary XYZ reveal icon to the existing Discord guild/bot.

Explicit one-time opt-ins only: GN_REVEAL_SERVER_ICON_ONCE and
GN_REVEAL_BOT_AVATAR_ONCE. No channel, role, messages, or permission edits.
"""
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re

import aiohttp

# The owner supplied the exact target guild. Never edit any other server.
TARGET_GUILD_ID = 1566290427366080612
BRAND_URL = "https://gaming-network-web-production.up.railway.app/xyz-logo-reveal.svg"
MAX_SVG_BYTES = 50000

def decode_owner_logo(svg_content: bytes) -> bytes:
    """Extract a single embedded WebP from the deployed self-contained SVG."""
    if not isinstance(svg_content, bytes) or not 0 < len(svg_content) <= MAX_SVG_BYTES:
        raise ValueError("Unexpected SVG size")
    # Do not follow URLs embedded in arbitrary SVG.
    match = re.search(rb'data:image/webp;base64,([A-Za-z0-9+/=]+)', svg_content)
    if not match:
        raise ValueError("XYZ reveal art not present in SVG")
    try:
        icon = base64.b64decode(match.group(1), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid embedded image") from exc
    if not 1024 <= len(icon) <= 10 * 1024 * 1024 or icon[:4] != b'RIFF' or icon[8:12] != b'WEBP':
        raise ValueError("Expected a WebP icon")
    return icon

def owner_intent(env, name):
    return env.get(name, "").lower() == "true"

def marker_path(data_dir):
    return Path(data_dir) / "xyz_reveal_icons_applied.json"

def read_markers(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError):
        return {}

def save_markers(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    os.replace(temp, path)

async def apply_xyz_brand_icons(bot, data_dir, env=None):
    env = os.environ if env is None else env
    update_server = owner_intent(env, "GN_REVEAL_SERVER_ICON_ONCE")
    update_bot = owner_intent(env, "GN_REVEAL_BOT_AVATAR_ONCE")
    if not (update_server or update_bot):
        return

    # Never run without the explicit target-guild/owner match.
    guild = bot.get_guild(TARGET_GUILD_ID)
    if guild is None or not getattr(bot, "user", None):
        print("XYZ branding: target guild/bot not connected; icon not changed")
        return

    marker_file = marker_path(data_dir)
    markers = read_markers(marker_file)
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(BRAND_URL, allow_redirects=False) as response:
                if response.status != 200:
                    raise RuntimeError(f"Unexpected logo response HTTP {response.status}")
                if not response.headers.get("content-type", "").startswith("image/svg+xml"):
                    raise RuntimeError("Unexpected brand asset MIME type")
                payload = await response.content.read(MAX_SVG_BYTES + 1)
        image_bytes = decode_owner_logo(payload)
    except Exception as exc:
        print(f"XYZ branding: no icons changed; logo download failed: {type(exc).__name__}: {exc}")
        return

    sha = hashlib.sha256(image_bytes).hexdigest()
    if update_server:
        if markers.get("guild") == sha:
            print("XYZ branding: server icon already applied to target guild")
        else:
            member = getattr(guild, "me", None)
            if member is None:
                try:
                    member = await guild.fetch_member(bot.user.id)
                except Exception:
                    member = None
            if not member or not getattr(member.guild_permissions, "manage_guild", False):
                print("XYZ branding: bot lacks Manage Server in target guild; no icon change")
            else:
                try:
                    await guild.edit(icon=image_bytes, reason="Owner requested temporary XYZ logo reveal")
                    markers["guild"] = sha
                    save_markers(marker_file, markers)
                    print("XYZ branding: target Discord server icon updated")
                except Exception as exc:
                    print(f"XYZ branding: server icon update failed: {type(exc).__name__}: {exc}")

    if update_bot:
        if markers.get("bot") == sha:
            print("XYZ branding: bot avatar already applied")
        else:
            try:
                await bot.user.edit(avatar=image_bytes)
                markers["bot"] = sha
                save_markers(marker_file, markers)
                print("XYZ branding: Discord bot avatar updated")
            except Exception as exc:
                print(f"XYZ branding: bot avatar update failed: {type(exc).__name__}: {exc}")
