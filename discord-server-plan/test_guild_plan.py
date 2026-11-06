"""Offline tests for idempotent guild structure planner."""
from __future__ import annotations

import unittest

from discord_bot_guild_plan import (
    GuildSnapshot,
    build_plan,
    plan_to_markdown,
    default_config,
    TARGET_CATEGORIES,
    COMING_SOON_TOPICS,
)


class GuildPlanTests(unittest.TestCase):
    def test_empty_snapshot_warns_and_plans_creates(self):
        snap = GuildSnapshot(guild_id=1566290427366080612)
        plan = build_plan(snap)
        self.assertTrue(any("Empty snapshot" in w for w in plan.warnings))
        self.assertGreater(len(plan.creates), 10)

    def test_idempotent_when_all_present(self):
        channels = {}
        categories = {}
        for cat, specs in TARGET_CATEGORIES.items():
            categories[cat] = hash(cat) % 10_000_000
            for s in specs:
                channels[s["name"]] = {
                    "id": hash(s["name"]) % 10_000_000,
                    "type": s.get("type", "text"),
                    "category": cat,
                    "topic": COMING_SOON_TOPICS.get(s["name"], ""),
                }
        snap = GuildSnapshot(
            guild_id=1566290427366080612,
            categories=categories,
            channels=channels,
        )
        plan = build_plan(snap)
        self.assertEqual(plan.creates, [])

    def test_coming_soon_channels_get_readonly_actions_when_missing(self):
        snap = GuildSnapshot(guild_id=1566290427366080612)
        plan = build_plan(snap)
        algo = [a for a in plan.actions if a.channel == "algo-lab"]
        ops = {a.op for a in algo}
        self.assertIn("create_channel", ops)
        self.assertIn("set_topic", ops)
        self.assertIn("deny_send_everyone", ops)

    def test_one_voice_per_public_category_in_template(self):
        for cat, specs in TARGET_CATEGORIES.items():
            if cat in default_config().public_category_names and cat != "BOT COMMANDS":
                voices = [s for s in specs if s.get("type") == "voice"]
                self.assertEqual(len(voices), 1, f"{cat} should have exactly one voice channel")

    def test_markdown_render(self):
        plan = build_plan(GuildSnapshot(guild_id=42), default_config(guild_id=42))
        md = plan_to_markdown(plan)
        self.assertIn("guild_id=42", md)
        self.assertIn("Dry-run only", md)

    def test_configurable_guild_id(self):
        plan = build_plan(GuildSnapshot(guild_id=99), default_config(guild_id=1))
        self.assertTrue(any("99" in w and "1" in w for w in plan.warnings))


if __name__ == "__main__":
        unittest.main()
