"""Regression for issue #50: NativeChannelHubView must not override LayoutView._refresh.

Offline only — no Discord network, no tokens.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

CANDIDATES = [
    pathlib.Path("discord-bot/bot.py"),
    pathlib.Path("../discord-bot/bot.py"),
    pathlib.Path("/home/workdir/artifacts/bot_fixed_batch3.py"),
]
BOT_PATH = next((p for p in CANDIDATES if p.exists()), None)


class NativeHubRefreshCollisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if BOT_PATH is None:
            raise unittest.SkipTest("bot.py not found for offline regression")
        cls.src = BOT_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.src)

    def _class_methods(self, class_name: str) -> dict:
        methods = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods[item.name] = item
        return methods

    def test_no_async_refresh_on_native_hub_view(self):
        methods = self._class_methods("NativeChannelHubView")
        self.assertTrue(methods, "NativeChannelHubView class not found")
        self.assertNotIn(
            "_refresh",
            methods,
            "NativeChannelHubView still defines _refresh — collides with "
            "discord.ui.LayoutView._refresh(components)",
        )
        self.assertIn("_refresh_feed", methods)
        self.assertIsInstance(methods["_refresh_feed"], ast.AsyncFunctionDef)

    def test_refresh_button_binds_refresh_feed(self):
        self.assertIn("button.callback = self._refresh_feed", self.src)
        self.assertNotIn("button.callback = self._refresh\n", self.src)
        self.assertNotIn("button.callback = self._refresh\r", self.src)

    def test_layoutview_refresh_still_resolvable_on_mro_text(self):
        methods = self._class_methods("NativeChannelHubView")
        self.assertNotIn("_refresh", methods)

    def test_refresh_feed_is_async_def(self):
        methods = self._class_methods("NativeChannelHubView")
        node = methods.get("_refresh_feed")
        self.assertIsNotNone(node)
        self.assertIsInstance(node, ast.AsyncFunctionDef)


if __name__ == "__main__":
    unittest.main()
