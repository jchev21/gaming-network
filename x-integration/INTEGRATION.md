# Integration notes

- Work from the user's selected `ai/games-x` branch in `jchev21/gaming-network`; do not move these files to the Education Center repository or to `main`.
- Keep existing `game-core.mjs` and `lobby-api.mjs` authoritative. The additive `bridge-contracts.mjs` module is an interface seam only and is not wired into request handling.
- Before exposing live lobby discovery, coordinate with draft PR #16 (`grok/public-lobby-feed`) rather than adding a second `GET /api/lobbies` route.
- Before persisting or delivering lifecycle announcements, coordinate with draft PR #21 (`grok/x-discord-announcements`). The added event builder is allowlisted and does not enqueue or post.
- Before claiming race-safety beyond one process, coordinate with draft PR #12 (`grok/lobby-storage`). The current JSON queue is not multi-process safe.
- Keep the X adapter disabled unless an explicitly reviewed deployment injects official API capabilities, verifies authors on the server, configures official OAuth and policy-compliant access, and separately approves any reply workflow. The adapter contains no HTTP transport.
- Join instructions remain private and encrypted using the existing dedicated key; do not expose them in feed or event payloads.
- The safe frontend API mapping and route availability are documented in `API_CONTRACT.md`; use fixtures only for UI development.
- No branch merge, deployment, paid API polling, Discord posting, or credential setup is part of this change.
