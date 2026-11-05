#!/usr/bin/env python3
"""
Gaming Network — offline launch preflight checks.

Validates project layout, config schema expectations, required non-secret
environment variable *names*, intents declarations, command registration
patterns, and persistence assumptions. Never prints secret values.
Never contacts Discord, Railway, or any network service.
"""

from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = REPO_ROOT / "discord-bot"
BOT_PY = BOT_DIR / "bot.py"
REQ_TXT = BOT_DIR / "requirements.txt"
RAILWAY_JSON = BOT_DIR / "railway.json"
DESIRED = Path(__file__).resolve().parent / "desired_guild_structure.json"

# Non-secret env var *names* expected for production. Values are never read
# or printed by this tool (except presence checks when explicitly allowed).
EXPECTED_ENV_NAMES = [
    "DISCORD_TOKEN",  # secret — presence only, never print value
    "DATA_DIR",
    "PYTHONUNBUFFERED",
    "GAMING_API_URL",
    "API_SERVICE_TOKEN",  # secret reference name only
]

REQUIRED_FILES = [
    BOT_PY,
    REQ_TXT,
    RAILWAY_JSON,
    DESIRED,
    Path(__file__).resolve().parent / "guild_planner.py",
]


class CheckResult:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.warnings: list[str] = []
        self.failures: list[str] = []
        self.owner_actions: list[str] = []

    @property
    def status(self) -> str:
        if self.failures:
            return "BLOCKED"
        if self.warnings or self.owner_actions:
            return "READY_FOR_MANUAL_SMOKE_TEST"
        return "READY_FOR_MANUAL_SMOKE_TEST"


def check_files(result: CheckResult) -> None:
    for p in REQUIRED_FILES:
        if p.exists():
            result.passed.append(f"Found required file: {p.relative_to(REPO_ROOT)}")
        else:
            result.failures.append(f"Missing required file: {p.relative_to(REPO_ROOT)}")


def check_requirements(result: CheckResult) -> None:
    if not REQ_TXT.exists():
        return
    text = REQ_TXT.read_text(encoding="utf-8").lower()
    if "discord.py" in text:
        result.passed.append("requirements.txt lists discord.py")
    else:
        result.failures.append("requirements.txt missing discord.py")
    if "aiohttp" in text:
        result.passed.append("requirements.txt lists aiohttp")
    else:
        result.warnings.append("requirements.txt does not list aiohttp (bot uses it)")


def check_bot_intents_and_patterns(result: CheckResult) -> None:
    if not BOT_PY.exists():
        return
    source = BOT_PY.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        result.failures.append(f"bot.py failed to parse: {e}")
        return

    # Intents
    if "intents.message_content" in source and "True" in source:
        result.passed.append("bot.py enables message_content intent (privileged)")
        result.owner_actions.append(
            "Confirm Message Content Intent is enabled in Discord Developer Portal for this bot."
        )
    else:
        result.warnings.append("message_content intent not clearly enabled in bot.py")

    if "intents.members" in source and "True" in source:
        result.passed.append("bot.py enables members intent (privileged)")
        result.owner_actions.append(
            "Confirm Server Members Intent is enabled in Discord Developer Portal for this bot."
        )
    else:
        result.warnings.append("members intent not clearly enabled in bot.py")

    # DATA_DIR / persistence
    if "DATA_DIR" in source:
        result.passed.append("bot.py respects DATA_DIR for volume-backed persistence")
    else:
        result.warnings.append("DATA_DIR not referenced in bot.py")

    if "config.json" in source and "hub_data.json" in source:
        result.passed.append("bot.py references config.json and hub_data.json")
    else:
        result.warnings.append("Expected persistence filenames not found in bot.py")

    # Dashboard bind — must stay loopback
    if "127.0.0.1" in source or "localhost" in source:
        result.passed.append("Dashboard appears bound to loopback (127.0.0.1/localhost)")
    else:
        result.warnings.append(
            "Could not confirm dashboard binds to loopback only. Do not expose port 8765 publicly."
        )
    result.owner_actions.append(
        "Never attach a public domain to the discord-hub-bot Railway service. Dashboard is loopback-only."
    )

    # Interaction patterns — defer / response
    handler_names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            handler_names.add(node.name)

    for expected in ("setup_hook", "on_ready", "on_message"):
        if expected in handler_names:
            result.passed.append(f"Found lifecycle handler: {expected}")
        else:
            result.warnings.append(f"Missing expected handler: {expected}")

    # Known interaction issue documentation hook
    if "send_modal" in source or "b_add" in source:
        result.passed.append("Add Event / modal path present in bot.py")
        result.owner_actions.append(
            "Manual smoke: open Add Event modal and confirm interaction is acknowledged "
            "(avoid Discord 10062 Unknown interaction). See launch/SMOKE_TESTS.md."
        )


