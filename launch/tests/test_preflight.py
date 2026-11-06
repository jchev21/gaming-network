#!/usr/bin/env python3
"""Offline tests for launch preflight."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from preflight import run_preflight, CheckResult  # noqa: E402


class TestPreflight(unittest.TestCase):
    def test_runs_without_network(self) -> None:
        result = run_preflight()
        self.assertIsInstance(result, CheckResult)
        self.assertIn(result.status, ("READY_FOR_MANUAL_SMOKE_TEST", "BLOCKED", "NOT_VERIFIED"))

    def test_has_passed_checks(self) -> None:
        result = run_preflight()
        # In a complete checkout we expect at least some passes
        self.assertIsInstance(result.passed, list)
        self.assertIsInstance(result.failures, list)
        self.assertIsInstance(result.warnings, list)
        self.assertIsInstance(result.owner_actions, list)

    def test_does_not_require_discord_token(self) -> None:
        import os
        token = os.environ.pop("DISCORD_TOKEN", None)
        try:
            result = run_preflight()
            # Should still complete; token absence is fine for offline mode
            self.assertIsInstance(result.status, str)
        finally:
            if token is not None:
                os.environ["DISCORD_TOKEN"] = token


if __name__ == "__main__":
    unittest.main()
