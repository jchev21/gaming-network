"""Offline regression checks for Discord Activity shell (issue #67 / Batch 1).

Run from gaming-network repo root:
  python3 test_activity_regression_offline.py

Does not contact Discord. Does not require tokens.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_index_has_activity_script() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "activity-sdk.js" in html, "index.html must load activity-sdk.js"


def test_index_is_duplicated_document() -> None:
    """Documents the known structural defect that contributes to unstable UI."""
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    count = html.count("<!DOCTYPE html>")
    assert count >= 2, f"expected dual HTML document, found {count}"


def test_sdk_client_id_and_scope() -> None:
    js = (ROOT / "activity-sdk.js").read_text(encoding="utf-8")
    assert "1566288861259108424" in js, "client id must match Discord application"
    assert "identify" in js, "identify scope expected"
    # Fail if broader scopes appear without deliberate review
    for forbidden in ("guilds", "messages.read", "rpc.activities.write"):
        # allow in comments only — simple check: if present as scope string fail
        if f'"{forbidden}"' in js or f"'{forbidden}'" in js:
            raise AssertionError(f"unexpected scope token {forbidden} in activity-sdk.js")


def test_sdk_calls_ready_and_authorize() -> None:
    js = (ROOT / "activity-sdk.js").read_text(encoding="utf-8")
    assert "discordSdk.ready()" in js
    assert "discordSdk.commands.authorize" in js


def test_no_private_message_fetch_in_shell() -> None:
    js = (ROOT / "activity-sdk.js").read_text(encoding="utf-8")
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    for token in ("channels.messages", "getChannel", "listMessages", "bot.token"):
        assert token not in js and token not in html, f"shell must not reference {token}"


def main() -> int:
    tests = [
        test_index_has_activity_script,
        test_index_is_duplicated_document,
        test_sdk_client_id_and_scope,
        test_sdk_calls_ready_and_authorize,
        test_no_private_message_fetch_in_shell,
    ]
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
            print(f"FAIL  {t.__name__}: missing file {e.filename}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