def check_desired_structure(result: CheckResult) -> None:
    if not DESIRED.exists():
        return
    try:
        data = json.loads(DESIRED.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        result.failures.append(f"desired_guild_structure.json invalid JSON: {e}")
        return
    cats = data.get("categories") or []
    roles = data.get("roles") or []
    if not cats:
        result.failures.append("desired structure has no categories")
    else:
        result.passed.append(f"Desired structure defines {len(cats)} categories")
    if not roles:
        result.failures.append("desired structure has no roles")
    else:
        result.passed.append(f"Desired structure defines {len(roles)} roles")
    admin_roles = [
        r["name"]
        for r in roles
        if "administrator" in [p.lower() for p in (r.get("permissions") or [])]
    ]
    if admin_roles:
        result.warnings.append(
            f"Desired structure includes Administrator role(s): {admin_roles}. Assign sparingly."
        )


def check_env_names_documented(result: CheckResult) -> None:
    """Only check that names are documented; never print values."""
    env_doc = Path(__file__).resolve().parent / "ENVIRONMENT_TEMPLATE.md"
    if env_doc.exists():
        text = env_doc.read_text(encoding="utf-8")
        for name in EXPECTED_ENV_NAMES:
            if name in text:
                result.passed.append(f"Env name documented: {name}")
            else:
                result.warnings.append(f"Env name not found in ENVIRONMENT_TEMPLATE.md: {name}")
    else:
        result.warnings.append("ENVIRONMENT_TEMPLATE.md missing — env names not documented yet")

    # Presence of secrets in process env is NOT required for offline preflight.
    # We only warn if someone accidentally exported a token into the CI environment
    # and we refuse to echo it.
    if os.environ.get("DISCORD_TOKEN"):
        result.warnings.append(
            "DISCORD_TOKEN is set in this environment. Preflight will not print it. "
            "Ensure CI does not log secret values."
        )


def check_railway_config(result: CheckResult) -> None:
    if not RAILWAY_JSON.exists():
        result.warnings.append("railway.json missing")
        return
    try:
        data = json.loads(RAILWAY_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        result.failures.append(f"railway.json invalid: {e}")
        return
    deploy = data.get("deploy") or {}
    start = deploy.get("startCommand") or ""
    if "bot.py" in start:
        result.passed.append(f"railway.json startCommand references bot.py: {start}")
    else:
        result.warnings.append(f"Unexpected startCommand: {start}")
    result.owner_actions.append(
        "Railway: keep discord-hub-data volume mounted at /data. Do not rotate tokens or change env from this package."
    )


def run_preflight() -> CheckResult:
    result = CheckResult()
    check_files(result)
    check_requirements(result)
    check_bot_intents_and_patterns(result)
    check_desired_structure(result)
    check_env_names_documented(result)
    check_railway_config(result)
    return result


def main() -> int:
    result = run_preflight()
    print("=== Gaming Network Launch Preflight (offline) ===")
    print(f"Status: {result.status}")
    print()
    if result.passed:
        print("PASSED:")
        for p in result.passed:
            print(f"  ✓ {p}")
        print()
    if result.warnings:
        print("WARNINGS:")
        for w in result.warnings:
            print(f"  ! {w}")
        print()
    if result.failures:
        print("FAILURES:")
        for f in result.failures:
            print(f"  ✗ {f}")
        print()
    if result.owner_actions:
        print("OWNER ACTIONS (manual):")
        for a in result.owner_actions:
            print(f"  → {a}")
        print()
    print("No network calls were made. No secrets were printed.")
    return 1 if result.failures else 0


if __name__ == "__main__":
    sys.exit(main())
