"""Offline parity tests: one voice/category, reject private reuse, category vs effective."""
from __future__ import annotations

import unittest

from discord_bot_guild_plan import (
    default_config,
    build_plan,
    effective_member_visibility,
    GuildSnapshot,
    ChannelRecord,
    CategoryRecord,
    OverwriteRecord,
    voice_channels_per_category,
    assert_one_voice_per_public_category,
    is_private_channel_record,
)
from discord_bot_guild_plan.visibility import ChannelVisibility

VIEW = 1 << 10
SEND = 1 << 11


class OneVoicePerCategoryTests(unittest.TestCase):
    def test_template_has_exactly_one_voice_per_public_category(self):
        assert_one_voice_per_public_category()
        voices = voice_channels_per_category()
        for cat in (
            "START HERE", "GAMING NETWORK", "LIVE DASHBOARD",
            "EDUCATION", "AFFILIATES & PARTNERS", "COMMUNITY",
        ):
            self.assertEqual(len(voices[cat]), 1, cat)

    def test_build_plan_enforces_template_invariant(self):
        plan = build_plan(GuildSnapshot(guild_id=1), default_config(guild_id=1))
        voice_creates = [
            a for a in plan.actions
            if a.op == "create_channel" and a.channel_type == "voice"
        ]
        self.assertGreaterEqual(len(voice_creates), 6)


class RejectPrivateReuseTests(unittest.TestCase):
    def test_blocklisted_name_is_private(self):
        meta = ChannelRecord(id=9, name="manager-controls", type="text")
        self.assertTrue(is_private_channel_record(meta, None, {"manager-controls"}))

    def test_hidden_from_everyone_is_private(self):
        meta = ChannelRecord(id=3, name="welcome", type="text")
        row = ChannelVisibility(
            channel_id=3, channel_name="welcome", channel_type="text",
            view=False, send=False, connect=None, source="channel_overwrite",
        )
        self.assertTrue(is_private_channel_record(meta, row, set()))

    def test_plan_rejects_reuse_when_channel_hidden(self):
        everyone = 100
        snap = GuildSnapshot(
            guild_id=100,
            everyone_role_id=everyone,
            categories=[CategoryRecord(id=10, name="START HERE")],
            channels=[
                ChannelRecord(
                    id=501, name="welcome", type="text", category_id=10,
                    overwrites=(OverwriteRecord(everyone, "role", allow=0, deny=VIEW),),
                )
            ],
        )
        plan = build_plan(snap, default_config(guild_id=100))
        rejects = [a for a in plan.actions if a.op == "reject_private_reuse"]
        self.assertTrue(any(a.channel == "welcome" and a.channel_id == 501 for a in rejects))
        self.assertEqual(
            [a for a in plan.actions if a.op == "reuse_channel" and a.channel == "welcome"],
            [],
        )

    def test_plan_reuses_when_member_visible(self):
        everyone = 100
        snap = GuildSnapshot(
            guild_id=100,
            everyone_role_id=everyone,
            categories=[CategoryRecord(id=10, name="START HERE")],
            channels=[
                ChannelRecord(
                    id=501, name="welcome", type="text", category_id=10,
                    overwrites=(OverwriteRecord(everyone, "role", allow=VIEW | SEND, deny=0),),
                )
            ],
        )
        plan = build_plan(snap, default_config(guild_id=100))
        self.assertEqual(
            len([a for a in plan.actions if a.op == "reuse_channel" and a.channel_id == 501]),
            1,
        )


class CategoryVsEffectivePermissionTests(unittest.TestCase):
    def test_category_overwrite_used_when_channel_has_none(self):
        everyone = 7
        cat = CategoryRecord(
            id=50, name="EDUCATION",
            overwrites=(OverwriteRecord(everyone, "role", allow=VIEW, deny=SEND),),
        )
        ch = ChannelRecord(id=1, name="algo-lab", type="text", category_id=50)
        snap = GuildSnapshot(
            guild_id=7, everyone_role_id=everyone, categories=[cat], channels=[ch]
        )
        row = effective_member_visibility(snap).channels[0]
        self.assertEqual(row.source, "category_overwrite")
        self.assertTrue(row.category_view is True)
        self.assertTrue(row.category_send is False)
        self.assertTrue(row.view is True)
        self.assertTrue(row.send is False)
        self.assertIsNone(row.channel_view)

    def test_channel_overwrite_overrides_category(self):
        everyone = 7
        cat = CategoryRecord(
            id=50, name="EDUCATION",
            overwrites=(OverwriteRecord(everyone, "role", allow=VIEW | SEND, deny=0),),
        )
        ch = ChannelRecord(
            id=1, name="algo-lab", type="text", category_id=50,
            overwrites=(OverwriteRecord(everyone, "role", allow=0, deny=VIEW),),
        )
        snap = GuildSnapshot(
            guild_id=7, everyone_role_id=everyone, categories=[cat], channels=[ch]
        )
        row = effective_member_visibility(snap).channels[0]
        self.assertEqual(row.source, "channel_overwrite")
        self.assertTrue(row.category_view is True)
        self.assertTrue(row.channel_view is False)
        self.assertTrue(row.view is False)

    def test_unknown_without_overwrites(self):
        snap = GuildSnapshot(
            guild_id=1, everyone_role_id=1,
            channels=[ChannelRecord(id=9, name="general", type="text")],
        )
        row = effective_member_visibility(snap).channels[0]
        self.assertEqual(row.source, "unknown_default_deny_closed")
        self.assertIsNone(row.view)
        self.assertIsNone(row.category_view)
        self.assertIsNone(row.channel_view)


if __name__ == "__main__":
    unittest.main()
