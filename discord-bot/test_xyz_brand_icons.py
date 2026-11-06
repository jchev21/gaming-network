"""Offline safety tests for XYZ brand icon helper."""
from __future__ import annotations
import os
import unittest
from pathlib import Path
import tempfile

from xyz_brand_icons import _truthy, apply_xyz_brand_icons


class XyzBrandTests(unittest.TestCase):
    def test_truthy(self):
        self.assertTrue(_truthy("true"))
        self.assertFalse(_truthy(""))

    def test_skipped_without_flag(self):
        os.environ.pop("XYZ_APPLY_BRAND_ICONS", None)
        # Should no-op without network
        import asyncio
        class B:
            def get_guild(self, _): return None
        asyncio.get_event_loop().run_until_complete(apply_xyz_brand_icons(B(), Path(tempfile.mkdtemp())))


if __name__ == "__main__":
    unittest.main()
