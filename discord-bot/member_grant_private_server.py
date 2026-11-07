"""Private Railway-only Member grant ingress; never expose Hub dashboard.

The normal Discord Hub dashboard stays at 127.0.0.1:8765. A distinct
aiohttp app with *only* POST /internal/member-grant may be bound to
Railway's internal IPv6 address, and ONLY with explicit owner grant flags
and a strong shared HMAC secret. No secret, no private server.
"""
from __future__ import annotations

import os
from pathlib import Path

INTERNAL_HOST = "::"
INTERNAL_PORT = 8787
MIN_SECRET_LENGTH = 32


def private_server_enabled(env=None) -> bool:
    env = os.environ if env is None else env
    secret = env.get("GN_MEMBER_GRANT_HMAC_SECRET") or ""
    return (
        env.get("GN_MEMBER_GRANT_ROUTE_ENABLED") == "true"
        and env.get("GN_MEMBER_GRANT_ENABLED") == "true"
        and len(secret) >= MIN_SECRET_LENGTH
    )


def make_private_app(bot, data_dir: Path, env=None):
    """Return None if unconfigured. No dashboard or general HTTP routes."""
    if not private_server_enabled(env):
        return None
    from aiohttp import web
    from member_grant_wire import attach_member_grant

    app = web.Application(client_max_size=4096)
    attach_member_grant(app, bot, Path(data_dir))
    paths = {(route.method, route.resource.canonical) for route in app.router.routes()}
    if paths != {("POST", "/internal/member-grant")}:
        raise RuntimeError("Private Member grant server has unexpected routes")
    return app


async def serve_private_member_grant(bot, data_dir: Path, env=None):
    """Only on Railway's encrypted internal network. No public domain/proxy."""
    app = make_private_app(bot, data_dir, env)
    if app is None:
        print("XYZ Member grant private server disabled (default safe)")
        return None
    from aiohttp import web

    runner = web.AppRunner(app)
    await runner.setup()
    try:
        await web.TCPSite(runner, host=INTERNAL_HOST, port=INTERNAL_PORT).start()
    except Exception:
        await runner.cleanup()
        raise
    print("XYZ Member grant private server ready on Railway internal port")
    return runner
