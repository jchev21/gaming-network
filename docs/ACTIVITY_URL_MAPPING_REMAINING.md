# Remaining real Discord Activity URL-mapping test

Superseded in detail by **`ACTIVITY_PORTAL_BATCH10.md`** (Batch 10).

Issue #67 / PR #74 shell is on `main`. Production Talk → Activity → Hub still requires owner Developer Portal configuration.

## Required mappings (targets **without** `https://`)

| PREFIX | TARGET |
|--------|--------|
| `/` | your Activity HTTPS host (directory root) |
| `/sdk` | `cdn.jsdelivr.net/npm` |

Then: Activities → Settings → **Enable Activities**.

Offline: `python3 test_activity_portal_preflight.py` → must PASS before portal work.
Live D1–D9: fill the checklist in `ACTIVITY_PORTAL_BATCH10.md` — not claimed PASS by automation.
