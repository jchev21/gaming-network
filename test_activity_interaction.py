"""Batch 2 offline tests — Activity shell interaction + structure.

Run from gaming-network repo root:
  python3 test_activity_interaction.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_single_html_document() -> None:
    html = read("index.html")
    assert html.count("<!DOCTYPE html>") == 1, "must be exactly one HTML document"
    assert html.count("</html>") == 1


def test_sdk_script_loaded() -> None:
    html = read("index.html")
    assert 'src="./activity-sdk.js"' in html or "src='./activity-sdk.js'" in html


def test_connection_status_elements() -> None:
    html = read("index.html")
    assert 'id="discord-status"' in html
    assert 'id="connection-badge"' in html


def test_feed_selectors_present() -> None:
    html = read("index.html")
    for feed in ("welcome", "public-x", "calendar", "local"):
        assert f'data-feed="{feed}"' in html, f"missing feed {feed}"


def test_layout_controls_present() -> None:
    html = read("index.html")
    assert 'id="layout-1"' in html
    assert 'id="layout-2"' in html
    assert 'id="btn-refresh"' in html


def test_no_private_discord_fetch() -> None:
    html = read("index.html")
    js = read("activity-sdk.js")
    banned = (
        "channels.messages",
        "getChannel",
        "listMessages",
        "bot.token",
        "DISCORD_TOKEN",
        "messages.read",
    )
    for token in banned:
        assert token not in html and token not in js, f"must not reference {token}"


def test_privacy_copy_present() -> None:
    html = read("index.html")
    assert "Private Discord channel messages" in html or "private Discord" in html.lower()


def test_sdk_scopes_identify_only() -> None:
    js = read("activity-sdk.js")
    assert "identify" in js
    for scope in ("guilds", "messages.read", "rpc.activities.write", "bot"):
        if re.search(rf'["\']({scope})["\']', js):
            raise AssertionError(f"unexpected scope {scope}")


def test_sdk_exports_connect() -> None:
    js = read("activity-sdk.js")
    assert "export async function connectActivity" in js or "function connectActivity" in js
    assert "discordSdk.ready()" in js
    assert "discordSdk.commands.authorize" in js


def test_connection_states_documented() -> None:
    js = read("activity-sdk.js")
    for state in ("connecting", "ready", "authorized", "browser", "error"):
        assert state in js, f"missing state {state}"


def test_interaction_api_exposed() -> None:
    html = read("index.html")
    assert "__GN_ACTIVITY__" in html
    assert "selectFeed" in html
    assert "showPage" in html


def test_client_id() -> None:
    js = read("activity-sdk.js")
    assert "1566288861259108424" in js


def main() -> int:
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
        except FileNotFoundError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
