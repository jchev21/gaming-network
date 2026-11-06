# Batch 1 — Native /hubview Refresh collision fix

**Issue refs:** #17 (launch), #2 (master), known RuntimeWarning on production bot logs 2026-11-05 22:44:42 UTC.

## Root cause
`NativeChannelHubView` (subclass of `discord.ui.LayoutView`) defined:
```python
async def _refresh(self, interaction):
```
and bound `button.callback = self._refresh`.

discord.py internally calls the synchronous `LayoutView._refresh(components)` for component layout bookkeeping. The name collision caused:
```
RuntimeWarning: coroutine 'NativeChannelHubView._refresh' was never awaited
  view._refresh(components)
```
and skipped normal refresh bookkeeping. Commands still responded for the owner, but the warning is a reliability defect.

## Exact isolated patch (apply to `discord-bot/bot.py`)

```diff
--- a/discord-bot/bot.py
+++ b/discord-bot/bot.py
@@ -1234,7 +1234,7 @@ class NativeChannelHubView(discord.ui.LayoutView):
             ))
         button = discord.ui.Button(label="Refresh feed", emoji="🔄", style=discord.ButtonStyle.secondary, custom_id="gn:channelhub:refresh")
-        button.callback = self._refresh
+        button.callback = self._on_refresh_feed
         container.add_item(discord.ui.ActionRow(button))
         container.add_item(discord.ui.TextDisplay(
             "Read-only · public X data or this channel only. For the full multi-server Studio, use Gaming Network → Launch in Discord App Launcher."
@@ -1264,7 +1264,8 @@ class NativeChannelHubView(discord.ui.LayoutView):
             return await interaction.response.send_message("Invalid feed selection.", ephemeral=True)
         await self._redraw(interaction, panel)

-    async def _refresh(self, interaction):
+    async def _on_refresh_feed(self, interaction):
+        """User-facing Refresh button. Named to avoid colliding with discord.ui.LayoutView._refresh."""
         rec = data.get("native_hubs", {}).get(str(interaction.message.id), {})
         panel = rec.get("panel", "channel")
         await self._redraw(interaction, panel if panel in NATIVE_HUB_FEEDS else "channel")
```

## Verification performed (code-level only)
- Confirmed on branch `fix/discord-dashboard-response` @ `c92485ce` / blob `f49220e8`.
- No other `self._refresh` or `def _refresh` remain after rename.
- `/hubview` command, select callback, `_redraw`, and public X / calendar / leaderboard / rewards panels are otherwise unchanged.
- DashboardView and image fingerprint path (PR #32) untouched.

## Human checks still pending (cannot be closed remotely)
Per #17:
- [ ] Owner Manage-Server `/hubview` in live text channel: selector ABOVE content, This Channel / Public X / Calendar / Refresh, no 429.
- [ ] Original `/dashboard` Calendar / Leaderboard / Rewards / Add event still work; data survives redeploy.
- [ ] Discord App Launcher → Gaming Network → Launch shows `Discord Activity connected` (not browser preview).
- [ ] Second trusted account role / invite / visibility checks.

## SHA / evidence
- Intended base: `c92485ce84ae17394797d31075ef434abeab21f2` (`fix/discord-dashboard-response`)
- This docs commit: see branch head after push.
- No Railway deploy, no token change, no paid X, no production bot restart from this branch.
- Deployment left to ChatGPT / owner after in-person acceptance.

## Open PRs snapshot (Batch 1 verification)
Many open draft PRs exist; none auto-merged. Key Discord-related:
- #20 Fix Discord dashboard interaction stalls (base deploy/discord-bot)
- #33 already merged historically for /hubview
- #32 fingerprint rate-limit mitigation already merged
- #1 original Discord Hub bot

Main default branch is sparse (static index + activity-sdk). Live bot lives on `fix/discord-dashboard-response` / Railway pin.

**Do not merge this branch until the two-line rename is applied to a clean bot.py and CI/Python compile passes.**
