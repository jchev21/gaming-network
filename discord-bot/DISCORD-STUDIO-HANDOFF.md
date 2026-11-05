# Discord Broadcast Studio — safe groundwork for Grok issue #22

This review-only continuation starts from the unmodified Grok branch `grok/discord-hub-launch-overhaul` (which currently matches `fix/discord-dashboard-response`). It does **not** deploy or change the existing bot, guild, local dashboard port or persistent data.

## Implemented here
- `discord-bot/dashboard-studio-model.mjs` — pure JS model for per-server mock broadcast themes and independent 1/2/4/8 channel panes.
- Demo server presets for Esports, Trading Desk, Academy, Rewards, Partner League and Community.
- Non-sensitive JSON import/export; unrecognized keys, message history, tokens and invalid theme values are discarded.
- `discord-bot/dashboard-studio-model.test.mjs` — regression tests covering per-server independence, pane choice, 1/2/4/8 counts and safe serialization.
- CI workflow runs the pure model tests separately from existing Python bot compile/interaction regression checks.

## Not yet implemented (for other UI AI, or a later follow-up)
The visual browser page, server-brand preview, mobile layouts and a screenshot-ready 1/2/4/8 pane UI. For that, use the *separate* `jchev21/gaming-network-hub` frontend `src/routes/command-center.tsx` and `src/routes/discord.tsx`, plus the pure model here as a reference. **Do not expose the loopback-only Python bot's private `/api/chat` or `/api/send` over the public internet.** Use demo data until a permission-scoped OAuth/Activity integration exists.

## Rules
Do not touch Railway or bot tokens. Do not reset `/data`. Do not merge without owner approval. This branch is not production-ready.
