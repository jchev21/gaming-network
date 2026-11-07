"""Safe content-handoff assertions; no Discord API or publishing."""
from __future__ import annotations
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "community-content"
MANIFEST = ROOT / "content-manifest.json"


class CommunityContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_handoff_files_and_official_handle(self):
        self.assertEqual(self.data["official_x_handle"], "@_xyzhub_")
        self.assertFalse(self.data["autopublish_enabled"])
        self.assertFalse(self.data["live_channel_moves_enabled"])
        for filename in self.data["source_files"]:
            body = (ROOT / filename).read_text(encoding="utf-8")
            self.assertTrue(body.startswith("# XYZ.HUB"))
            self.assertNotIn("@xyzhub", body, filename)
            self.assertNotIn("@jordan__chev", body, filename)
            self.assertIn("@_xyzhub_", body, filename)

    def test_all_destinations_are_manual_and_protect_role_gates(self):
        data = self.data["channel_content"]
        self.assertGreaterEqual(len(data), 15)
        self.assertEqual(len({x["id"] for x in data}), len(data))
        self.assertTrue(all(x["requires_fresh_inventory_and_owner_review"] for x in data))
        self.assertTrue(all(x["existing_channel_id_last_audit"] is None
                            or x["existing_channel_id_last_audit"].isdigit() for x in data))
        verify = next(x for x in data if x["destination_channel_name"] == "verify-x")
        self.assertIn("restricted", verify["permission_expectation"])
        self.assertTrue(verify["real_discord_published"])
        self.assertTrue(next(x for x in data if x["destination_channel_name"] == "rules")["real_discord_published"])
        self.assertIsNone(next(x for x in data if x["destination_channel_name"] == "games-and-events")["existing_channel_id_last_audit"])
        self.assertEqual(next(x for x in data if x["destination_channel_name"] == "stage")["status"], "MISSING_CHANNEL")

    def test_no_false_claim_of_live_member_grant(self):
        state = self.data["launch_status"]
        self.assertIn("disabled", state["member_auto_grant"])
        self.assertIn("deferred", state["real_account_test"])
        self.assertIn("disabled", state["paid_x_polling"])
        self.assertTrue(self.data["manual_owner_review_required"])


if __name__ == "__main__":
    unittest.main()
