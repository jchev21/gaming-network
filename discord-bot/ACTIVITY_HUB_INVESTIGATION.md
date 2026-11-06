# Batch I — Talk → Activity → Hub view-only

## Hypotheses
1. Persistent views need `bot.add_view` in setup_hook (present).
2. Guild command sync vs Activity entry-point (frontend).
3. View timeout leaves dead components until `/hubview` re-post.
4. Interaction 3s respond window.

## Verify
Re-post `/hubview`, check Railway logs, confirm Activity URL + bot permissions.
