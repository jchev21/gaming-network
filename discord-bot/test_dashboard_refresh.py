import unittest
from datetime import date

from dashboard_refresh import dashboard_fingerprint


def dataset():
    return {
        "events": [{"id": 1, "title": "Community meetup", "date": "2026-11-06", "important": False}],
        "users": {"42": {"server_points": 100}},
        "affiliates": {},
        "redemptions": [{"status": "pending"}],
        "rewards": [{"id": 1, "name": "Sample badge", "active": True}],
        "feed": [{"content": "unrelated new chat"}],
    }


class DashboardRefreshFingerprintTests(unittest.TestCase):
    def test_unchanged_image_sources_share_signature(self):
        d = dataset()
        a = dashboard_fingerprint("calendar", d, today=date(2026, 11, 5))
        b = dashboard_fingerprint("calendar", dict(d), today=date(2026, 11, 5))
        self.assertEqual(a, b)

    def test_unrelated_chat_does_not_force_dashboard_edit(self):
        d = dataset()
        old = dashboard_fingerprint("board", d)
        d["feed"].append({"content": "another chat message"})
        self.assertEqual(old, dashboard_fingerprint("board", d))

    def test_event_edit_invalidates_calendar_only(self):
        d = dataset()
        cal = dashboard_fingerprint("calendar", d, today=date(2026, 11, 5))
        board = dashboard_fingerprint("board", d)
        d["events"][0]["title"] = "Event rescheduled"
        self.assertNotEqual(cal, dashboard_fingerprint("calendar", d, today=date(2026, 11, 5)))
        self.assertEqual(board, dashboard_fingerprint("board", d))

    def test_calendar_updates_on_new_day(self):
        d = dataset()
        self.assertNotEqual(
            dashboard_fingerprint("calendar", d, today=date(2026, 11, 5)),
            dashboard_fingerprint("calendar", d, today=date(2026, 11, 6)),
        )

    def test_new_points_and_redemptions_invalidate_relevant_panels(self):
        d = dataset()
        board = dashboard_fingerprint("board", d)
        rewards = dashboard_fingerprint("rewards", d)
        d["users"]["42"]["server_points"] = 250
        self.assertNotEqual(board, dashboard_fingerprint("board", d))
        self.assertEqual(rewards, dashboard_fingerprint("rewards", d))
        d["redemptions"][0]["status"] = "approved"
        self.assertNotEqual(rewards, dashboard_fingerprint("rewards", d))

    def test_unknown_panel_is_rejected(self):
        with self.assertRaises(ValueError):
            dashboard_fingerprint("unknown", dataset())


if __name__ == "__main__":
    unittest.main()
