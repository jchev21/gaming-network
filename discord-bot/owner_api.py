"""Batch E: owner-only change-bridge HTTP API for Gemini dashboard."""
from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path

from aiohttp import web

API_PREFIX = "/owner/change-bridge"


def _owner_token() -> str:
    return os.environ.get("CHANGE_BRIDGE_OWNER_API_TOKEN") or ""


def _guild_id() -> int:
    return int(os.environ.get("CHANGE_BRIDGE_GUILD_ID") or "1566290427366080612")


def _check_auth(request: web.Request) -> str | None:
    token = _owner_token()
    if not token:
        return "CHANGE_BRIDGE_OWNER_API_TOKEN not configured"
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {token}":
        return "unauthorized"
    csrf_hdr = request.headers.get("X-CSRF-Token", "")
    csrf_cookie = request.cookies.get("cb_csrf", "")
    if csrf_cookie and csrf_hdr and not hmac.compare_digest(csrf_cookie, csrf_hdr):
        return "csrf_mismatch"
    return None


def _json_error(msg: str, status: int = 403) -> web.Response:
    return web.json_response({"ok": False, "error": msg}, status=status)


async def inventory_handler(request: web.Request) -> web.Response:
    err = _check_auth(request)
    if err:
        return _json_error(err)
    builder = request.app.get("change_bridge_inventory")
    if builder is None:
        return _json_error("inventory builder not wired", 503)
    inv = await builder()
    return web.json_response({
        "ok": True,
        "guild_id": inv.guild_id,
        "digest": inv.digest(),
        "channels": [{"id": c.id, "name": c.name, "type": c.type, "private": c.private} for c in inv.channels],
        "categories": [{"id": c.id, "name": c.name, "private": c.private} for c in inv.categories],
    })


async def preview_handler(request: web.Request) -> web.Response:
    err = _check_auth(request)
    if err:
        return _json_error(err)
    try:
        body = await request.json()
    except Exception:
        return _json_error("invalid json", 400)
    from discord_bot_change_bridge import parse_proposal, plan_hash, build_plan_diff, ProposalError
    try:
        proposal = parse_proposal(body.get("proposal") or body)
    except ProposalError as e:
        return _json_error(str(e), 400)
    if proposal.guild_id != _guild_id():
        return _json_error("guild_id mismatch", 403)
    builder = request.app.get("change_bridge_inventory")
    if builder is None:
        return _json_error("inventory builder not wired", 503)
    inv = await builder()
    ph = plan_hash(proposal)
    diff = build_plan_diff(proposal, inv, ph)
    return web.json_response({
        "ok": True,
        "plan_hash": ph,
        "stale": diff.stale,
        "blocked": diff.blocked,
        "risk_flags": diff.risk_flags,
        "lines": [{"op_id": l.op_id, "op": l.op, "summary": l.summary, "blocked": l.blocked,
                   "block_reason": l.block_reason} for l in diff.lines],
    })


async def status_handler(request: web.Request) -> web.Response:
    err = _check_auth(request)
    if err:
        return _json_error(err)
    journal_path = request.app.get("change_bridge_journal_path")
    if not journal_path or not Path(journal_path).exists():
        return web.json_response({"ok": True, "entries": []})
    from discord_bot_change_bridge import Journal
    entries = Journal(Path(journal_path)).entries()[-50:]
    return web.json_response({"ok": True, "entries": entries})


def register_owner_api(app: web.Application, *, journal_path: Path | None = None) -> None:
    app.router.add_get(f"{API_PREFIX}/inventory", inventory_handler)
    app.router.add_post(f"{API_PREFIX}/preview", preview_handler)
    app.router.add_get(f"{API_PREFIX}/status", status_handler)
    if journal_path:
        app["change_bridge_journal_path"] = str(journal_path)

    async def csrf_handler(request: web.Request) -> web.Response:
        err = _check_auth(request)
        if err:
            return _json_error(err)
        tok = secrets.token_hex(16)
        resp = web.json_response({"ok": True, "csrf": tok})
        resp.set_cookie("cb_csrf", tok, httponly=False, samesite="Strict", max_age=3600)
        return resp

    app.router.add_get(f"{API_PREFIX}/csrf", csrf_handler)
