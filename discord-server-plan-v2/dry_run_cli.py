#!/usr/bin/env python3
"""Independently usable dry-run CLI. No Discord API. No live edits.

Usage:
  python dry_run_cli.py --guild-id 1566290427366080612
  python dry_run_cli.py --snapshot snapshot.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from discord_bot_guild_plan import (
    parse_snapshot,
    SnapshotError,
    default_config,
    build_plan,
    plan_to_markdown,
    GuildSnapshot,
)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Discord guild structure dry-run (no live edits)")
    p.add_argument("--guild-id", type=int, help="Required when no snapshot file")
    p.add_argument("--snapshot", type=Path, help="JSON with explicit guild_id and channel ids")
    args = p.parse_args(argv)

    if args.snapshot:
        try:
            raw = json.loads(args.snapshot.read_text())
            snap = parse_snapshot(raw)
        except (OSError, json.JSONDecodeError, SnapshotError) as e:
            print(f"FAIL CLOSED: {e}", file=sys.stderr)
            return 2
        guild_id = snap.guild_id
    else:
        if not args.guild_id:
            print("FAIL CLOSED: --guild-id or --snapshot required", file=sys.stderr)
            return 2
        guild_id = args.guild_id
        snap = GuildSnapshot(guild_id=guild_id)

    try:
        plan = build_plan(snap, default_config(guild_id=guild_id))
    except ValueError as e:
        print(f"FAIL CLOSED: {e}", file=sys.stderr)
        return 2

    print(plan_to_markdown(plan))
    if any(a.op == "fail_closed" for a in plan.actions):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
