from __future__ import annotations
import tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from discord_bot_change_bridge.bulk import validate_bulk_bounds
from discord_bot_change_bridge.schedule import ScheduleStore, ScheduledPost
from discord_bot_change_bridge.locking import OperationLock
from discord_bot_change_bridge.onboarding_ops import is_safe_onboarding_publish


class BulkTests(unittest.TestCase):
    def test_bounds(self):
        class O:
            def __init__(self, op): self.op = op
        ops = [O("create_text_channel") for _ in range(20)]
        flags = validate_bulk_bounds(ops)
        self.assertTrue(any("too_many_creates" in f for f in flags))


class ScheduleTests(unittest.TestCase):
    def test_due_and_expire(self):
        with tempfile.TemporaryDirectory() as td:
            s = ScheduleStore(Path(td) / "sched.json")
            s.add(ScheduledPost("s1", 1, "p", "h", "a", execute_after_unix=10, execute_before_unix=20))
            self.assertEqual(s.due(now_unix=5), [])
            self.assertEqual(len(s.due(now_unix=15)), 1)
            s.mark_posted("s1", 99)
            self.assertEqual(s.due(now_unix=16), [])


class LockTests(unittest.TestCase):
    def test_lock(self):
        with tempfile.TemporaryDirectory() as td:
            lock = OperationLock(Path(td) / "lock", ttl_seconds=60)
            self.assertTrue(lock.acquire("k1"))
            self.assertFalse(lock.acquire("k1"))
            lock.release("k1")
            self.assertTrue(lock.acquire("k1"))


class OnboardingTests(unittest.TestCase):
    def test_no_role_grants(self):
        ok, _ = is_safe_onboarding_publish("welcome", grant_roles=True)
        self.assertFalse(ok)
        ok, _ = is_safe_onboarding_publish("welcome")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
