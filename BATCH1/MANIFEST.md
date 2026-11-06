# Batch 1 — Clean rebuild (no placeholder bot.py)

**Intended branch:** `grok/batch1-hubview-refresh-rename`
**Base:** `fix/discord-dashboard-response` @ `c92485ce84ae17394797d31075ef434abeab21f2`
**Blob before change:** `f49220e83fc400dd4343397c286c997424f52e0d`

## What changed
Only the narrow rename in `discord-bot/bot.py`:
- `button.callback = self._on_refresh_feed`
- `async def _on_refresh_feed(...)` (was `_refresh`)

## Evidence
- `python3 -m py_compile` on the fully patched file: **PASS**
- Offline AST name check (`test_native_hub_refresh_name.py`): **PASS** against patched source
- No other files touched
- No Railway / secrets / polling changes

## How to apply cleanly
```bash
git checkout fix/discord-dashboard-response
git checkout -b grok/batch1-hubview-refresh-rename-clean
git apply BATCH1/NATIVE_HUB_REFRESH_PATCH.diff
python3 -m py_compile discord-bot/bot.py
python3 BATCH1/test_native_hub_refresh_name.py
```

Or have the integrator apply the two-line rename via a full-file write from the verified base blob.

## Human checks still pending (#17)
- Live `/hubview` Refresh after deploy
- `/dashboard` buttons
- Discord Activity connected state

**Do not merge any intermediate branch that contains a PLACEHOLDER bot.py.**
