"""Offline tests: explicit IDs, fail-closed ambiguity, visibility parity (no live Discord)."""
from __future__ import annotations

import unittest

from discord_bot_guild_plan import (
    default_config,
    parse_snapshot,
    SnapshotError,
    resolve_targets,
    AmbiguousMappingError,
    effective_member_visibility,
    build_plan,
    plan_to_markdown,
    GuildSnapshot,
    ChannelRecord,
    CategoryRecord,
    OverwriteRecord,
    TARGET_CATEGORIES,
)

VIEW = 1 << 10
SEND = 1 << 11


class SnapshotParseTests(unittest.TestCase):
    def test_requires_guild_id(self):
        with self.assertRaises(SnapshotError):
            parse_snapshot({"channels": []})

    def test_rejects_duplicate_channel_ids(self):
        with self.assertRaises(SnapshotError):
            parse_snapshot({
                "guild_id": 1,
                "channels": [
                    {"id": 10, "name": "a", "type": "text"},
                    {"id": 10, "name": "b", "type": "text"},
                ],
            })

    def test_parses_explicit_ids(self):
        snap = parse_snapshot({
            "guild_id": 1566290427366080612,
            "channels": [{"id": 111, "name": "welcome", "type": "text", "category_id": 99}],
            "categories": [{"id": 99, "name": "START HERE"}],
        })
        self.assertEqual(snap.guild_id, 1566290427366080612)
        self.assertEqual(snap.channels[0].id, 111)


class ResolveFailClosedTests(unittest.TestCase):
    def test_unique_name_reuses_id(self):
        snap = GuildSnapshot(
            guild_id=1,
            channels=[ChannelRecord(id=42, name="welcome", type="text")],
            categories=[CategoryRecord(id=7, name="START HERE")],
        )
        res = resolve_targets(snap, ["START HERE"], ["welcome"])
        self.assertEqual(res.channels["welcome"], 42)
        self.assertEqual(res.categories["START HERE"], 7)

    def test_ambiguous_channel_name_fails_closed(self):
        snap = GuildSnapshot(
            guild_id=1,
            channels=[
                ChannelRecord(id=1, name="general", type="text"),
                ChannelRecord(id=2, name="general", type="text"),
            ],
        )
        with self.assertRaises(AmbiguousMappingError):
            resolve_targets(snap, [], ["general"], fail_closed=True)

    def test_missing_name_is_create_candidate(self):
        snap = GuildSnapshot(guild_id=1)
        res = resolve_targets(snap, ["START HERE"], ["welcome"])
        self.assertIsNone(res.channels["welcome"])


class VisibilityParityTests(unittest.TestCase):
    def test_reports_without_mutating(self):
        everyone = 100
        snap = GuildSnapshot(
            guild_id=100,
            everyone_role_id=everyone,
            channels=[
                ChannelRecord(
                    id=1, name="welcome", type="text",
                    overwrites=(OverwriteRecord(everyone, "role", allow=VIEW | SEND, deny=0),),
                ),
                ChannelRecord(
                    id=2, name="manager-controls", type="text",
                    overwrites=(OverwriteRecord(everyone, "role", allow=0, deny=VIEW),),
                ),
                ChannelRecord(id=3, name="mystery", type="text"),
            ],
        )
        before = list(snap.channels)
        report = effective_member_visibility(snap)
        self.assertEqual(snap.channels, before)
        by_id = {c.channel_id: c for c in report.channels}
        self.assertTrue(by_id[1].view is True)
        self.assertTrue(by_id[2].view is False)
        self.assertIsNone(by_id[3].view)
        self.assertEqual(report.member_visible_ids(), [1])
        self.assertEqual(report.member_hidden_ids(), [2])

    def test_deny_wins_over_allow(self):
        everyone = 5
        snap = GuildSnapshot(
            guild_id=5,
            everyone_role_id=everyone,
            channels=[
                ChannelRecord(
                    id=9, name="locked", type="text",
                    overwrites=(OverwriteRecord(everyone, "role", allow=VIEW, deny=VIEW),),
                )
            ],
        )
        report = effective_member_visibility(snap)
        self.assertFalse(report.channels[0].view)


class BuildPlanTests(unittest.TestCase):
    def test_guild_id_mismatch_fails(self):
        snap = GuildSnapshot(guild_id=1)
        with self.assertRaises(ValueError):
            build_plan(snap, default_config(guild_id=2))

    def test_reuse_explicit_ids_in_actions(self):
        snap = parse_snapshot({
            "guild_id": 1566290427366080612,
            "categories": [{"id": 50, "name": "START HERE"}],
            "channels": [
                {"id": 501, "name": "welcome", "type": "text", "category_id": 50},
                {"id": 502, "name": "rules", "type": "text", "category_id": 50},
            ],
        })
        plan = build_plan(snap, default_config(guild_id=1566290427366080612))
        reuse = [a for a in plan.actions if a.op == "reuse_channel" and a.channel == "welcome"]
        self.assertEqual(len(reuse), 1)
        self.assertEqual(reuse[0].channel_id, 501)

    def test_ambiguous_plan_fail_closed_action(self):
        snap = GuildSnapshot(
            guild_id=1,
            channels=[
                ChannelRecord(id=1, name="dashboard", type="text"),
                ChannelRecord(id=2, name="dashboard", type="text"),
            ],
        )
        plan = build_plan(snap, default_config(guild_id=1))
        self.assertTrue(any(a.op == "fail_closed" for a in plan.actions))
        self.assertEqual(plan.creates, [])

    def test_markdown_includes_visibility_and_ids(self):
        snap = parse_snapshot({
            "guild_id": 9,
            "channels": [{
                "id": 1, "name": "welcome", "type": "text",
                "overwrites": [{"id": 9, "type": "role", "allow": VIEW, "deny": 0}],
            }],
        })
        plan = build_plan(snap, default_config(guild_id=9))
        md = plan_to_markdown(plan)
        self.assertIn("Effective member visibility", md)
        self.assertIn("id=1", md)


if __name__ == "__main__":
    unittest.main()
