#!/usr/bin/env python3
"""Batch 10 — offline Activity portal readiness preflight (#67).

Does not contact Discord. Verifies the static shell is safe to map in the
Developer Portal (single document, SDK path, client ID, privacy strings).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CANDIDATES = [ROOT, ROOT.parent, Path.cwd()]


def find_root() -> Path:
    for base in CANDIDATES:
        if (base / "index.html").exists() and (base / "activity-sdk.js").exists():
            return base
    raise SystemExit("index.html + activity-sdk.js not found (run from repo root)")


def main() -> int:
    root = find_root()
    html = (root / "index.html").read_text(encoding="utf-8")
    sdk = (root / "activity-sdk.js").read_text(encoding="utf-8")
    failures: list[str] = []

    doctypes = len(re.findall(r"<!DOCTYPE\s+html", html, flags=re.I))
    if doctypes != 1:
        failures.append(f"expected exactly 1 DOCTYPE, found {doctypes} (dual-HTML regression)")

    if html.lower().count("<html") != 1:
        failures.append("expected exactly one <html> root")

    if "/sdk/@discord/embedded-app-sdk@2.5.0" not in sdk:
        failures.append("activity-sdk.js must import /sdk/@discord/embedded-app-sdk@2.5.0")

    if "1566288861259108424" not in sdk:
        failures.append("CLIENT_ID 1566288861259108424 missing from activity-sdk.js")

    for needle in (
        'data-feed="welcome"',
        'id="layout-1"',
        'id="layout-2"',
        'id="btn-refresh"',
        'id="connection-badge"',
        'id="board"',
        'id="btn-roll"',
    ):
        if needle not in html:
            failures.append(f"missing interactive marker: {needle}")

    privacy_bits = ("private", "redemption", "Public feeds only", "public/sample")
    if not any(b.lower() in html.lower() for b in privacy_bits):
        failures.append("privacy copy missing from shell")

    if "YOUR_DISCORD_APPLICATION_ID" in html or "YOUR_DISCORD_APPLICATION_ID" in sdk:
        failures.append("placeholder application id still present")

    if "activity-sdk.js" not in html:
        failures.append("index.html does not load activity-sdk.js")

    if failures:
        print("FAIL — Activity portal preflight")
        for f in failures:
            print(" -", f)
        return 1

    print("PASS — Activity portal preflight")
    print(f" root: {root}")
    print(" single-document: yes")
    print(" sdk mapping path: /sdk/@discord/embedded-app-sdk@2.5.0")
    print(" client id: 1566288861259108424")
    print(" interactive feeds/layout/games: present")
    print(" Next: owner configures Developer Portal URL mappings (see ACTIVITY_PORTAL_BATCH10.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
