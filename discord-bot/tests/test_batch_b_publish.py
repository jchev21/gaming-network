"""Batch B: publish_message schema, diff gates, idempotent apply."""
from __future__ import annotations
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from discord_bot_change_bridge import (
    SCHEMA_VERSION, parse_proposal, plan_hash, ProposalError,
    build_plan_diff, approve_plan, apply_approved_plan, Journal,
)
from discord_bot_change_bridge.diff import GuildInventory, ChannelSnap, CategorySnap


class MockMutator:
    def __init__(self):
        self.calls = []
        self._mid = 5000

    def create_category(self, name): self.calls.append(("create_category", name)); return 1
    def create_text_channel(self, *a): self.calls.append(("create_text", a)); return 2
    def rename_channel(self, *a): self.calls.append(("rename", a))
    def update_topic(self, *a): self.calls.append(("topic", a))
    def move_channel(self, *a): self.calls.append(("move", a))
    def publish_message(self, channel_id, content, embed_title, embed_description, embed_color):
        self._mid += 1
        self.calls.append(("publish", channel_id, content, embed_title))
        return self._mid


def _inv():
    return GuildInventory(
        guild_id=1566290427366080612,
        categories=[CategorySnap(10, "START HERE")],
        channels=[
            ChannelSnap(100, "announcements", "text", category_id=10),
            ChannelSnap(101, "staff-only", "text", category_id=10, private=True),
        ],
    )


class PublishSchemaTests(unittest.TestCase):
    def test_parse_publish(self):
        inv = _inv()
        p = parse_proposal({
            "schema_version": SCHEMA_VERSION, "guild_id": 1566290427366080612,
            "proposal_id": "ann-1", "idempotency_token": "pub-idem-1",
            "snapshot_digest": inv.digest(), "created_at_unix": 1, "expires_at_unix": 9999999999,
            "operations": [{"op_id": "p1", "op": "publish_message", "channel_id": 100,
                            "content": "Hello members", "embed_title": "Launch",
                            "embed_description": "We are live"}],
        })
        self.assertEqual(p.operations[0].op, "publish_message")
        self.assertEqual(len(plan_hash(p)), 64)

    def test_rejects_empty_publish(self):
        with self.assertRaises(ProposalError):
            parse_proposal({
                "schema_version": SCHEMA_VERSION, "guild_id": 1, "proposal_id": "x",
                "idempotency_token": "y", "snapshot_digest": "z",
                "created_at_unix": 1, "expires_at_unix": 9,
                "operations": [{"op_id": "1", "op": "publish_message", "channel_id": 1}],
            })


class PublishDiffTests(unittest.TestCase):
    def test_blocks_private_channel(self):
        inv = _inv()
        p = parse_proposal({
            "schema_version": SCHEMA_VERSION, "guild_id": 1566290427366080612,
            "proposal_id": "a", "idempotency_token": "b", "snapshot_digest": inv.digest(),
            "created_at_unix": 1, "expires_at_unix": 9999999999,
            "operations": [{"op_id": "1", "op": "publish_message", "channel_id": 101, "content": "leak"}],
        })
        self.assertTrue(build_plan_diff(p, inv, plan_hash(p)).lines[0].blocked)

    def test_public_ok(self):
        inv = _inv()
        p = parse_proposal({
            "schema_version": SCHEMA_VERSION, "guild_id": 1566290427366080612,
            "proposal_id": "a", "idempotency_token": "b", "snapshot_digest": inv.digest(),
            "created_at_unix": 1, "expires_at_unix": 9999999999,
            "operations": [{"op_id": "1", "op": "publish_message", "channel_id": 100, "content": "ok"}],
        })
        self.assertFalse(build_plan_diff(p, inv, plan_hash(p)).blocked)


class PublishApplyTests(unittest.TestCase):
    def test_apply_once_idempotent(self):
        inv = _inv()
        p = parse_proposal({
            "schema_version": SCHEMA_VERSION, "guild_id": 1566290427366080612,
            "proposal_id": "ann-2", "idempotency_token": "pub-once",
            "snapshot_digest": inv.digest(), "created_at_unix": 1, "expires_at_unix": 9999999999,
            "operations": [{"op_id": "1", "op": "publish_message", "channel_id": 100, "content": "once"}],
        })
        a = approve_plan(p, owner_user_id=9, owner_allowlist={9}, now_unix=10)
        with tempfile.TemporaryDirectory() as td:
            j = Journal(Path(td) / "j.json")
            m = MockMutator()
            r1 = apply_approved_plan(p, a, inv, m, j, now_unix=10)
            self.assertTrue(r1.ok, r1.error)
            self.assertEqual(m.calls[0][0], "publish")
            r2 = apply_approved_plan(p, a, inv, m, j, now_unix=10)
            self.assertTrue(r2.skipped_idempotent)
            self.assertEqual(len(m.calls), 1)


if __name__ == "__main__":
    unittest.main()
