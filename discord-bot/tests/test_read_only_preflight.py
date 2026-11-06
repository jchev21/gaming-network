"""Read-only rollout audit never includes private channel names/messages."""
import json
import unittest
from types import SimpleNamespace

from discord_bot_change_bridge.preflight import (
    TARGET_GUILD_ID,
    make_public_preflight,
)


class FakeChannel:
    def __init__(self, channel_id, name, is_public, *, is_category=False, parent_id=None):
        self.id = channel_id
        self.name = name
        self._public = is_public
        self.type = SimpleNamespace(name="category" if is_category else "text")
        self.category_id = parent_id
        self.topic = "hidden-test-topic" if not is_public else ""
        self.overwrites = {}

    def permissions_for(self, _role):
        return SimpleNamespace(view_channel=self._public)


class FakeGuild:
    id = TARGET_GUILD_ID
    owner_id = 987654321098765432
    default_role = object()

    def __init__(self):
        self.categories = [
            FakeChannel(100, "COMMUNITY", True, is_category=True),
            FakeChannel(200, "SECRET STAFF", False, is_category=True),
        ]
        self.channels = [
            *self.categories,
            FakeChannel(101, "general", True, parent_id=100),
            FakeChannel(201, "do-not-print-private", False, parent_id=200),
        ]
        self.me = SimpleNamespace(guild_permissions=SimpleNamespace(
            manage_channels=False, manage_guild=False,
            send_messages=True, view_channel=True, embed_links=False
        ))


class PreflightTests(unittest.TestCase):
    def test_only_public_inventory_emitted(self):
        record = make_public_preflight(FakeGuild(), bot_id=123)
        serialized = json.dumps(record)
        self.assertIn("general", serialized)
        self.assertIn("COMMUNITY", serialized)
        self.assertNotIn("do-not-print-private", serialized)
        self.assertNotIn("SECRET STAFF", serialized)
        self.assertNotIn("hidden-test-topic", serialized)
        self.assertEqual(record["channel_counts"], {"public": 1, "not_public": 1})
        self.assertEqual(record["category_counts"], {"public": 1, "not_public": 1})
        self.assertFalse(record["bot_permissions"]["manage_channels"])
        self.assertEqual(record["guild_owner_id"], FakeGuild.owner_id)
        self.assertEqual(record["mode"], "READ_ONLY_NO_CHANGES")

    def test_target_guild_only(self):
        bad = FakeGuild()
        bad.id = TARGET_GUILD_ID + 1
        with self.assertRaises(ValueError):
            make_public_preflight(bad)

    def test_unknown_visibility_fail_closed(self):
        guild = FakeGuild()
        # Fake object doesn't support deleting class methods, so replace
        guild.channels[2].permissions_for = lambda role: SimpleNamespace(view_channel=None)
        record = make_public_preflight(guild)
        self.assertEqual(record["channel_counts"], {"public": 0, "not_public": 2})


if __name__ == "__main__":
    unittest.main()
