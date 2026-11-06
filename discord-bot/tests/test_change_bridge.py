"""Offline tests for AI→Discord change bridge. No Discord network. No tokens."""
from __future__ import annotations

import unittest
from pathlib import Path
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from discord_bot_change_bridge import (
    SCHEMA_VERSION,
    parse_proposal,
    plan_hash,
    ProposalError,
    build_plan_diff,
    approve_plan,
    verify_approval,
    ApprovalError,
    Journal,
    apply_approved_plan,
    rollback_preview,
)
from discord_bot_change_bridge.diff import GuildInventory, ChannelSnap, CategorySnap


def _base_proposal(**over):
    data = {
        "schema_version": SCHEMA_VERSION,
        "guild_id": 1566290427366080612,
        "proposal_id": "prop-1",
        "idempotency_token": "idem-abc",
        "snapshot_digest": "deadbeef",
        "created_at_unix": 1_700_000_000,
        "expires_at_unix": 1_800_000_000,
        "requester_note": "Create EDUCATION videos channel",
        "operations": [
            {"op_id": "op1", "op": "create_category", "name": "EDUCATION"},
            {
                "op_id": "op2",
                "op": "create_text_channel",
                "name": "videos",
                "parent_category_id": 50,
                "topic": "Member-visible education videos",
            },
        ],
    }
    data.update(over)
    return data


class MockMutator:
    def __init__(self):
        self.calls = []
        self._next = 1000

    def create_category(self, name: str) -> int:
        self.calls.append(("create_category", name))
        self._next += 1
        return self._next

    def create_text_channel(self, name, parent_category_id, topic):
        self.calls.append(("create_text_channel", name, parent_category_id, topic))
        self._next += 1
        return self._next

    def rename_channel(self, channel_id, name):
        self.calls.append(("rename_channel", channel_id, name))

    def update_topic(self, channel_id, topic):
        self.calls.append(("update_topic", channel_id, topic))

    def move_channel(self, channel_id, parent_category_id):
        self.calls.append(("move_channel", channel_id, parent_category_id))


class SchemaTests(unittest.TestCase):
    def test_parses_valid_proposal(self):
        p = parse_proposal(_base_proposal())
        self.assertEqual(p.guild_id, 1566290427366080612)
        self.assertEqual(len(p.operations), 2)
        self.assertEqual(len(plan_hash(p)), 64)

    def test_rejects_unknown_top_level_key(self):
        raw = _base_proposal()
        raw["evil_script"] = "rm -rf /"
        with self.assertRaises(ProposalError):
            parse_proposal(raw)

    def test_rejects_unknown_op(self):
        raw = _base_proposal()
        raw["operations"] = [{"op_id": "x", "op": "delete_channel", "channel_id": 1}]
        with self.assertRaises(ProposalError):
            parse_proposal(raw)

    def test_rejects_bad_channel_name(self):
        raw = _base_proposal()
        raw["operations"] = [{"op_id": "x", "op": "create_text_channel", "name": "NOT VALID"}]
        with self.assertRaises(ProposalError):
            parse_proposal(raw)

    def test_plan_hash_stable(self):
        self.assertEqual(plan_hash(parse_proposal(_base_proposal())), plan_hash(parse_proposal(_base_proposal())))


class DiffTests(unittest.TestCase):
    def setUp(self):
        self.inv = GuildInventory(
            guild_id=1566290427366080612,
            categories=[CategorySnap(50, "START HERE"), CategorySnap(51, "STAFF", private=True)],
            channels=[
                ChannelSnap(501, "welcome", "text", category_id=50, topic="hi"),
                ChannelSnap(502, "mod-log", "text", category_id=51, private=True),
            ],
            protected_channel_ids=frozenset({501}),
        )
        self.digest = self.inv.digest()

    def test_stale_snapshot_flagged(self):
        p = parse_proposal(_base_proposal(snapshot_digest="wrong"))
        d = build_plan_diff(p, self.inv, plan_hash(p))
        self.assertTrue(d.stale and d.blocked)

    def test_rename_protected_blocked(self):
        p = parse_proposal(_base_proposal(
            snapshot_digest=self.digest,
            operations=[{"op_id": "r1", "op": "rename_channel", "channel_id": 501, "name": "welcome-renamed"}],
        ))
        d = build_plan_diff(p, self.inv, plan_hash(p))
        self.assertTrue(d.lines[0].blocked)
        self.assertIn("protected", d.lines[0].block_reason)

    def test_private_channel_mutate_blocked(self):
        p = parse_proposal(_base_proposal(
            snapshot_digest=self.digest,
            operations=[{"op_id": "t1", "op": "update_topic", "channel_id": 502, "topic": "x"}],
        ))
        self.assertTrue(build_plan_diff(p, self.inv, plan_hash(p)).lines[0].blocked)

    def test_create_under_private_category_blocked(self):
        p = parse_proposal(_base_proposal(
            snapshot_digest=self.digest,
            operations=[{"op_id": "c1", "op": "create_text_channel", "name": "leaked", "parent_category_id": 51}],
        ))
        self.assertTrue(build_plan_diff(p, self.inv, plan_hash(p)).lines[0].blocked)

    def test_happy_rename_diff(self):
        inv = GuildInventory(
            guild_id=1,
            channels=[ChannelSnap(9, "general", "text", category_id=2)],
            categories=[CategorySnap(2, "COMMUNITY")],
        )
        p = parse_proposal({
            "schema_version": SCHEMA_VERSION, "guild_id": 1, "proposal_id": "p",
            "idempotency_token": "i", "snapshot_digest": inv.digest(),
            "created_at_unix": 10, "expires_at_unix": 9999999999,
            "operations": [{"op_id": "1", "op": "rename_channel", "channel_id": 9, "name": "lounge"}],
        })
        d = build_plan_diff(p, inv, plan_hash(p))
        self.assertFalse(d.blocked)
        self.assertEqual(d.lines[0].before["name"], "general")


