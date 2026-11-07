"""Verify private Member grant is an independent fail-closed app."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from member_grant_private_server import (
    INTERNAL_HOST, INTERNAL_PORT,
    make_private_app, private_server_enabled,
)

VALID = {
    "GN_MEMBER_GRANT_ROUTE_ENABLED": "true",
    "GN_MEMBER_GRANT_ENABLED": "true",
    "GN_MEMBER_GRANT_HMAC_SECRET": "test-only-not-a-secret-" + "y" * 48,
}


class MemberPrivateServerTests(unittest.TestCase):
    def test_defaults_to_no_server(self):
        self.assertFalse(private_server_enabled({}))
        self.assertIsNone(make_private_app(None, Path("/tmp"), {}))

    def test_any_single_gate_is_not_enough(self):
        for flag in ("GN_MEMBER_GRANT_ROUTE_ENABLED", "GN_MEMBER_GRANT_ENABLED"):
            state = dict(VALID)
            del state[flag]
            self.assertFalse(private_server_enabled(state))
            self.assertIsNone(make_private_app(None, Path("/tmp"), state))

    def test_short_or_missing_secret_is_denied(self):
        for secret in ("", "a" * 31):
            self.assertFalse(private_server_enabled({**VALID, "GN_MEMBER_GRANT_HMAC_SECRET": secret}))

    def test_private_address_only_and_isolated_route(self):
        from aiohttp import web
        self.assertEqual(INTERNAL_HOST, "::")
        self.assertEqual(INTERNAL_PORT, 8787)

        async def handler(_):
            return web.json_response({"ok": True})

        def fake_attach(app, bot, path):
            self.assertIsNone(bot)
            self.assertEqual(Path(path), Path("/tmp"))
            app.router.add_post("/internal/member-grant", handler)

        with patch("member_grant_wire.attach_member_grant", side_effect=fake_attach):
            app = make_private_app(None, Path("/tmp"), VALID)

        self.assertIsNotNone(app)
        self.assertEqual(app._client_max_size, 4096)
        self.assertEqual(
            {(r.method, r.resource.canonical) for r in app.router.routes()},
            {("POST", "/internal/member-grant")}
        )

    def test_refuses_extra_public_dashboard_routes(self):
        from aiohttp import web
        async def handler(_):
            return web.json_response({"ok": True})

        def unsafe_attach(app, *args):
            app.router.add_post("/internal/member-grant", handler)
            app.router.add_get("/api/chat", handler)

        with patch("member_grant_wire.attach_member_grant", side_effect=unsafe_attach):
            with self.assertRaisesRegex(RuntimeError, "unexpected routes"):
                make_private_app(None, Path("/tmp"), VALID)

    def test_existing_dashboard_stays_loopback(self):
        bot = (Path(__file__).resolve().parents[1] / "bot.py").read_text()
        self.assertIn('web.TCPSite(runner, "127.0.0.1", PORT)', bot)
        self.assertIn("serve_private_member_grant(bot, DATA_DIR)", bot)
        self.assertNotIn("attach_member_grant(app, bot, DATA_DIR)", bot)


if __name__ == "__main__":
    unittest.main()
