"""Offline regression: AddEventModal.on_submit must acknowledge before disk/refresh work."""
from __future__ import annotations

import ast
import pathlib
import unittest

CANDIDATES = [
    pathlib.Path("discord-bot/bot.py"),
    pathlib.Path("../discord-bot/bot.py"),
    pathlib.Path("/home/workdir/artifacts/bot_fixed_addevent.py"),
]


def _find_on_submit(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "AddEventModal":
            for item in node.body:
                if isinstance(item, ast.AsyncFunctionDef) and item.name == "on_submit":
                    return item
    return None


def _ordered_attrs_and_names(fn: ast.AsyncFunctionDef) -> list:
    calls = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            calls.append((node.lineno or 0, node.col_offset or 0, func.attr))
        elif isinstance(func, ast.Name):
            calls.append((node.lineno or 0, node.col_offset or 0, func.id))
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            if isinstance(arg, ast.Name) and arg.id == "save_data":
                calls.append((node.lineno or 0, node.col_offset or 0, "save_data"))
    calls.sort()
    return [name for _, _, name in calls]


class AddEventModalTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = next((p for p in CANDIDATES if p.exists()), None)
        if path is None:
            raise unittest.SkipTest("bot.py not found")
        cls.src = path.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.src)
        cls.on_submit = _find_on_submit(cls.tree)
        if cls.on_submit is None:
            raise unittest.SkipTest("AddEventModal.on_submit not found")

    def test_on_submit_is_async(self):
        self.assertIsInstance(self.on_submit, ast.AsyncFunctionDef)

    def test_send_message_before_persist(self):
        names = _ordered_attrs_and_names(self.on_submit)
        self.assertIn("send_message", names)
        self.assertTrue(
            "save_data" in names or "to_thread" in names,
            f"expected save_data or to_thread after acknowledge; got {names}",
        )
        send_idx = names.index("send_message")
        persist_idx = names.index("save_data") if "save_data" in names else names.index("to_thread")
        self.assertLess(
            send_idx,
            persist_idx,
            "interaction.response.send_message must run before disk persist "
            "so the modal is acknowledged within Discord's ~3s window",
        )

    def test_send_message_before_refresh_all_dashboards(self):
        names = _ordered_attrs_and_names(self.on_submit)
        self.assertIn("send_message", names)
        self.assertIn("refresh_all_dashboards", names)
        self.assertLess(names.index("send_message"), names.index("refresh_all_dashboards"))

    def test_b_add_still_sends_modal_without_defer(self):
        self.assertIn("send_modal(AddEventModal())", self.src)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "b_add":
                body_src = ast.get_source_segment(self.src, node) or ""
                self.assertNotIn("defer(", body_src)
                self.assertIn("send_modal", body_src)
                break
        else:
            self.fail("b_add handler not found")


if __name__ == "__main__":
    unittest.main()
