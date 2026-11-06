from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import PlanConfig, default_config

TARGET_CATEGORIES: dict[str, list[dict[str, Any]]] = {
    "START HERE": [
        {"name": "welcome", "type": "text", "topic": "Welcome — accept Rules Screening, then read #how-to-start"},
        {"name": "rules", "type": "text", "topic": "Community rules summary — Discord Rules Screening is authoritative"},
        {"name": "announcements", "type": "text", "topic": "Official announcements (read-only for members)"},
        {
            "name": "how-to-start",
            "type": "text",
            "topic": "Hub links: /get-started · /hubview · /dashboard · https://x-game-intake-production.up.railway.app/auth/x/start?next=%2Fmy-games",
        },
        {"name": "roles-and-interests", "type": "text", "topic": "Self-roles and interests (prefer Discord native Onboarding)"},
        {"name": "support", "type": "text", "topic": "Ask for help — never post private codes"},
        {"name": "start-here-voice", "type": "voice"},
    ],
    "GAMING NETWORK": [
        {"name": "games-and-events", "type": "text"},
        {"name": "find-a-game", "type": "text"},
        {"name": "live-lobbies", "type": "text", "topic": "Public lobby pointers only — no private join codes"},
        {"name": "tournaments", "type": "text"},
        {"name": "winners-and-highlights", "type": "text"},
        {"name": "game-help", "type": "text"},
        {"name": "gaming-voice", "type": "voice"},
    ],
    "LIVE DASHBOARD": [
        {"name": "dashboard", "type": "text", "topic": "Use /dashboard and /hubview in-server"},
        {"name": "giveaways", "type": "text"},
        {"name": "promo-codes", "type": "text", "topic": "Published codes only"},
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
        {"name": "suggestions", "type": "text"},
    ],
}

COMING_SOON_TOPICS = {
    "education-start": "COMING SOON — Education Center preview (read-only)",
    "course-library": "COMING SOON — Course library preview (read-only)",
    "algo-lab": "COMING SOON — Algo Lab preview (read-only; demo UI only)",
}


@dataclass
class GuildSnapshot:
    guild_id: int
    guild_name: str = ""
    categories: dict = field(default_factory=dict)
    channels: dict = field(default_factory=dict)
    roles: dict = field(default_factory=dict)


@dataclass
class PlanAction:
    op: str
    category: str | None = None
    channel: str | None = None
    channel_type: str | None = None
    detail: str = ""
    risk: str = "low"


@dataclass
class PlanResult:
    guild_id: int
    actions: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def creates(self):
        return [a for a in self.actions if a.op.startswith("create_")]


def build_plan(snapshot: GuildSnapshot, config: PlanConfig | None = None) -> PlanResult:
    cfg = config or default_config()
    result = PlanResult(guild_id=snapshot.guild_id)

    if snapshot.guild_id != cfg.guild_id:
        result.warnings.append(
            f"Snapshot guild_id {snapshot.guild_id} != config guild_id {cfg.guild_id}; "
            "continuing with snapshot id (configurable)."
        )

    existing_channels = {n.lower(): meta for n, meta in snapshot.channels.items()}
    existing_categories = {n.upper(): cid for n, cid in snapshot.categories.items()}

    for cat_name, channels in TARGET_CATEGORIES.items():
        cat_key = cat_name.upper()
        if cat_key not in existing_categories and cat_name not in snapshot.categories:
            result.actions.append(
                PlanAction(
                    op="create_category",
                    category=cat_name,
                    detail="Category missing — will create on apply",
                    risk="medium",
                )
            )
        else:
            result.actions.append(
                PlanAction(op="noop", category=cat_name, detail="Category already present")
            )

        for spec in channels:
            name = spec["name"]
            ctype = spec.get("type", "text")
            low = name.lower()

            if low in {b.lower() for b in cfg.private_name_blocklist}:
                result.actions.append(
                    PlanAction(
                        op="skip_private",
                        category=cat_name,
                        channel=name,
                        detail="Blocklisted private name — planner will not open or alter",
                        risk="high",
                    )
                )
                continue

            if low in existing_channels:
                meta = existing_channels[low]
                if spec.get("coming_soon") and cfg.lock_coming_soon:
                    topic = COMING_SOON_TOPICS.get(low, "COMING SOON — preview (read-only)")
                    current_topic = (meta.get("topic") or "")
                    if "COMING SOON" not in current_topic.upper():
                        result.actions.append(
                            PlanAction(
                                op="set_topic",
                                category=cat_name,
                                channel=name,
                                detail=f"Set topic to {topic!r}",
                                risk="low",
                            )
                        )
                    result.actions.append(
                        PlanAction(
                            op="deny_send_everyone",
                            category=cat_name,
                            channel=name,
                            detail="Ensure @everyone cannot send (Coming Soon read-only)",
                            risk="medium",
                        )
                    )
                else:
                    result.actions.append(
                        PlanAction(
                            op="noop",
                            category=cat_name,
                            channel=name,
                            channel_type=ctype,
                            detail="Channel exists — preserve",
                        )
                    )
            else:
                if not cfg.ensure_category_voice and ctype == "voice":
                    continue
                detail = "Create missing channel"
                if spec.get("coming_soon"):
                    detail += " + Coming Soon topic + deny send @everyone"
                result.actions.append(
                    PlanAction(
                        op="create_channel",
                        category=cat_name,
                        channel=name,
                        channel_type=ctype,
                        detail=detail,
                        risk="medium" if ctype == "voice" else "low",
                    )
                )
                if spec.get("coming_soon") and cfg.lock_coming_soon:
                    result.actions.append(
                        PlanAction(
                            op="set_topic",
                            category=cat_name,
                            channel=name,
                            detail=COMING_SOON_TOPICS.get(low, "COMING SOON"),
                            risk="low",
                        )
                    )
                    result.actions.append(
                        PlanAction(
                            op="deny_send_everyone",
                            category=cat_name,
                            channel=name,
                            detail="Coming Soon read-only for @everyone",
                            risk="medium",
                        )
                    )

    if not snapshot.channels and not snapshot.categories:
        result.warnings.append(
            "Empty snapshot — plan lists full additive creates. "
            "Run /channelids or export_channel_ids before apply."
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
    lines.append("## Actions")
    for a in result.actions:
        loc = f"{a.category or ''} / {a.channel or ''}".strip(" /")
        lines.append(f"- `{a.op}` [{a.risk}] {loc} — {a.detail}")
    lines.append("")
    lines.append("## Apply gate")
    lines.append("Dry-run only until owner approves and an operator runs apply with live bot credentials.")
    lines.append("Grok does not perform live Discord edits.")
    return "\n".join(lines)
