"""Batch 5 regression tests — security blockers for issue #78 Member grant."""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from member_grant_api import (
    BotCapability, DurableStoreError, GrantRequest, MemberSnapshot, ReplayStore,
    RoleSnapshot, abort_grant_attempt, confirm_grant, evaluate_grant, sign_request,
    TARGET_GUILD_ID,
)

SECRET = "test-hmac-secret-at-least-32-bytes-long!!"
GUILD = str(TARGET_GUILD_ID)
DISCORD = "2000000000000000001"
XID = "1000000000000000001"
RULES = RoleSnapshot("3000000000000000001", "Rules Accepted", 5)
MEMBER = RoleSnapshot("3000000000000000002", "Member", 4)
BOT = BotCapability(manage_roles=True, top_role_position=20)


def make_req(*, nonce="nonce-abcdefghijklmnopqrstuvwxyz", ts=None, sig=None, **over):
    timestamp = str(ts if ts is not None else int(time.time()))
    idem = over.pop("idempotency_key", "idem-" + "a" * 32)
    discord = over.pop("discord_user_id", DISCORD)
    xid = over.pop("x_user_id", XID)
    guild = over.pop("guild_id", GUILD)
    signature = sig if sig is not None else sign_request(
        SECRET, timestamp, nonce, idem, discord, xid, guild,
    )
    return GrantRequest(
        discord_user_id=discord, x_user_id=xid, guild_id=guild,
        idempotency_key=idem, timestamp=timestamp, nonce=nonce, signature=signature,
    )


def screened(roles=None):
    return MemberSnapshot(user_id=DISCORD, pending=False, role_ids=roles or [RULES.role_id])


class SecurityBlockerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "journal.json"
        self.store = ReplayStore(self.path, now=time.time, require_persist=True)

    def tearDown(self):
        self.tmp.cleanup()

    def eval(self, req, **kwargs):
        defaults = dict(
            store=self.store, member=screened(), rules_role=RULES,
            member_role=MEMBER, bot=BOT, secret=SECRET, enabled=True, now=time.time(),
        )
        defaults.update(kwargs)
        return evaluate_grant(req, **defaults)

    def test_disabled(self):
        self.assertEqual(self.eval(make_req(), enabled=False).code, "MEMBER_GRANT_DISABLED")

    def test_bad_sig(self):
        self.assertEqual(self.eval(make_req(sig="0" * 64)).code, "INVALID_SIGNATURE")

    def test_pending(self):
        m = MemberSnapshot(user_id=DISCORD, pending=True, role_ids=[RULES.role_id])
        self.assertEqual(self.eval(make_req(), member=m).code, "DISCORD_RULES_NOT_ACCEPTED")

    def test_missing_rules(self):
        m = MemberSnapshot(user_id=DISCORD, pending=False, role_ids=[])
        self.assertEqual(self.eval(make_req(), member=m).code, "MISSING_RULES_ACCEPTED_ROLE")

    def test_x_alone_no_rules(self):
        m = MemberSnapshot(user_id=DISCORD, pending=False, role_ids=[])
        self.assertFalse(self.eval(make_req(), member=m).ok)

    def test_failed_request_does_not_bind(self):
        r = self.eval(make_req(), member=None)
        self.assertEqual(r.code, "MEMBER_NOT_IN_GUILD")
        self.assertEqual(self.store._bindings, {})
        r2 = self.eval(make_req(nonce="nonce-legit-abcdefghijklmnopq"))
        self.assertTrue(r2.ok)
        self.assertEqual(self.store._bindings, {}, "authorization alone must not bind")

    def test_missing_rules_does_not_bind(self):
        m = MemberSnapshot(user_id=DISCORD, pending=False, role_ids=[])
        self.eval(make_req(), member=m)
        self.assertEqual(self.store._bindings, {})

    def test_authorize_does_not_write_success_receipt(self):
        r = self.eval(make_req())
        self.assertEqual(r.code, "GRANT_AUTHORIZED")
        self.assertTrue(r.needs_discord_apply)
        att = self.store.get_attempt("idem-" + "a" * 32)
        self.assertIsNotNone(att)
        self.assertEqual(att["phase"], "authorized_pending_discord")
        self.assertIsNone(self.store.get_idempotency("idem-" + "a" * 32))

    def test_confirm_requires_role_present(self):
        r = self.eval(make_req())
        self.assertTrue(r.needs_discord_apply)
        after = screened([RULES.role_id])
        c = confirm_grant(self.store, "idem-" + "a" * 32, member_after=after, member_role=MEMBER)
        self.assertFalse(c.ok)
        self.assertEqual(c.code, "DISCORD_ROLE_NOT_PRESENT")
        self.assertIsNone(self.store.get_idempotency("idem-" + "a" * 32))

    def test_confirm_writes_success_when_role_present(self):
        r = self.eval(make_req())
        self.assertTrue(r.needs_discord_apply)
        after = screened([RULES.role_id, MEMBER.role_id])
        c = confirm_grant(self.store, "idem-" + "a" * 32, member_after=after, member_role=MEMBER)
        self.assertTrue(c.ok)
        self.assertEqual(c.code, "GRANT_CONFIRMED")
        prior = self.store.get_idempotency("idem-" + "a" * 32)
        self.assertTrue(prior["ok"])
        self.assertEqual(prior["phase"], "success")

    def test_abort_allows_retry_with_new_nonce(self):
        key = "idem-" + "r" * 32
        r1 = self.eval(make_req(nonce="nonce-abort-1-abcdefghijklmno", idempotency_key=key))
        self.assertTrue(r1.needs_discord_apply)
        abort_grant_attempt(self.store, key)
        r2 = self.eval(make_req(nonce="nonce-abort-2-abcdefghijklmno", idempotency_key=key))
        self.assertTrue(r2.ok)
        self.assertTrue(r2.needs_discord_apply)

    def test_already_member_is_durable_success(self):
        m = screened([RULES.role_id, MEMBER.role_id])
        r = self.eval(make_req(), member=m)
        self.assertEqual(r.code, "ALREADY_MEMBER")
        self.assertFalse(r.needs_discord_apply)
        prior = self.store.get_idempotency("idem-" + "a" * 32)
        self.assertTrue(prior["ok"])

    def test_idempotent_success_replay(self):
        key = "idem-" + "s" * 32
        self.eval(make_req(nonce="nonce-succ-1-abcdefghijklmnop", idempotency_key=key))
        after = screened([RULES.role_id, MEMBER.role_id])
        confirm_grant(self.store, key, member_after=after, member_role=MEMBER)
        r2 = self.eval(make_req(nonce="nonce-succ-2-abcdefghijklmnop", idempotency_key=key))
        self.assertTrue(r2.ok)
        self.assertFalse(r2.needs_discord_apply)

    def test_journal_survives_restart(self):
        key = "idem-" + "j" * 32
        self.eval(make_req(nonce="nonce-journal-1-abcdefghijkl", idempotency_key=key))
        after = screened([RULES.role_id, MEMBER.role_id])
        confirm_grant(self.store, key, member_after=after, member_role=MEMBER)
        store2 = ReplayStore(self.path, now=time.time, require_persist=True)
        prior = store2.get_idempotency(key)
        self.assertTrue(prior["ok"])
        self.assertEqual(store2._bindings[XID], DISCORD)
        self.assertIn("nonce-journal-1-abcdefghijkl", store2._nonces)

    def test_nonce_persisted_and_replay_denied_after_restart(self):
        n = "nonce-persist-replay-abcdefgh"
        self.eval(make_req(nonce=n, idempotency_key="idem-" + "n" * 32))
        store2 = ReplayStore(self.path, now=time.time, require_persist=True)
        self.assertFalse(store2.see_nonce(n))

    def test_journal_write_failure_fail_closed(self):
        bad = ReplayStore(Path("/proc/unlikely_member_grant_path/x.json"), require_persist=True)
        with self.assertRaises(DurableStoreError):
            bad.see_nonce("nonce-fail-write-abcdefghijklmn")

    def test_binding_conflict_after_legitimate_bind(self):
        self.eval(make_req(nonce="nonce-b1-abcdefghijklmnopqrst"))
        confirm_grant(self.store, "idem-" + "a" * 32,
                      member_after=screened([RULES.role_id, MEMBER.role_id]),
                      member_role=MEMBER)
        other = make_req(
            nonce="nonce-b2-abcdefghijklmnopqrst",
            x_user_id="1000000000000000002",
            idempotency_key="idem-" + "b" * 32,
        )
        self.assertEqual(self.eval(other).code, "DISCORD_ALREADY_BOUND_TO_OTHER_X")

    def test_failed_discord_grant_does_not_permanently_claim_account(self):
        req = make_req(nonce="nonce-fail-discord-abcdefghij",
                       idempotency_key="idem-" + "q" * 32)
        self.assertTrue(self.eval(req).needs_discord_apply)
        self.assertEqual(self.store._bindings, {})
        abort_grant_attempt(self.store, req.idempotency_key)
        self.assertEqual(self.store._bindings, {})
        different_discord = "2000000000000000009"
        retry = make_req(nonce="nonce-other-member-abcdefghijkl",
                         idempotency_key="idem-" + "w" * 32,
                         discord_user_id=different_discord)
        member = MemberSnapshot(user_id=different_discord, pending=False,
                                role_ids=[RULES.role_id])
        self.assertTrue(self.eval(retry, member=member).needs_discord_apply)

    def test_pending_grant_blocks_competing_identity_without_binding(self):
        self.assertTrue(self.eval(make_req(nonce="nonce-pending-owner-abcdefghi")).needs_discord_apply)
        other = make_req(nonce="nonce-pending-other-abcdefghi",
                         idempotency_key="idem-" + "b" * 32,
                         x_user_id="1000000000000000002")
        self.assertEqual(self.eval(other).code, "GRANT_ATTEMPT_IDENTITY_CONFLICT")
        self.assertEqual(self.store._bindings, {})

    def test_crash_reconciliation_with_actual_member_role(self):
        key = "idem-" + "z" * 32
        req = make_req(nonce="nonce-crash-first-abcdefghijk", idempotency_key=key)
        self.assertTrue(self.eval(req).needs_discord_apply)
        restart = ReplayStore(self.path, require_persist=True)
        next_req = make_req(nonce="nonce-crash-second-abcdefghij", idempotency_key=key)
        result = self.eval(next_req, store=restart,
                           member=screened([RULES.role_id, MEMBER.role_id]))
        self.assertEqual(result.code, "GRANT_CONFIRMED")
        self.assertEqual(restart._bindings[XID], DISCORD)

    def test_hierarchy(self):
        high = RoleSnapshot(MEMBER.role_id, "Member", position=50)
        self.assertEqual(self.eval(make_req(), member_role=high).code, "BOT_HIERARCHY_INSUFFICIENT")
        self.assertEqual(self.store._bindings, {})

    def test_privileged_member_role(self):
        bad = RoleSnapshot(MEMBER.role_id, "Member", 4, {"manage_guild": True})
        self.assertEqual(self.eval(make_req(), member_role=bad).code, "MEMBER_ROLE_PRIVILEGED")
        self.assertEqual(self.store._bindings, {})


if __name__ == "__main__":
    unittest.main()
