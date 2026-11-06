from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import PlanConfig
from .snapshot import GuildSnapshot
from .resolve import resolve_targets, AmbiguousMappingError, Resolution
from .visibility import effective_member_visibility, VisibilityReport

TARGET_CATEGORIES: dict[str, list[dict[str, Any]]] = {
    "START HERE": [
        {"name": "welcome", "type": "text"},
        {"name": "rules", "type": "text"},
        {"name": "announcements", "type": "text"},
        {"name": "how-to-start", "type": "text"},
        {"name": "roles-and-interests", "type": "text"},
        {"name": "support", "type": "text"},
        {"name": "start-here-voice", "type": "voice"},
    ],
    "GAMING NETWORK": [
        {"name": "games-and-events", "type": "text"},
        {"name": "find-a-game", "type": "text"},
        {"name": "live-lobbies", "type": "text"},
        {"name": "tournaments", "type": "text"},
        {"name": "winners-and-highlights", "type": "text"},
        {"name": "game-help", "type": "text"},
        {"name": "gaming-voice", "type": "voice"},
    ],
    "LIVE DASHBOARD": [
        {"name": "dashboard", "type": "text"},
        {"name": "giveaways", "type": "text"},
        {"name": "promo-codes", "type": "text"},
        {"name": "alerts", "type": "text"},
        {"name": "leaderboards", "type": "text"},
        {"name": "rewards-and-points", "type": "text"},
        {"name": "dashboard-voice", "type": "voice"},
    ],
    "EDUCATION": [
        {"name": "education-start", "type": "text", "coming_soon": True},
        {"name": "course-library", "type": "text", "coming_soon": True},
        {"name": "algo-lab", "type": "text", "coming_soon": True},
        {"name": "education-questions", "type": "text"},
        {"name": "education-voice", "type": "voice"},
    ],
    "AFFILIATES & PARTNERS": [
        {"name": "affiliate-help", "type": "text"},
        {"name": "affiliate-news", "type": "text"},
        {"name": "affiliate-links", "type": "text"},
        {"name": "affiliate-reports", "type": "text"},
        {"name": "affiliate-voice", "type": "voice"},
    ],
    "COMMUNITY": [
        {"name": "general", "type": "text"},
        {"name": "introductions", "type": "text"},
        {"name": "suggestions", "type": "text"},
        {"name": "bug-reports", "type": "text"},
        {"name": "community-voice", "type": "voice"},
    ],
    "BOT COMMANDS": [
        {"name": "bot-commands", "type": "text"},
    ],
}

COMING_SOON_TOPICS = {
    "education-start": "COMING SOON — Education Center preview (read-only)",
    "course-library": "COMING SOON — Course library preview (read-only)",
    "algo-lab": "COMING SOON — Algo Lab preview (read-only; demo UI only)",
}


def voice_channels_per_category() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for cat, specs in TARGET_CATEGORIES.items():
        out[cat] = [s["name"] for s in specs if s.get("type") == "voice"]
    return out


def assert_one_voice_per_public_category(public_names: tuple[str, ...] | None = None) -> None:
    names = public_names or (
        "START HERE", "GAMING NETWORK", "LIVE DASHBOARD",
        "EDUCATION", "AFFILIATES & PARTNERS", "COMMUNITY",
    )
    voices = voice_channels_per_category()
    for cat in names:
        v = voices.get(cat, [])
        if len(v) != 1:
            raise ValueError(
                f"Category {cat!r} must have exactly one member-visible voice channel, found {v}"
            )


def is_private_channel_record(meta, visibility_row, blocklist: set[str]) -> bool:
    """Refuse public reuse without affirmative @everyone VIEW evidence.

    This is a candidate filter, not full Discord role/permission verification.
    Missing and unknown visibility must not be treated as public.
    """
    if meta is None or visibility_row is None:
        return True
    if meta.name.casefold() in {name.casefold() for name in blocklist}:
        return True
    return visibility_row.view is not True


@dataclass
class PlanAction:
    op: str
    category: str | None = None
    channel: str | None = None
    channel_id: int | None = None
    category_id: int | None = None
    channel_type: str | None = None
    detail: str = ""
    risk: str = "low"


@dataclass
class PlanResult:
    guild_id: int
    actions: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    resolution: Resolution | None = None
    visibility: VisibilityReport | None = None

    @property
    def creates(self):
        return [a for a in self.actions if a.op.startswith("create_")]


