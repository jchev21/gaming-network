"""Secure server-to-server Member role grant for XYZ.HUB (issue #78).

Flow (X service → Hub bot only):
  Rules Accepted (native screening) + verified X OAuth + verified Discord OAuth
  → signed, expiring, replay-protected POST /internal/member-grant
  → Hub bot re-checks hierarchy, Rules Accepted, pending=false
  → grants low-privilege Member role only

Defaults OFF (GN_MEMBER_GRANT_ENABLED != true).
Never trusts browser/client JSON for role state.
Never exposes bot token to the X service.
X login alone never grants Member.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

TARGET_GUILD_ID = 1566290427366080612
MEMBER_ROLE_NAME = "Member"
RULES_ROLE_NAME = "Rules Accepted"
MAX_SKEW_SECONDS = 60
NONCE_TTL_SECONDS = 300
IDEMPOTENCY_TTL_SECONDS = 86400

DANGEROUS_PERMS = (
    "administrator", "manage_guild", "manage_roles", "manage_channels",
    "manage_webhooks", "manage_messages", "ban_members", "kick_members",
    "moderate_members",
)


def _snowflake(value: Any) -> bool:
    return isinstance(value, str) and value.isdigit() and 15 <= len(value) <= 24


def _secret() -> str:
    return (os.environ.get("GN_MEMBER_GRANT_HMAC_SECRET") or "").strip()


def grant_enabled() -> bool:
    return (os.environ.get("GN_MEMBER_GRANT_ENABLED") or "false").lower() == "true"


def canonical_payload(
    timestamp: str, nonce: str, idempotency_key: str,
    discord_user_id: str, x_user_id: str, guild_id: str,
) -> str:
    return "\n".join([timestamp, nonce, idempotency_key, discord_user_id, x_user_id, guild_id])


def sign_request(
    secret: str, timestamp: str, nonce: str, idempotency_key: str,
    discord_user_id: str, x_user_id: str, guild_id: str,
) -> str:
    msg = canonical_payload(timestamp, nonce, idempotency_key, discord_user_id, x_user_id, guild_id)
    return hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(secret: str, signature: str, *parts: str) -> bool:
    if not secret or not signature or len(signature) != 64:
        return False
    expected = sign_request(secret, *parts)
    return hmac.compare_digest(expected, signature)


@dataclass
class GrantRequest:
    discord_user_id: str
    x_user_id: str
    guild_id: str
    idempotency_key: str
    timestamp: str
    nonce: str
    signature: str
    request_id: str = ""


@dataclass
class GrantResult:
    ok: bool
    code: str
    status: int
    detail: str = ""
    already_had_role: bool = False


@dataclass
class MemberSnapshot:
    user_id: str
    pending: Optional[bool]
    role_ids: list[str]
    bot: bool = False


@dataclass
class RoleSnapshot:
    role_id: str
    name: str
    position: int
    permissions_flags: dict[str, bool] = field(default_factory=dict)


@dataclass
class BotCapability:
    manage_roles: bool
    top_role_position: int


class ReplayStore:
    def __init__(self, path: Optional[Path] = None, now: Callable[[], float] = time.time):
        self.path = path
        self.now = now
        self._nonces: dict[str, float] = {}
        self._idem: dict[str, dict] = {}
        self._bindings: dict[str, str] = {}
        self._rev_bindings: dict[str, str] = {}
        if path and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._bindings = {str(k): str(v) for k, v in (data.get("bindings") or {}).items()}
                self._rev_bindings = {v: k for k, v in self._bindings.items()}
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass

    def _purge(self) -> None:
        t = self.now()
        self._nonces = {k: exp for k, exp in self._nonces.items() if exp > t}
        self._idem = {k: v for k, v in self._idem.items() if v.get("exp", 0) > t}

    def see_nonce(self, nonce: str) -> bool:
        self._purge()
        if not nonce or len(nonce) < 16 or len(nonce) > 128:
            return False
        if nonce in self._nonces:
            return False
        self._nonces[nonce] = self.now() + NONCE_TTL_SECONDS
        return True

    def get_idempotency(self, key: str) -> Optional[dict]:
        self._purge()
        return self._idem.get(key)

    def put_idempotency(self, key: str, result: dict) -> None:
        self._purge()
        self._idem[key] = {**result, "exp": self.now() + IDEMPOTENCY_TTL_SECONDS}

    def bind(self, x_user_id: str, discord_user_id: str) -> Optional[str]:
        prior_d = self._bindings.get(x_user_id)
        if prior_d and prior_d != discord_user_id:
            return "X_ALREADY_BOUND_TO_OTHER_DISCORD"
        prior_x = self._rev_bindings.get(discord_user_id)
        if prior_x and prior_x != x_user_id:
            return "DISCORD_ALREADY_BOUND_TO_OTHER_X"
        self._bindings[x_user_id] = discord_user_id
        self._rev_bindings[discord_user_id] = x_user_id
        self._persist()
        return None

    def _persist(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"bindings": self._bindings}, indent=2), encoding="utf-8")
        except OSError:
            pass


def role_is_dangerous(role: RoleSnapshot) -> bool:
    return any(bool(role.permissions_flags.get(f)) for f in DANGEROUS_PERMS)


def can_bot_assign(bot: BotCapability, role: RoleSnapshot) -> bool:
    return bool(bot.manage_roles and bot.top_role_position > role.position)


def evaluate_grant(
    req: GrantRequest, *, store: ReplayStore, member: Optional[MemberSnapshot],
    rules_role: Optional[RoleSnapshot], member_role: Optional[RoleSnapshot],
    bot: BotCapability, secret: Optional[str] = None, enabled: Optional[bool] = None,
    now: Optional[float] = None,
) -> GrantResult:
    t = now if now is not None else time.time()
    sec = secret if secret is not None else _secret()
    is_on = enabled if enabled is not None else grant_enabled()

    if not is_on:
        return GrantResult(False, "MEMBER_GRANT_DISABLED", 403, "Automatic Member grant is OFF")
    if not sec or len(sec) < 32:
        return GrantResult(False, "MEMBER_GRANT_MISCONFIGURED", 503, "HMAC secret missing")
    if not all([
        _snowflake(req.discord_user_id), _snowflake(req.x_user_id), _snowflake(req.guild_id),
        isinstance(req.idempotency_key, str) and 16 <= len(req.idempotency_key) <= 128,
        isinstance(req.timestamp, str) and req.timestamp.isdigit(),
        isinstance(req.nonce, str) and 16 <= len(req.nonce) <= 128,
        isinstance(req.signature, str),
    ]):
        return GrantResult(False, "INVALID_GRANT_REQUEST", 400)
    if int(req.guild_id) != TARGET_GUILD_ID:
        return GrantResult(False, "GUILD_MISMATCH", 403)
    try:
        ts = int(req.timestamp)
    except ValueError:
        return GrantResult(False, "INVALID_TIMESTAMP", 400)
    if ts > 10_000_000_000:
        ts = ts / 1000.0
    if abs(t - ts) > MAX_SKEW_SECONDS:
        return GrantResult(False, "EXPIRED_OR_SKEWED_TIMESTAMP", 401)
    if not verify_signature(sec, req.signature, req.timestamp, req.nonce, req.idempotency_key,
                            req.discord_user_id, req.x_user_id, req.guild_id):
        return GrantResult(False, "INVALID_SIGNATURE", 401)

    prior = store.get_idempotency(req.idempotency_key)
    if prior:
        return GrantResult(True, prior.get("code", "IDEMPOTENT_REPLAY"), 200,
                           detail=prior.get("detail", "idempotent"),
                           already_had_role=bool(prior.get("already_had_role")))
    if not store.see_nonce(req.nonce):
        return GrantResult(False, "REPLAYED_NONCE", 401)
    bind_err = store.bind(req.x_user_id, req.discord_user_id)
    if bind_err:
        return GrantResult(False, bind_err, 409)
    if member is None:
        return GrantResult(False, "MEMBER_NOT_IN_GUILD", 404)
    if member.bot:
        return GrantResult(False, "TARGET_IS_BOT", 403)
    if str(member.user_id) != str(req.discord_user_id):
        return GrantResult(False, "DISCORD_IDENTITY_MISMATCH", 403)
    if member.pending is not False:
        return GrantResult(False, "DISCORD_RULES_NOT_ACCEPTED", 403)
    if rules_role is None:
        return GrantResult(False, "RULES_ROLE_MISSING", 503)
    if rules_role.role_id not in member.role_ids:
        return GrantResult(False, "MISSING_RULES_ACCEPTED_ROLE", 403)
    if member_role is None:
        return GrantResult(False, "MEMBER_ROLE_MISSING", 503)
    if role_is_dangerous(member_role):
        return GrantResult(False, "MEMBER_ROLE_PRIVILEGED", 503)
    if not can_bot_assign(bot, member_role):
        return GrantResult(False, "BOT_HIERARCHY_INSUFFICIENT", 503)
    if member_role.role_id in member.role_ids:
        result = GrantResult(True, "ALREADY_MEMBER", 200, already_had_role=True)
        store.put_idempotency(req.idempotency_key, {"code": result.code, "detail": result.detail, "already_had_role": True})
        return result
    result = GrantResult(True, "GRANT_AUTHORIZED", 200)
    store.put_idempotency(req.idempotency_key, {"code": result.code, "detail": result.detail, "already_had_role": False})
    return result


def parse_grant_headers_and_body(headers: dict, body: dict) -> GrantRequest:
    return GrantRequest(
        discord_user_id=str(body.get("discord_user_id") or ""),
        x_user_id=str(body.get("x_user_id") or ""),
        guild_id=str(body.get("guild_id") or ""),
        idempotency_key=str(body.get("idempotency_key") or ""),
        timestamp=str(headers.get("X-GN-Timestamp") or body.get("timestamp") or ""),
        nonce=str(headers.get("X-GN-Nonce") or body.get("nonce") or ""),
        signature=str(headers.get("X-GN-Signature") or body.get("signature") or ""),
        request_id=str(body.get("request_id") or ""),
    )


def register_member_grant_routes(app, *, store: ReplayStore, guild_resolver: Callable):
    from aiohttp import web

    async def handler(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "code": "INVALID_JSON"}, status=400)
        hdrs = {k: request.headers.get(k, "") for k in ("X-GN-Timestamp", "X-GN-Nonce", "X-GN-Signature")}
        req = parse_grant_headers_and_body(hdrs, body if isinstance(body, dict) else {})
        ctx = guild_resolver()
        member = await ctx.fetch_member(req.discord_user_id)
        result = evaluate_grant(
            req, store=store, member=member, rules_role=ctx.rules_role(),
            member_role=ctx.member_role(), bot=ctx.bot_capability(),
        )
        if not result.ok:
            return web.json_response({"ok": False, "code": result.code, "detail": result.detail}, status=result.status)
        if result.code == "GRANT_AUTHORIZED":
            role = ctx.member_role()
            try:
                await ctx.add_member_role(req.discord_user_id, role.role_id)
            except Exception as exc:
                return web.json_response({"ok": False, "code": "DISCORD_ROLE_ADD_FAILED", "detail": type(exc).__name__}, status=502)
        return web.json_response({"ok": True, "code": result.code, "already_had_role": result.already_had_role})

    app.router.add_post("/internal/member-grant", handler)
    return app