class ApprovalTests(unittest.TestCase):
    def test_non_owner_rejected(self):
        with self.assertRaises(ApprovalError):
            approve_plan(parse_proposal(_base_proposal()), owner_user_id=1, owner_allowlist={99})

    def test_expired_proposal_rejected(self):
        p = parse_proposal(_base_proposal(created_at_unix=1, expires_at_unix=2))
        with self.assertRaises(ApprovalError):
            approve_plan(p, owner_user_id=5, owner_allowlist={5}, now_unix=10)

    def test_hash_mismatch_on_verify(self):
        p = parse_proposal(_base_proposal())
        a = approve_plan(p, owner_user_id=5, owner_allowlist={5}, now_unix=1_700_000_100)
        with self.assertRaises(ApprovalError):
            verify_approval(a, parse_proposal(_base_proposal(requester_note="tampered")), now_unix=1_700_000_100)


class ApplyJournalTests(unittest.TestCase):
    def test_apply_once_idempotent(self):
        inv = GuildInventory(
            guild_id=1,
            categories=[CategorySnap(2, "COMMUNITY")],
            channels=[ChannelSnap(9, "general", "text", category_id=2)],
        )
        p = parse_proposal({
            "schema_version": SCHEMA_VERSION, "guild_id": 1, "proposal_id": "p2",
            "idempotency_token": "once-1", "snapshot_digest": inv.digest(),
            "created_at_unix": 10, "expires_at_unix": 9999999999,
            "operations": [{"op_id": "1", "op": "update_topic", "channel_id": 9, "topic": "hello"}],
        })
        a = approve_plan(p, owner_user_id=7, owner_allowlist={7}, now_unix=100)
        with tempfile.TemporaryDirectory() as td:
            j = Journal(Path(td) / "journal.json")
            m = MockMutator()
            r1 = apply_approved_plan(p, a, inv, m, j, now_unix=100)
            self.assertTrue(r1.ok)
            self.assertEqual(m.calls, [("update_topic", 9, "hello")])
            r2 = apply_approved_plan(p, a, inv, m, j, now_unix=100)
            self.assertTrue(r2.ok and r2.skipped_idempotent)
            self.assertEqual(len(m.calls), 1)

    def test_unauthorized_never_approves(self):
        inv = GuildInventory(guild_id=1, channels=[ChannelSnap(9, "general", "text")])
        p = parse_proposal({
            "schema_version": SCHEMA_VERSION, "guild_id": 1, "proposal_id": "p3",
            "idempotency_token": "x", "snapshot_digest": inv.digest(),
            "created_at_unix": 10, "expires_at_unix": 9999999999,
            "operations": [{"op_id": "1", "op": "update_topic", "channel_id": 9, "topic": "t"}],
        })
        with self.assertRaises(ApprovalError):
            approve_plan(p, owner_user_id=1, owner_allowlist={2})

    def test_rollback_preview_no_delete(self):
        inv = GuildInventory(
            guild_id=1,
            categories=[CategorySnap(2, "COMMUNITY")],
            channels=[ChannelSnap(9, "general", "text", category_id=2, topic="old")],
        )
        p = parse_proposal({
            "schema_version": SCHEMA_VERSION, "guild_id": 1, "proposal_id": "p4",
            "idempotency_token": "y", "snapshot_digest": inv.digest(),
            "created_at_unix": 10, "expires_at_unix": 9999999999,
            "operations": [
                {"op_id": "1", "op": "update_topic", "channel_id": 9, "topic": "new"},
                {"op_id": "2", "op": "create_text_channel", "name": "clips", "parent_category_id": 2},
            ],
        })
        rb = rollback_preview(build_plan_diff(p, inv, plan_hash(p)))
        self.assertTrue(any(r["op"] == "update_topic" for r in rb.reversible))
        self.assertTrue(any("cannot be auto-deleted" in n for n in rb.irreversible_notes))


class MoveRenameTests(unittest.TestCase):
    def test_move_and_rename_apply(self):
        inv = GuildInventory(
            guild_id=42,
            categories=[CategorySnap(1, "A"), CategorySnap(2, "B")],
            channels=[ChannelSnap(10, "general", "text", category_id=1)],
        )
        p = parse_proposal({
            "schema_version": SCHEMA_VERSION, "guild_id": 42, "proposal_id": "mv",
            "idempotency_token": "mv-1", "snapshot_digest": inv.digest(),
            "created_at_unix": 1, "expires_at_unix": 9999999999,
            "operations": [
                {"op_id": "a", "op": "rename_channel", "channel_id": 10, "name": "lounge"},
                {"op_id": "b", "op": "move_channel", "channel_id": 10, "parent_category_id": 2},
            ],
        })
        a = approve_plan(p, owner_user_id=3, owner_allowlist={3}, now_unix=10)
        with tempfile.TemporaryDirectory() as td:
            j = Journal(Path(td) / "j.json")
            m = MockMutator()
            r = apply_approved_plan(p, a, inv, m, j, now_unix=10)
            self.assertTrue(r.ok, r.error)
            self.assertEqual(m.calls, [("rename_channel", 10, "lounge"), ("move_channel", 10, 2)])


if __name__ == "__main__":
    unittest.main()
