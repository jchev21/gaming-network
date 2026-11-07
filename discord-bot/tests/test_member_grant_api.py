"""Comprehensive denial + happy-path tests for issue #78 Member grant S2S API."""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from member_grant_api import (
    BotCapability, GrantRequest, MemberSnapshot, ReplayStore, RoleSnapshot,
    evaluate_grant, sign_request, TARGET_GUILD_ID,
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
        discord_user_id=discord,
        x_user_id=xid,
        guild_id=guild,
        idempotency_key=idem,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
    )


def screened_member(roles=None):
    return MemberSnapshot(user_id=DISCORD, pending=False, role_ids=roles or [RULES.role_id])


class MemberGrantTests(unittest.TestCase):
    def setUp(self):
        self.store = ReplayStore(now=time.time)

    def eval(self, req, **kwargs):
        defaults = dict(
            store=self.store, member=screened_member(), rules_role=RULES,
            member_role=MEMBER, bot=BOT, secret=SECRET, enabled=True, now=time.time(),
        )
        defaults.update(kwargs)
        return evaluate_grant(req, **defaults)

    def test_disabled_by_default(self):
        r = self.eval(make_req(), enabled=False)
        self.assertEqual(r.code, "MEMBER_GRANT_DISABLED")

    def test_missing_secret(self):
        r = self.eval(make_req(), secret="")
        self.assertEqual(r.code, "MEMBER_GRANT_MISCONFIGURED")

    def test_invalid_signature(self):
        r = self.eval(make_req(sig="0" * 64))
        self.assertEqual(r.code, "INVALID_SIGNATURE")

    def test_replayed_nonce(self):
        n = "nonce-replay-test-abcdefghijklmn"
        self.assertTrue(self.eval(make_req(nonce=n, idempotency_key="idem-" + "b" * 32)).ok)
        self.assertEqual(self.eval(make_req(nonce=n, idempotency_key="idem-" + "c" * 32)).code, "REPLAYED_NONCE")

    def test_expired_timestamp(self):
        self.assertEqual(self.eval(make_req(ts=int(time.time()) - 3600)).code, "EXPIRED_OR_SKEWED_TIMESTAMP")

    def test_guild_mismatch(self):
        self.assertEqual(self.eval(make_req(guild_id="1111111111111111111")).code, "GUILD_MISMATCH")

    def test_pending_screening_denied(self):
        m = MemberSnapshot(user_id=DISCORD, pending=True, role_ids=[RULES.role_id])
        self.assertEqual(self.eval(make_req(), member=m).code, "DISCORD_RULES_NOT_ACCEPTED")

    def test_missing_rules_accepted_role(self):
        m = MemberSnapshot(user_id=DISCORD, pending=False, role_ids=[])
        self.assertEqual(self.eval(make_req(), member=m).code, "MISSING_RULES_ACCEPTED_ROLE")

    def test_x_login_alone_cannot_skip_rules(self):
        m = MemberSnapshot(user_id=DISCORD, pending=False, role_ids=[])
        self.assertFalse(self.eval(make_req(), member=m).ok)

    def test_bot_hierarchy_insufficient(self):
        high = RoleSnapshot(MEMBER.role_id, "Member", position=50)
        self.assertEqual(self.eval(make_req(), member_role=high).code, "BOT_HIERARCHY_INSUFFICIENT")

    def test_privileged_member_role_rejected(self):
        bad = RoleSnapshot(MEMBER.role_id, "Member", 4, {"manage_guild": True})
        self.assertEqual(self.eval(make_req(), member_role=bad).code, "MEMBER_ROLE_PRIVILEGED")

    def test_identity_mismatch(self):
        m = MemberSnapshot(user_id="9999999999999999999", pending=False, role_ids=[RULES.role_id])
        self.assertEqual(self.eval(make_req(), member=m).code, "DISCORD_IDENTITY_MISMATCH")

    def test_member_not_in_guild(self):
        self.assertEqual(self.eval(make_req(), member=None).code, "MEMBER_NOT_IN_GUILD")

    def test_happy_path_authorizes_grant(self):
        r = self.eval(make_req())
        self.assertTrue(r.ok)
        self.assertEqual(r.code, "GRANT_AUTHORIZED")

    def test_already_member_idempotent(self):
        m = screened_member([RULES.role_id, MEMBER.role_id])
        r = self.eval(make_req(), member=m)
        self.assertEqual(r.code, "ALREADY_MEMBER")
        self.assertTrue(r.already_had_role)

    def test_idempotency_key_replays_success(self):
        key = "idem-" + "d" * 32
        self.assertEqual(self.eval(make_req(nonce="nonce-idem-1-abcdefghijklmnop", idempotency_key=key)).code, "GRANT_AUTHORIZED")
        r2 = self.eval(make_req(nonce="nonce-idem-2-abcdefghijklmnop", idempotency_key=key))
        self.assertTrue(r2.ok)

    def test_one_x_to_one_discord_binding(self):
        self.assertTrue(self.eval(make_req(nonce="nonce-bind-1-abcdefghijklmnopq")).ok)
        other = make_req(nonce="nonce-bind-2-abcdefghijklmnopq", x_user_id="1000000000000000002", idempotency_key="idem-" + "e" * 32)
        self.assertEqual(self.eval(other).code, "DISCORD_ALREADY_BOUND_TO_OTHER_X")

    def test_cross_user_x_cannot_steal_discord(self):
        self.assertTrue(self.eval(make_req(nonce="nonce-x1-abcdefghijklmnopqrstu")).ok)
        other = make_req(nonce="nonce-x2-abcdefghijklmnopqrstu", discord_user_id="2000000000000000009", idempotency_key="idem-" + "f" * 32)
        r2 = self.eval(other, member=MemberSnapshot(user_id="2000000000000000009", pending=False, role_ids=[RULES.role_id]))
        self.assertEqual(r2.code, "X_ALREADY_BOUND_TO_OTHER_DISCORD")

    def test_target_bot_denied(self):
        m = MemberSnapshot(user_id=DISCORD, pending=False, role_ids=[RULES.role_id], bot=True)
        self.assertEqual(self.eval(make_req(), member=m).code, "TARGET_IS_BOT")


if __name__ == "__main__":
    unittest.main()
