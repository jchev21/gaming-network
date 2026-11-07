"""Secure server-to-server Member role grant for XYZ.HUB (issue #78).

Batch 5 security contract:
- Bind X\u2194Discord ONLY after membership, screening, Rules Accepted, and role-safety checks pass.
- Record durable SUCCESS only after Discord confirms the Member role was added (or already present).
- Persist nonces, in-flight attempts, and idempotency receipts under /data; fail closed if journal unwritable.
- Ambiguous / failed Discord role adds do not grant access and remain retryable without false success.

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
import tempfile
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
ATTEMPT_TTL_SECONDS = 900

DANGEROUS_PERMS = (
    "administrator", "manage_guild", "manage_roles", "manage_channels",
    "manage_webhooks", "manage_messages", "ban_members", "kick_members",
    "moderate_members",
)

SUCCESS_CODES = frozenset({"GRANT_CONFIRMED", "ALREADY_MEMBER", "IDEMPOTENT_SUCCESS"})


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
    needs_discord_apply: bool = False


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


class DurableStoreError(RuntimeError):
    """Raised when anti-replay journal cannot be written (fail closed)."""


class ReplayStore:
    """Restart-safe nonce / attempt / idempotency / binding store."""

    def __init__(
        self, path: Optional[Path] = None, now: Callable[[], float] = time.time,
        *, require_persist: bool = False,
    ):
        self.path = Path(path) if path else None
        self.now = now
        self.require_persist = require_persist or (self.path is not None)
        self._nonces: dict[str, float] = {}
        self._idem: dict[str, dict] = {}
        self._attempts: dict[str, dict] = {}
        self._bindings: dict[str, str] = {}
        self._rev_bindings: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            if self.require_persist:
                raise DurableStoreError("member-grant journal unreadable")
            return
        self._bindings = {str(k): str(v) for k, v in (data.get("bindings") or {}).items()}
        self._rev_bindings = {v: k for k, v in self._bindings.items()}
        t = self.now()
        self._nonces = {str(k): float(v) for k, v in (data.get("nonces") or {}).items() if float(v) > t}
        self._idem = {str(k): v for k, v in (data.get("idempotency") or {}).items() if float(v.get("exp", 0)) > t}
        self._attempts = {str(k): v for k, v in (data.get("attempts") or {}).items() if float(v.get("exp", 0)) > t}

    def _purge(self) -> None:
        t = self.now()
        self._nonces = {k: exp for k, exp in self._nonces.items() if exp > t}
        self._idem = {k: v for k, v in self._idem.items() if float(v.get("exp", 0)) > t}
        self._attempts = {k: v for k, v in self._attempts.items() if float(v.get("exp", 0)) > t}

    def _persist(self) -> None:
        if not self.path:
            if self.require_persist:
                raise DurableStoreError("member-grant journal path not configured")
            return
        self._purge()
        payload = {
            "bindings": self._bindings,
            "nonces": self._nonces,
            "idempotency": self._idem,
            "attempts": self._attempts,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".member_grant_", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, indent=2, sort_keys=True)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, self.path)
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except OSError as exc:
            raise DurableStoreError(f"member-grant journal write failed: {exc}") from exc

    def see_nonce(self, nonce: str) -> bool:
        self._purge()
        if not nonce or len(nonce) < 16 or len(nonce) > 128:
            return False
        if nonce in self._nonces:
            return False
        self._nonces[nonce] = self.now() + NONCE_TTL_SECONDS
        self._persist()
        return True

    def get_idempotency(self, key: str) -> Optional[dict]:
        self._purge()
        return self._idem.get(key)

    def get_attempt(self, key: str) -> Optional[dict]:
        self._purge()
        return self._attempts.get(key)

    def begin_attempt(self, key: str, x_user_id: str, discord_user_id: str) -> None:
        self._purge()
        self._attempts[key] = {
            "phase": "authorized_pending_discord",
            "x": x_user_id,
            "discord": discord_user_id,
            "exp": self.now() + ATTEMPT_TTL_SECONDS,
        }
        self._persist()

    def clear_attempt(self, key: str) -> None:
        self._attempts.pop(key, None)
        self._persist()

    def put_success(self, key: str, *, code: str, already_had_role: bool) -> None:
        self._purge()
        self._attempts.pop(key, None)
        self._idem[key] = {
            "code": code, "ok": True, "already_had_role": already_had_role,
            "phase": "success", "exp": self.now() + IDEMPOTENCY_TTL_SECONDS,
        }
        self._persist()

    def check_binding_conflict(self, x_user_id: str, discord_user_id: str) -> Optional[str]:
        prior_d = self._bindings.get(x_user_id)
        if prior_d and prior_d != discord_user_id:
            return "X_ALREADY_BOUND_TO_OTHER_DISCORD"
        prior_x = self._rev_bindings.get(discord_user_id)
        if prior_x and prior_x != x_user_id:
            return "DISCORD_ALREADY_BOUND_TO_OTHER_X"
        return None

    def pending_identity_conflict(self, x_user_id: str, discord_user_id: str,
                                  idempotency_key: str) -> Optional[str]:
        self._purge()
        for key, attempt in self._attempts.items():
            if key == idempotency_key:
                if (attempt.get("x") != x_user_id or
                        attempt.get("discord") != discord_user_id):
                    return "IDEMPOTENCY_IDENTITY_MISMATCH"
                return "GRANT_PENDING_RECONCILIATION"
            if attempt.get("x") == x_user_id or attempt.get("discord") == discord_user_id:
                return "GRANT_ATTEMPT_IDENTITY_CONFLICT"
        return None

    def commit_binding(self, x_user_id: str, discord_user_id: str) -> Optional[str]:
        conflict = self.check_binding_conflict(x_user_id, discord_user_id)
        if conflict:
            return conflict
        self._bindings[x_user_id] = discord_user_id
        self._rev_bindings[discord_user_id] = x_user_id
        self._persist()
        return None


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
    if prior and prior.get("ok") and prior.get("phase") == "success":
        return GrantResult(True, prior.get("code", "IDEMPOTENT_SUCCESS"), 200,
                           detail="idempotent success",
                           already_had_role=bool(prior.get("already_had_role")))

    try:
        if not store.see_nonce(req.nonce):
            return GrantResult(False, "REPLAYED_NONCE", 401)
    except DurableStoreError:
        return GrantResult(False, "JOURNAL_UNAVAILABLE", 503, "anti-replay journal unavailable")

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

    conflict = store.check_binding_conflict(req.x_user_id, req.discord_user_id)
    if conflict:
        return GrantResult(False, conflict, 409)

    pending = store.pending_identity_conflict(
        req.x_user_id, req.discord_user_id, req.idempotency_key
    )
    if pending and pending != "GRANT_PENDING_RECONCILIATION":
        return GrantResult(False, pending, 409)

    if member_role.role_id in member.role_ids:
        if pending == "GRANT_PENDING_RECONCILIATION":
            return confirm_grant(
                store, req.idempotency_key, member_after=member, member_role=member_role
            )
        try:
            bind_err = store.commit_binding(req.x_user_id, req.discord_user_id)
            if bind_err:
                return GrantResult(False, bind_err, 409)
            store.put_success(req.idempotency_key, code="ALREADY_MEMBER", already_had_role=True)
        except DurableStoreError:
            return GrantResult(False, "JOURNAL_UNAVAILABLE", 503)
        return GrantResult(True, "ALREADY_MEMBER", 200, already_had_role=True)

    if pending:
        return GrantResult(False, "GRANT_PENDING_RECONCILIATION", 409)

    # Reserve the signed identity pair durably before calling Discord, but
    # do NOT make a permanent 1:1 binding until the role is confirmed.
    try:
        store.begin_attempt(req.idempotency_key, req.x_user_id, req.discord_user_id)
    except DurableStoreError:
        return GrantResult(False, "JOURNAL_UNAVAILABLE", 503)

    return GrantResult(
        True, "GRANT_AUTHORIZED", 200, needs_discord_apply=True,
        detail="authorized; awaiting Discord role confirmation",
    )


def confirm_grant(
    store: ReplayStore, idempotency_key: str, *,
    member_after: MemberSnapshot, member_role: RoleSnapshot,
) -> GrantResult:
    if member_role.role_id not in member_after.role_ids:
        try:
            store.clear_attempt(idempotency_key)
        except DurableStoreError:
            return GrantResult(False, "JOURNAL_UNAVAILABLE", 503)
        return GrantResult(False, "DISCORD_ROLE_NOT_PRESENT", 502,
                           detail="Discord add_roles returned but Member role not observed")
    attempt = store.get_attempt(idempotency_key)
    if not attempt or str(member_after.user_id) != str(attempt.get("discord")):
        return GrantResult(False, "GRANT_ATTEMPT_IDENTITY_MISMATCH", 409)
    try:
        bind_err = store.commit_binding(str(attempt["x"]), str(attempt["discord"]))
        if bind_err:
            return GrantResult(False, bind_err, 409)
        store.put_success(idempotency_key, code="GRANT_CONFIRMED", already_had_role=False)
    except DurableStoreError:
        return GrantResult(False, "JOURNAL_UNAVAILABLE", 503)
    return GrantResult(True, "GRANT_CONFIRMED", 200, already_had_role=False)


def abort_grant_attempt(store: ReplayStore, idempotency_key: str) -> None:
    try:
        store.clear_attempt(idempotency_key)
    except DurableStoreError:
        pass


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


def register_member_grant_routes(app, *, store: ReplayStore, guild_resolver: Callable, rate_limit_per_minute: int = 30):
    from aiohttp import web
    from collections import defaultdict

    hits: dict[str, list[float]] = defaultdict(list)

    def _rate_ok(key: str) -> bool:
        now = time.time()
        window = hits[key]
        hits[key] = [t for t in window if now - t < 60]
        if len(hits[key]) >= rate_limit_per_minute:
            return False
        hits[key].append(now)
        return True

    async def handler(request: web.Request) -> web.Response:
        peer = request.remote or "unknown"
        if not _rate_ok(peer):
            return web.json_response({"ok": False, "code": "RATE_LIMITED"}, status=429)
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "code": "INVALID_JSON"}, status=400)
        if not isinstance(body, dict) or len(json.dumps(body)) > 4096:
            return web.json_response({"ok": False, "code": "INVALID_JSON"}, status=400)

        hdrs = {k: request.headers.get(k, "") for k in ("X-GN-Timestamp", "X-GN-Nonce", "X-GN-Signature")}
        req = parse_grant_headers_and_body(hdrs, body)
        ctx = guild_resolver()
        member = await ctx.fetch_member(req.discord_user_id)
        try:
            result = evaluate_grant(
                req, store=store, member=member, rules_role=ctx.rules_role(),
                member_role=ctx.member_role(), bot=ctx.bot_capability(),
            )
        except DurableStoreError:
            return web.json_response({"ok": False, "code": "JOURNAL_UNAVAILABLE"}, status=503)

        if not result.ok:
            return web.json_response({"ok": False, "code": result.code}, status=result.status)

        if result.needs_discord_apply:
            role = ctx.member_role()
            try:
                await ctx.add_member_role(req.discord_user_id, role.role_id)
            except Exception:
                abort_grant_attempt(store, req.idempotency_key)
                return web.json_response({"ok": False, "code": "DISCORD_ROLE_ADD_FAILED"}, status=502)
            member_after = await ctx.fetch_member(req.discord_user_id)
            if member_after is None:
                abort_grant_attempt(store, req.idempotency_key)
                return web.json_response({"ok": False, "code": "DISCORD_ROLE_ADD_FAILED"}, status=502)
            confirmed = confirm_grant(store, req.idempotency_key, member_after=member_after, member_role=role)
            if not confirmed.ok:
                return web.json_response({"ok": False, "code": confirmed.code}, status=confirmed.status)
            return web.json_response({"ok": True, "code": confirmed.code, "already_had_role": False})

        return web.json_response({"ok": True, "code": result.code, "already_had_role": result.already_had_role})

    app.router.add_post("/internal/member-grant", handler)
    return app
