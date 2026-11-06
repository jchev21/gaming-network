"""Safety regressions for offline planner review. No Discord API calls."""
import unittest
from discord_bot_guild_plan import default_config, build_plan, GuildSnapshot, ChannelRecord, CategoryRecord, OverwriteRecord, effective_member_visibility

VIEW = 1 << 10
SEND = 1 << 11


def snapshot(channel, *, category_id=50, category_overwrites=()):
    return GuildSnapshot(
        guild_id=1, everyone_role_id=1,
        categories=[CategoryRecord(id=category_id, name="START HERE", overwrites=category_overwrites)],
        channels=[channel],
    )


def actions(snap):
    return [a.op for a in build_plan(snap, default_config(guild_id=1)).actions if a.channel == "welcome"]


class ReuseSafetyTests(unittest.TestCase):
    def test_unknown_visibility_refused(self):
        ch = ChannelRecord(id=501, name="welcome", type="text", category_id=50)
        self.assertIn("reject_private_reuse", actions(snapshot(ch)))
        self.assertNotIn("reuse_channel", actions(snapshot(ch)))

    def test_wrong_kind_refused(self):
        ch = ChannelRecord(id=501, name="welcome", type="voice", category_id=50,
                           overwrites=(OverwriteRecord(1, "role", allow=VIEW),))
        self.assertIn("reject_private_reuse", actions(snapshot(ch)))

    def test_wrong_parent_refused(self):
        ch = ChannelRecord(id=501, name="welcome", type="text", category_id=99,
                           overwrites=(OverwriteRecord(1, "role", allow=VIEW),))
        self.assertIn("reject_private_reuse", actions(snapshot(ch)))

    def test_verified_kind_and_parent_reused(self):
        ch = ChannelRecord(id=501, name="welcome", type="text", category_id=50,
                           overwrites=(OverwriteRecord(1, "role", allow=VIEW),))
        self.assertIn("reuse_channel", actions(snapshot(ch)))

    def test_unmentioned_view_bit_not_assumed_public_or_private(self):
        ch = ChannelRecord(id=501, name="welcome", type="text", category_id=50,
                           overwrites=(OverwriteRecord(1, "role", allow=SEND),))
        row = effective_member_visibility(snapshot(ch)).channels[0]
        self.assertIsNone(row.view)
        self.assertTrue(row.send)
        self.assertIn("reject_private_reuse", actions(snapshot(ch)))

    def test_channel_send_only_inherits_category_view(self):
        cat_overwrites = (OverwriteRecord(1, "role", allow=VIEW),)
        ch = ChannelRecord(id=501, name="welcome", type="text", category_id=50,
                           overwrites=(OverwriteRecord(1, "role", allow=SEND),))
        snap = snapshot(ch, category_overwrites=cat_overwrites)
        row = effective_member_visibility(snap).channels[0]
        self.assertTrue(row.view)
        self.assertTrue(row.send)
        self.assertIn("reuse_channel", actions(snap))


if __name__ == "__main__":
    unittest.main()
