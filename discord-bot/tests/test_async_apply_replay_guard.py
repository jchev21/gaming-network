"""Crash-safety regression: Discord operations must never replay implicitly."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from discord_bot_change_bridge import SCHEMA_VERSION, parse_proposal, approve_plan, Journal
from discord_bot_change_bridge.async_apply import apply_approved_plan_async
from discord_bot_change_bridge.diff import GuildInventory


GUILD = 1566290427366080612


class FakeMutator:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    async def create_category_async(self, name):
        self.calls += 1
        if self.fail:
            raise RuntimeError("Discord accepted the request, but receipt was lost")
        return 7654321


def make_plan(token):
    inventory = GuildInventory(guild_id=GUILD, categories=[], channels=[])
    proposal = parse_proposal({
        "schema_version": SCHEMA_VERSION,
        "guild_id": GUILD,
        "proposal_id": "safe-preview-1",
        "idempotency_token": token,
        "snapshot_digest": inventory.digest(),
        "created_at_unix": 1,
        "expires_at_unix": 9999999999,
        "operations": [{"op_id": "one", "op": "create_category", "name": "PUBLIC TEST"}],
    })
    approval = approve_plan(
        proposal, owner_user_id=999, owner_allowlist={999}, now_unix=10
    )
    return inventory, proposal, approval


class CrashReplayGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_failure_never_replays_same_idempotency_token(self):
        inv, proposal, approval = make_plan("crash-guard-1")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "journal.json"
            mutator = FakeMutator(fail=True)
            first = await apply_approved_plan_async(
                proposal, approval, inv, mutator, Journal(path), now_unix=11
            )
            self.assertFalse(first.ok)
            self.assertEqual(mutator.calls, 1)
            # Fresh process / journal instance simulates a restart.
            restart = await apply_approved_plan_async(
                proposal, approval, inv, mutator, Journal(path), now_unix=12
            )
            self.assertFalse(restart.ok)
            self.assertIn("manual reconciliation", restart.error)
            self.assertEqual(mutator.calls, 1)

    async def test_completed_operation_still_skips_duplicate(self):
        inv, proposal, approval = make_plan("crash-guard-2")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "journal.json"
            mutator = FakeMutator()
            first = await apply_approved_plan_async(
                proposal, approval, inv, mutator, Journal(path), now_unix=11
            )
            self.assertTrue(first.ok, first.error)
            self.assertEqual(mutator.calls, 1)
            second = await apply_approved_plan_async(
                proposal, approval, inv, mutator, Journal(path), now_unix=12
            )
            self.assertTrue(second.skipped_idempotent)
            self.assertEqual(mutator.calls, 1)

    async def test_disabled_apply_never_writes_attempt(self):
        inv, proposal, approval = make_plan("crash-guard-3")
        with tempfile.TemporaryDirectory() as temp:
            journal = Journal(Path(temp) / "journal.json")
            mutator = FakeMutator()
            result = await apply_approved_plan_async(
                proposal, approval, inv, mutator, journal,
                now_unix=11, apply_enabled=False
            )
            self.assertFalse(result.ok)
            self.assertEqual(mutator.calls, 0)
            self.assertFalse(any(e["kind"] == "operation_attempt" for e in journal.entries()))


if __name__ == "__main__":
    unittest.main()
