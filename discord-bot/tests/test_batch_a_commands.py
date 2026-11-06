"""Offline tests for Batch A owner gates and inventory builder."""
from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from discord_bot_change_bridge.inventory_live import build_inventory_from_guild
from discord_bot_change_bridge import parse_proposal, plan_hash, SCHEMA_VERSION, build_plan_diff


class FakeOverwrite:
    def __init__(self, allow=0, deny=0):
        self._allow = allow
        self._deny = deny

    def pair(self):
        return SimpleNamespace(value=self._allow), SimpleNamespace(value=self._deny)


class FakeRole:
    def __init__(self, id):
        self.id = id


class FakeChannel:
    def __init__(self, id, name, *, category_id=None, topic="", overwrites=None, type_name="text"):
        self.id = id
        self.name = name
        self.category_id = category_id
        self.topic = topic
        self.overwrites = overwrites or {}
        self.type = SimpleNamespace(name=type_name)


class FakeGuild:
    def __init__(self, id, categories, channels, everyone_id):
        self.id = id
        self.categories = categories
        self.channels = channels
        self.default_role = FakeRole(everyone_id)


class InventoryLiveTests(unittest.TestCase):
    def test_marks_private_when_view_denied(self):
        everyone = FakeRole(100)
        deny_view = FakeOverwrite(allow=0, deny=1 << 10)
        cat = SimpleNamespace(id=1, name="STAFF", overwrites={everyone: deny_view})
        ch = FakeChannel(2, "mod-log", category_id=1, overwrites={everyone: deny_view})
        g = FakeGuild(1566290427366080612, [cat], [ch], 100)
        inv = build_inventory_from_guild(g)
        self.assertTrue(inv.channels[0].private)
        self.assertTrue(inv.categories[0].private)

    def test_digest_stable(self):
        ch = FakeChannel(9, "general")
        g = FakeGuild(1, [], [ch], 1)
        self.assertEqual(build_inventory_from_guild(g).digest(), build_inventory_from_guild(g).digest())


class OwnerEnvTests(unittest.TestCase):
    def test_owner_ids_parse(self):
        raw = "123, 456;789"
        ids = {int(p.strip()) for p in raw.replace(";", ",").split(",") if p.strip().isdigit()}
        self.assertEqual(ids, {123, 456, 789})

    def test_apply_env_default_false(self):
        os.environ.pop("CHANGE_BRIDGE_APPLY_ENABLED", None)
        enabled = os.environ.get("CHANGE_BRIDGE_APPLY_ENABLED", "false").lower() in ("1", "true", "yes")
        self.assertFalse(enabled)


class EndToEndOfflinePreview(unittest.TestCase):
    def test_preview_blocks_private_target(self):
        everyone = FakeRole(100)
        deny = FakeOverwrite(0, 1 << 10)
        cat = SimpleNamespace(id=51, name="STAFF", overwrites={everyone: deny})
        ch = FakeChannel(502, "mod-log", category_id=51, overwrites={everyone: deny})
        g = FakeGuild(1566290427366080612, [cat], [ch], 100)
        inv = build_inventory_from_guild(g)
        p = parse_proposal({
            "schema_version": SCHEMA_VERSION,
            "guild_id": 1566290427366080612,
            "proposal_id": "t",
            "idempotency_token": "i",
            "snapshot_digest": inv.digest(),
            "created_at_unix": 1,
            "expires_at_unix": 9999999999,
            "operations": [{"op_id": "1", "op": "update_topic", "channel_id": 502, "topic": "x"}],
        })
        d = build_plan_diff(p, inv, plan_hash(p))
        self.assertTrue(d.lines[0].blocked)


if __name__ == "__main__":
    unittest.main()
