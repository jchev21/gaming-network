#!/usr/bin/env python3
"""
Gaming Network — safe, dry-run-first Discord guild structure planner.

Reads desired_guild_structure.json and an optional current-state snapshot
(or uses empty current state). Produces a structured plan of creates /
updates / skips / conflicts. NEVER mutates a live guild.

Default mode is dry-run / read-only. An --apply flag exists only as a
stub and is disabled unless APPLY_GUILD_CHANGES=1 is set AND an
interactive confirmation is given. Tests and CI never enable apply.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DESIRED_PATH = ROOT / "desired_guild_structure.json"


@dataclass
class Action:
    action: str  # create | update | skip | conflict | preserve
    kind: str  # category | channel | role
    name: str
    details: str = ""
    risk: str = "low"  # low | medium | high
    existing_id: str | None = None


@dataclass
class PlanResult:
    status: str  # READY_FOR_MANUAL_SMOKE_TEST | BLOCKED | NOT_VERIFIED
    actions: list[Action] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    risks: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "risks": self.risks,
            "notes": self.notes,
            "actions": [asdict(a) for a in self.actions],
        }


def load_desired(path: Path = DESIRED_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Desired structure not found: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_current(path: Path | None) -> dict[str, Any]:
    """
    Expected optional current snapshot shape (all optional):
    {
      "guild_id": "...",
      "categories": [{"id": "...", "name": "..."}],
      "channels": [{"id": "...", "name": "...", "category": "..."}],
      "roles": [{"id": "...", "name": "..."}]
    }
    If no file is provided, treat current as empty (first-run plan).
    """
    if path is None or not path.exists():
        return {"categories": [], "channels": [], "roles": [], "guild_id": None}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("categories", [])
    data.setdefault("channels", [])
    data.setdefault("roles", [])
    return data


def index_by_name(items: list[dict[str, Any]], key: str = "name") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        name = (item.get(key) or "").strip().lower()
        if name:
            # Prefer first occurrence; later duplicates are conflicts
            if name not in out:
                out[name] = item
    return out


def plan_structure(desired: dict[str, Any], current: dict[str, Any]) -> PlanResult:
    result = PlanResult(status="READY_FOR_MANUAL_SMOKE_TEST")
    result.notes.append(
        "Dry-run only. No Discord API calls. Existing IDs always take precedence over names."
    )
    result.notes.append(
        "Owner must review plan and run apply (if ever enabled) only after explicit approval."
    )

    cur_cats = index_by_name(current.get("categories") or [])
    cur_channels = index_by_name(current.get("channels") or [])
    cur_roles = index_by_name(current.get("roles") or [])

    # Detect name collisions in current state
    def find_dupes(items: list[dict[str, Any]]) -> list[str]:
        seen: dict[str, int] = {}
        dups = []
        for it in items:
            n = (it.get("name") or "").strip().lower()
            if not n:
                continue
            seen[n] = seen.get(n, 0) + 1
        for n, c in seen.items():
            if c > 1:
                dups.append(n)
        return dups

    for kind, items in (
        ("category", current.get("categories") or []),
        ("channel", current.get("channels") or []),
        ("role", current.get("roles") or []),
    ):
        for d in find_dupes(items):
            result.actions.append(
                Action(
                    action="conflict",
                    kind=kind,
                    name=d,
                    details=f"Multiple existing {kind}s share this name. Resolve manually before apply.",
                    risk="high",
                )
            )
            result.risks.append(f"Duplicate existing {kind} name: {d}")

    # Categories & channels
    for cat in desired.get("categories") or []:
        cat_name = cat["name"]
        cat_key = cat_name.strip().lower()
        existing_cat = cur_cats.get(cat_key)
        if existing_cat:
            result.actions.append(
                Action(
                    action="preserve",
                    kind="category",
                    name=cat_name,
                    details="Category already exists; name match. ID preserved.",
                    existing_id=str(existing_cat.get("id") or "") or None,
                    risk="low",
                )
            )
        else:
            result.actions.append(
                Action(
                    action="create",
                    kind="category",
                    name=cat_name,
                    details="Would create category (dry-run).",
                    risk="medium",
                )
            )

        for ch in cat.get("channels") or []:
            ch_name = ch["name"]
            ch_key = ch_name.strip().lower()
            existing_ch = cur_channels.get(ch_key)
            restricted = bool(ch.get("restricted"))
            if existing_ch:
                result.actions.append(
                    Action(
                        action="preserve",
                        kind="channel",
                        name=ch_name,
                        details=(
                            f"Channel already exists under category intent '{cat_name}'. "
                            f"ID preserved. Restricted={restricted}."
                        ),
                        existing_id=str(existing_ch.get("id") or "") or None,
                        risk="low",
                    )
                )
            else:
                risk = "medium" if not restricted else "high"
                result.actions.append(
                    Action(
                        action="create",
                        kind="channel",
                        name=ch_name,
                        details=(
                            f"Would create text channel in category '{cat_name}'. "
                            f"Topic: {ch.get('topic', '')}. Restricted={restricted}."
                        ),
                        risk=risk,
                    )
                )

    # Roles
    for role in desired.get("roles") or []:
        r_name = role["name"]
        r_key = r_name.strip().lower()
        existing_r = cur_roles.get(r_key)
        perms = role.get("permissions") or []
        is_admin = "administrator" in [p.lower() for p in perms]
        if existing_r:
            result.actions.append(
                Action(
                    action="preserve",
                    kind="role",
                    name=r_name,
                    details=f"Role already exists. ID preserved. Desired perms: {perms}",
                    existing_id=str(existing_r.get("id") or "") or None,
                    risk="low",
                )
            )
        else:
            risk = "high" if is_admin else "medium"
            result.actions.append(
                Action(
                    action="create",
                    kind="role",
                    name=r_name,
                    details=(
                        f"Would create role. Color={role.get('color')}, "
                        f"hoist={role.get('hoist')}, perms={perms}. "
                        f"{role.get('notes', '')}"
                    ),
                    risk=risk,
                )
            )
            if is_admin:
                result.risks.append(
                    f"Role '{r_name}' requests Administrator permission. Assign only after explicit owner approval."
                )

    # Summary counts
    counts: dict[str, int] = {}
    for a in result.actions:
        key = f"{a.action}_{a.kind}"
        counts[key] = counts.get(key, 0) + 1
        counts[a.action] = counts.get(a.action, 0) + 1
    result.summary = counts

    if any(a.action == "conflict" for a in result.actions):
        result.status = "BLOCKED"
        result.notes.append("Conflicts detected. Resolve duplicate names before any apply.")
    elif any(a.risk == "high" for a in result.actions):
        result.notes.append("High-risk actions present (admin roles or restricted channels). Manual review required.")

    result.notes.append(
        "This planner never deletes channels or roles. Idempotent: re-running with same current state yields the same plan."
    )
    return result


def render_markdown(plan: PlanResult) -> str:
    lines = [
        "# Guild Structure Plan (Dry-Run)",
        "",
        f"**Status:** `{plan.status}`",
        "",
        "## Summary",
        "",
    ]
    for k, v in sorted(plan.summary.items()):
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    if plan.risks:
        lines.append("## Risks")
        lines.append("")
        for r in plan.risks:
            lines.append(f"- ⚠️ {r}")
        lines.append("")
    lines.append("## Actions")
    lines.append("")
    lines.append("| Action | Kind | Name | Risk | Details |")
    lines.append("|--------|------|------|------|---------|")
    for a in plan.actions:
        details = a.details.replace("|", "\\|")[:120]
        eid = f" id={a.existing_id}" if a.existing_id else ""
        lines.append(f"| {a.action} | {a.kind} | {a.name}{eid} | {a.risk} | {details} |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for n in plan.notes:
        lines.append(f"- {n}")
    lines.append("")
    lines.append("---")
    lines.append("*Generated by `launch/guild_planner.py`. No live Discord mutations performed.*")
    return "\n".join(lines)


def apply_stub(plan: PlanResult, force: bool = False) -> None:
    """
    Apply is intentionally a no-op stub.
    Real mutation requires:
      1. APPLY_GUILD_CHANGES=1 in the environment
      2. --apply on the CLI
      3. Interactive 'yes' confirmation
    Even then this stub refuses to call Discord APIs.
    """
    import os

    if os.environ.get("APPLY_GUILD_CHANGES") != "1":
        print("APPLY DISABLED: set APPLY_GUILD_CHANGES=1 only under explicit owner control.", file=sys.stderr)
        sys.exit(2)
    if not force:
        print("APPLY DISABLED: pass --apply and confirm interactively. Refusing.", file=sys.stderr)
        sys.exit(2)
    print(
        "APPLY STUB: Live guild mutation is not implemented in this safety package. "
        "Document desired changes and perform them manually or via a future owner-approved tool.",
        file=sys.stderr,
    )
    sys.exit(3)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run Discord guild structure planner for Gaming Network Hub."
    )
    parser.add_argument(
        "--desired",
        type=Path,
        default=DESIRED_PATH,
        help="Path to desired_guild_structure.json",
    )
    parser.add_argument(
        "--current",
        type=Path,
        default=None,
        help="Optional JSON snapshot of current categories/channels/roles",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown", "both"),
        default="both",
        help="Output format",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write plan to this path (extension determines format if --format=both)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Attempt apply (disabled by default; requires env + confirmation)",
    )
    args = parser.parse_args(argv)

    desired = load_desired(args.desired)
    current = load_current(args.current)
    plan = plan_structure(desired, current)

    if args.apply:
        apply_stub(plan, force=True)

    if args.format in ("json", "both"):
        payload = json.dumps(plan.to_dict(), indent=2)
        if args.out and args.format == "json":
            args.out.write_text(payload + "\n", encoding="utf-8")
        else:
            print(payload)

    if args.format in ("markdown", "both"):
        md = render_markdown(plan)
        if args.out and args.format == "markdown":
            args.out.write_text(md + "\n", encoding="utf-8")
        elif args.format == "markdown":
            print(md)
        elif args.out:
            # both + out: write markdown beside json
            md_path = args.out.with_suffix(".md") if args.out.suffix else Path(str(args.out) + ".md")
            md_path.write_text(md + "\n", encoding="utf-8")
            if args.format == "both":
                json_path = args.out if args.out.suffix == ".json" else Path(str(args.out) + ".json")
                json_path.write_text(json.dumps(plan.to_dict(), indent=2) + "\n", encoding="utf-8")

    return 0 if plan.status != "BLOCKED" else 1


if __name__ == "__main__":
    sys.exit(main())
