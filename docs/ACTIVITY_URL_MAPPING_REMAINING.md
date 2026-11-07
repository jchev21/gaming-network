# Remaining real Discord Activity URL-mapping test

Issue #67 / PR #74 delivered a single-document interactive Activity shell offline.
**Production Talk → Activity → Hub still requires owner portal configuration.**

## Exact remaining steps (owner)

1. Discord Developer Portal → Application (client id `1566288861259108424`) → **Activities**.
2. Set **URL Mapping**:
   - `/` → HTTPS origin serving Batch 2 `index.html` (branch `grok/activity-interaction-fix-1106` / PR #74 once approved)
   - `/sdk` → Embedded App SDK proxy for `@discord/embedded-app-sdk@2.5.0`
3. Confirm Activity is enabled for the target guild and visible in Talk → Activity shelf.
4. Real-user checks D1–D9 (connection badge, feeds, layout, privacy, `/hubview` independent).

## Evidence to record

| Check | Pass criteria |
|-------|---------------|
| Portal `/` mapping | Single HTML document, no dual-doctype |
| Portal `/sdk` mapping | Module import succeeds |
| Talk → Activity → Hub | Interactive controls |
| Badge state | connected / authorized / explicit error |

This is the **only** remaining Activity regression gate that cannot be completed offline.
