"""Offline safety smoke tests for Perplexity completed repair queue source only."""
import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gn_feedback.repair import RepairQueue, canonical, signed
from gn_feedback.repair_pr import PRVerifier
from gn_feedback.repair_cli import configured_queue


class RepairHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock_value = 1700000000.0
        self.key = b"offline-testing-key-0123456789abcdef"
        self.q = RepairQueue(
            str(Path(self.tmp.name) / "repairs.sqlite3"),
            owners={1001}, guild=2001, channel=3001,
            worker_key=self.key, base_sha="a" * 40,
            clock=lambda: self.clock_value,
        )
        self.group = {
            "id": "source-1", "issue": 123, "state": "done",
            "kind": "bug", "text": "Untrusted report; reproduce on safe fixture",
        }

    def tearDown(self):
        self.q.close()
        self.tmp.cleanup()

    def test_untrusted_report_does_not_enqueue_without_owner(self):
        with self.assertRaises(PermissionError):
            self.q.enqueue(999, 2001, 3001, self.group)
        with self.assertRaises(PermissionError):
            self.q.enqueue(1001, 2002, 3001, self.group)
        with self.assertRaises(PermissionError):
            self.q.enqueue(1001, 2001, 3002, self.group)
        self.assertEqual(self.q.db.execute("SELECT count(*) FROM jobs").fetchone()[0], 0)

    def test_duplicate_source_is_idempotent(self):
        one = self.q.enqueue(1001, 2001, 3001, self.group)
        two = self.q.enqueue(1001, 2001, 3001, self.group)
        self.assertEqual(one, two)
        self.assertEqual(self.q.db.execute("SELECT count(*) FROM jobs").fetchone()[0], 1)

    def test_job_is_bounded_and_signed(self):
        self.q.enqueue(1001, 2001, 3001, self.group)
        ticket = self.q.claim()
        self.assertEqual(ticket["payload"]["baseSha"], "a" * 40)
        self.assertEqual(ticket["payload"]["budget"]["maxProviderCalls"], 1)
        self.assertTrue(hmac.compare_digest(
            ticket["mac"],
            hmac.new(self.key, canonical(ticket["payload"]).encode(), hashlib.sha256).hexdigest(),
        ))
        self.assertIsNone(self.q.claim())

    def test_bad_worker_signature_rejected(self):
        self.q.enqueue(1001, 2001, 3001, self.group)
        ticket = self.q.claim()
        p = ticket["payload"]
        result = {
            "schemaVersion": 1, "job": p["job"], "attempt": p["attempt"],
            "nonce": p["nonce"], "status": "failed", "pr": None, "sha": None,
            "costMicroUSD": 0, "tokens": 0,
        }
        wrong = signed(result, b"wrong-key-12345678901234567890123")
        with self.assertRaises(PermissionError):
            self.q.submit(wrong, lambda *args: "PASS")
        self.assertEqual(self.q.get(p["job"])["state"], "running")

    def test_owner_approval_requires_verified_ci(self):
        self.q.enqueue(1001, 2001, 3001, self.group)
        claim = self.q.claim()["payload"]
        result = signed({
            "schemaVersion": 1, "job": claim["job"], "attempt": claim["attempt"],
            "nonce": claim["nonce"], "status": "completed",
            "pr": 12, "sha": "b" * 40,
            "costMicroUSD": 20, "tokens": 80,
        }, self.key)
        self.assertEqual(self.q.submit(result, lambda *args: "NOT RUN"), "awaiting_owner")
        j = self.q.get(claim["job"])
        with self.assertRaises(ValueError):
            self.q.decide(1001, 2001, 3001, j["id"], j["rev"], "verified")
        self.assertEqual(self.q.decide(1001, 2001, 3001, j["id"], j["rev"], "reject"), "rejected")
        with self.assertRaises(ValueError):
            self.q.decide(1001, 2001, 3001, j["id"], j["rev"], "reject")

    def test_expired_leases_not_accepted(self):
        self.q.enqueue(1001, 2001, 3001, self.group)
        p = self.q.claim()["payload"]
        self.clock_value += 1000
        self.q.expire()
        self.assertEqual(self.q.get(p["job"])["state"], "expired")

    def test_worker_cli_requires_explicit_opt_in(self):
        with patch.dict("os.environ", {"GN_FEEDBACK_REPAIR_ENABLED": "false"}):
            with self.assertRaises(ValueError):
                configured_queue()

    def test_pr_verifier_requires_checks_and_allowed_apps(self):
        for checks, apps in [([], {1}), (["node-tests"], set())]:
            with self.assertRaises(ValueError):
                PRVerifier("placeholder-token", checks, apps)


if __name__ == "__main__":
    unittest.main()
