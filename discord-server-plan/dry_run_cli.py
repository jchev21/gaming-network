#!/usr/bin/env python3
"""Print a dry-run plan. Does not call Discord.

Usage:
  python dry_run_cli.py
  python dry_run_cli.py --guild-id 1566290427366080612 --snapshot snapshot.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from discord_bot_guild_plan import GuildSnapshot, build_plan, plan_to_markdown, default_config


def main():
    p = argparse.ArgumentParser(description="Discord guild structure dry-run (no live edits)")
    p.add_argument("--guild-id", type=int, default=1566290427366080612)
    p.add_argument("--snapshot", type=Path, help="Optional JSON snapshot of categories/channels")
    args = p.parse_args()

    if args.snapshot and args.snapshot.exists():
        raw = json.loads(args.snapshot.read_text())
        snap = GuildSnapshot(
            guild_id=int(raw.get("guild_id", args.guild_id)),
            guild_name=raw.get("guild_name", ""),
            categories=raw.get("categories") or {},
            channels=raw.get("channels") or {},
            roles=raw.get("roles") or {},
        )
    else:
        snap = GuildSnapshot(guild_id=args.guild_id)

    plan = build_plan(snap, default_config(guild_id=args.guild_id))
    print(plan_to_markdown(plan))


if __name__ == "__main__":
    main()
