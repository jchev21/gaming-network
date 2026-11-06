# Batch 3 — NativeChannelHubView._refresh collision (issue #50)

**Base:** `fix/discord-dashboard-response` @ `c92485ce84ae17394797d31075ef434abeab21f2`  
**Blob before change:** `f49220e83fc400dd4343397c286c997424f52e0d`  
**Issue:** #50 (Reliability: NativeChannelHubView._refresh method collision)

## Change (narrow)
Rename only:
- `button.callback = self._refresh_feed`
- `async def _refresh_feed(...)` (was `_refresh`)

Name chosen to match the explicit recommendation in #50 (`_refresh_feed`).

## Evidence
- `python3 -m py_compile` on fully patched source: **PASS**
- Offline regression `test_native_hub_refresh_collision.py`: **PASS** (4 tests)
- No other files or behavior changed
- No Railway / secrets / polling / deployment

## Apply
```bash
git checkout fix/discord-dashboard-response
git checkout -b grok/batch3-hubview-refresh-collision-clean
git apply BATCH3/NATIVE_HUB_REFRESH_COLLISION_FIX.diff
python3 -m py_compile discord-bot/bot.py
python3 BATCH3/test_native_hub_refresh_collision.py
```

Human post-deploy check (owner only): `/hubview` → select feeds → press Refresh repeatedly; confirm no new unawaited-coroutine warning in bot logs.
