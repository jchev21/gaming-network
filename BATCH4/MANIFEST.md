# Batch 4 — Add Event modal interaction timing (10062 risk)

**Production base:** `fix/discord-dashboard-response` @ `4f4397dab18df198c116ac46695b5f3f2f12d825` (post PR #62)

## Problem
`AddEventModal.on_submit` on production source did sync `save_data()` **before** `interaction.response.send_message(...)`. Discord requires the first response to a modal submit within ~3s. Disk I/O before acknowledge is a classic `10062 Unknown interaction` cause, matching historical launch notes on the Add event path.

PR #20 fixed *opening* the modal (immediate `send_modal`, no defer) and moved PIL off the loop for panel buttons; it did not reorder `on_submit`.

**AST evidence (unpatched):** `save_data` appears before `send_message`.

## Narrow fix
- Build event in memory
- **Acknowledge with `send_message` first**
- Then `await asyncio.to_thread(save_data)`
- Then `await refresh_all_dashboards()`

`b_add` remains immediate `send_modal` with no defer (already correct).

## Evidence
- `python3 -m py_compile` on patched source: **PASS**
- Offline timing regression (4 tests): **PASS**
- No Railway / token / polling changes; no deployment

## Apply
Apply `BATCH4/ADD_EVENT_MODAL_TIMING_FIX.diff` onto `discord-bot/bot.py` at base `4f4397da…`, then run:
```bash
python3 -m py_compile discord-bot/bot.py
python3 BATCH4/test_add_event_modal_timing.py
```

Human check after approved deploy: `/dashboard` → Add event → submit valid and invalid dates; confirm no 10062 and calendar updates.