def build_plan(snapshot: GuildSnapshot, config: PlanConfig) -> PlanResult:
    if snapshot.guild_id != config.guild_id:
        raise ValueError(
            f"guild_id mismatch: snapshot={snapshot.guild_id} config={config.guild_id} (fail closed)"
        )

    assert_one_voice_per_public_category(
        tuple(c for c in config.public_category_names if c != "BOT COMMANDS")
    )
    result = PlanResult(guild_id=snapshot.guild_id)
    result.visibility = effective_member_visibility(snapshot)

    target_cats = list(TARGET_CATEGORIES.keys())
    target_channels = [s["name"] for specs in TARGET_CATEGORIES.values() for s in specs]

    try:
        resolution = resolve_targets(
            snapshot, target_cats, target_channels, fail_closed=True
        )
    except AmbiguousMappingError as exc:
        result.warnings.append(str(exc))
        result.actions.append(
            PlanAction(op="fail_closed", detail=str(exc), risk="high")
        )
        return result

    result.resolution = resolution
    ch_by_id = snapshot.channel_by_id()

    for cat_name, specs in TARGET_CATEGORIES.items():
        cat_id = resolution.categories.get(cat_name)
        if cat_id is None:
            result.actions.append(
                PlanAction(
                    op="create_category",
                    category=cat_name,
                    detail="No explicit category id resolved — create candidate",
                    risk="medium",
                )
            )
        else:
            result.actions.append(
                PlanAction(
                    op="reuse_category",
                    category=cat_name,
                    category_id=cat_id,
                    detail=f"Reuse category id={cat_id}",
                    risk="low",
                )
            )

        for spec in specs:
            name = spec["name"]
            ctype = spec.get("type", "text")
            low = name.lower()
            if low in {b.lower() for b in config.private_name_blocklist}:
                result.actions.append(
                    PlanAction(
                        op="skip_private",
                        category=cat_name,
                        channel=name,
                        detail="Blocklisted — will not open or alter",
                        risk="high",
                    )
                )
                continue

            resolved_id = resolution.channels.get(name)
            if resolved_id is not None:
                meta = ch_by_id.get(resolved_id)
                vis_row = None
                if result.visibility is not None:
                    vis_row = next(
                        (v for v in result.visibility.channels if v.channel_id == resolved_id),
                        None,
                    )
                block = {b.lower() for b in config.private_name_blocklist}
                wrong_type = meta is not None and meta.type != ctype
                wrong_category = meta is not None and (
                    cat_id is None or meta.category_id != cat_id
                )
                if is_private_channel_record(meta, vis_row, block) or wrong_type or wrong_category:
                    reasons = []
                    if is_private_channel_record(meta, vis_row, block):
                        reasons.append("@everyone visibility missing, denied or blocklisted")
                    if wrong_type:
                        reasons.append(f"type mismatch: expected {ctype}")
                    if wrong_category:
                        reasons.append("category mismatch or unresolved category id")
                    result.actions.append(
                        PlanAction(
                            op="reject_private_reuse",
                            category=cat_name,
                            channel=name,
                            channel_id=resolved_id,
                            category_id=cat_id,
                            channel_type=ctype,
                            detail=f"Refuse reuse of id={resolved_id} ({'; '.join(reasons)})",
                            risk="high",
                        )
                    )
                    continue
                detail = f"Reuse channel id={resolved_id}"
                result.actions.append(
                    PlanAction(
                        op="reuse_channel",
                        category=cat_name,
                        channel=name,
                        channel_id=resolved_id,
                        category_id=cat_id,
                        channel_type=ctype,
                        detail=detail,
                        risk="low",
                    )
                )
                if spec.get("coming_soon") and config.lock_coming_soon:
                    topic = COMING_SOON_TOPICS.get(low, "COMING SOON")
                    if meta and "COMING SOON" not in (meta.topic or "").upper():
                        result.actions.append(
                            PlanAction(
                                op="set_topic",
                                category=cat_name,
                                channel=name,
                                channel_id=resolved_id,
                                detail=f"Set topic {topic!r}",
                                risk="low",
                            )
                        )
                    result.actions.append(
                        PlanAction(
                            op="deny_send_everyone",
                            category=cat_name,
                            channel=name,
                            channel_id=resolved_id,
                            detail="Coming Soon read-only for @everyone (planned)",
                            risk="medium",
                        )
                    )
            else:
                if not config.ensure_category_voice and ctype == "voice":
                    continue
                detail = "No explicit channel id — create candidate"
                if spec.get("coming_soon"):
                    detail += " + Coming Soon topic + deny send"
                result.actions.append(
                    PlanAction(
                        op="create_channel",
                        category=cat_name,
                        channel=name,
                        category_id=cat_id,
                        channel_type=ctype,
                        detail=detail,
                        risk="medium" if ctype == "voice" else "low",
                    )
                )

    if not snapshot.channels and not snapshot.categories:
        result.warnings.append(
            "Empty inventory — all targets are create candidates. "
            "Supply snapshot with explicit ids before apply."
        )

    return result


def plan_to_markdown(result: PlanResult) -> str:
    lines = [
        f"# Guild plan dry-run (guild_id={result.guild_id})",
        "",
        f"Actions: {len(result.actions)} · Creates: {len(result.creates)}",
        "",
    ]
    if result.warnings:
        lines.append("## Warnings")
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")
    if result.visibility is not None:
        lines.append("## Effective member visibility (read-only, no permission changes)")
        vis = result.visibility
        known = [c for c in vis.channels if c.view is not None]
        unknown = [c for c in vis.channels if c.view is None]
        lines.append(
            f"- Known overwrite data: {len(known)} channels; unknown: {len(unknown)}"
        )
        for c in known[:30]:
            lines.append(
                f"- id={c.channel_id} #{c.channel_name}: view={c.view} send={c.send} "
                f"connect={c.connect} ({c.source})"
            )
        if len(known) > 30:
            lines.append(f"- … {len(known) - 30} more")
        lines.append("")
    if result.resolution is not None:
        lines.append("## Explicit ID resolution")
        for name, cid in sorted(result.resolution.channels.items()):
            lines.append(f"- channel `{name}` → {cid if cid is not None else 'CREATE'}")
        lines.append("")
    lines.append("## Actions")
    for a in result.actions:
        idpart = ""
        if a.channel_id is not None:
            idpart = f" id={a.channel_id}"
        elif a.category_id is not None and a.channel is None:
            idpart = f" id={a.category_id}"
        loc = f"{a.category or ''} / {a.channel or ''}".strip(" /")
        lines.append(f"- `{a.op}` [{a.risk}] {loc}{idpart} — {a.detail}")
    lines.append("")
    lines.append("## Apply gate")
    lines.append("Dry-run only. Grok does not perform live Discord edits.")
    return "\n".join(lines)
