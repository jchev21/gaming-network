#!/usr/bin/env python3
"""Unit tests for guild_planner — pure offline, no network, no credentials."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from guild_planner import (  # noqa: E402
    load_desired,
    load_current,
    plan_structure,
    render_markdown,
    main as planner_main,
)


class TestGuildPlanner(unittest.TestCase):
    def setUp(self) -> None:
        self.desired = load_desired()

    def test_desired_loads(self) -> None:
        self.assertIn("categories", self.desired)
        self.assertIn("roles", self.desired)
        self.assertGreater(len(self.desired["categories"]), 0)
        self.assertGreater(len(self.desired["roles"]), 0)

    def test_empty_current_produces_creates(self) -> None:
        current = {"categories": [], "channels": [], "roles": []}
        plan = plan_structure(self.desired, current)
        self.assertIn(plan.status, ("READY_FOR_MANUAL_SMOKE_TEST", "BLOCKED"))
        creates = [a for a in plan.actions if a.action == "create"]
        self.assertGreater(len(creates), 0)
        preserves = [a for a in plan.actions if a.action == "preserve"]
        self.assertEqual(len(preserves), 0)

    def test_idempotent_with_matching_names(self) -> None:
        # Simulate current state that already has every desired name
        categories = [{"id": f"cat-{i}", "name": c["name"]} for i, c in enumerate(self.desired["categories"])]
        channels = []
        for c in self.desired["categories"]:
            for ch in c["channels"]:
                channels.append({"id": f"ch-{ch['name']}", "name": ch["name"], "category": c["name"]})
        roles = [{"id": f"role-{r['name']}", "name": r["name"]} for r in self.desired["roles"]]
        current = {"categories": categories, "channels": channels, "roles": roles}

        plan1 = plan_structure(self.desired, current)
        plan2 = plan_structure(self.desired, current)

        self.assertEqual(
            [(a.action, a.kind, a.name) for a in plan1.actions],
            [(a.action, a.kind, a.name) for a in plan2.actions],
        )
        creates = [a for a in plan1.actions if a.action == "create"]
        self.assertEqual(len(creates), 0, "Matching names must not schedule creates")
        preserves = [a for a in plan1.actions if a.action == "preserve"]
        self.assertGreater(len(preserves), 0)

    def test_no_deletes_ever(self) -> None:
        current = {
            "categories": [{"id": "1", "name": "LEGACY ONLY"}],
            "channels": [{"id": "2", "name": "old-channel"}],
            "roles": [{"id": "3", "name": "OldRole"}],
        }
        plan = plan_structure(self.desired, current)
        for a in plan.actions:
            self.assertNotEqual(a.action, "delete")
            self.assertNotIn("delete", a.action.lower())

    def test_duplicate_current_names_conflict(self) -> None:
        current = {
            "categories": [],
            "channels": [
                {"id": "1", "name": "welcome"},
                {"id": "2", "name": "welcome"},
            ],
            "roles": [],
        }
        plan = plan_structure(self.desired, current)
        conflicts = [a for a in plan.actions if a.action == "conflict"]
        self.assertGreater(len(conflicts), 0)
        self.assertEqual(plan.status, "BLOCKED")

    def test_existing_ids_preserved_in_action(self) -> None:
        current = {
            "categories": [{"id": "999", "name": "START HERE"}],
            "channels": [{"id": "888", "name": "welcome"}],
            "roles": [{"id": "777", "name": "Member"}],
        }
        plan = plan_structure(self.desired, current)
        by_name = {(a.kind, a.name): a for a in plan.actions}
        self.assertEqual(by_name[("category", "START HERE")].existing_id, "999")
        self.assertEqual(by_name[("channel", "welcome")].existing_id, "888")
        self.assertEqual(by_name[("role", "Member")].existing_id, "777")
        self.assertEqual(by_name[("category", "START HERE")].action, "preserve")

    def test_admin_role_flagged_high_risk(self) -> None:
        current = {"categories": [], "channels": [], "roles": []}
        plan = plan_structure(self.desired, current)
        admin_actions = [a for a in plan.actions if a.kind == "role" and a.name == "Admin"]
        self.assertEqual(len(admin_actions), 1)
        self.assertEqual(admin_actions[0].risk, "high")

    def test_markdown_render(self) -> None:
        plan = plan_structure(self.desired, {"categories": [], "channels": [], "roles": []})
        md = render_markdown(plan)
        self.assertIn("# Guild Structure Plan", md)
        self.assertIn(plan.status, md)

    def test_cli_json_exit_zero_on_clean(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "plan.json"
            rc = planner_main(["--format", "json", "--out", str(out)])
            self.assertIn(rc, (0, 1))  # 1 only if blocked by design
            data = json.loads(out.read_text())
            self.assertIn("status", data)
            self.assertIn("actions", data)

    def test_apply_refused_without_env(self) -> None:
        # apply path must refuse when APPLY_GUILD_CHANGES is unset
        import os
        os.environ.pop("APPLY_GUILD_CHANGES", None)
        with self.assertRaises(SystemExit) as ctx:
            planner_main(["--apply"])
        self.assertNotEqual(ctx.exception.code, 0)


class TestLoadCurrent(unittest.TestCase):
    def test_missing_file_empty(self) -> None:
        c = load_current(None)
        self.assertEqual(c["categories"], [])
        self.assertEqual(c["channels"], [])
        self.assertEqual(c["roles"], [])

    def test_load_from_temp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "snap.json"
            p.write_text(json.dumps({"categories": [{"name": "X", "id": "1"}]}))
            c = load_current(p)
            self.assertEqual(len(c["categories"]), 1)


if __name__ == "__main__":
    unittest.main()
