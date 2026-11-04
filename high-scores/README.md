# Gaming Network — High Scores Arcade

Standalone browser prototype with two original mini-games:

1. **Comet Hop** — jump over obstacles, earn points for distance and obstacles passed, and avoid collisions.
2. **Neon Targets** — tap targets, earn combo bonuses, and chase a high score.

Both games have selectable 30-second, 1-minute, 2-minute, and 5-minute maximum run durations, responsive canvas controls, and per-game/per-duration local high-score tables. A missed Comet Hop jump ends a round early. Tab switching automatically pauses a round.

## Run

Open `index.html` in a modern browser. No server, credentials, account, or network required. Tests can be performed with a headless browser.

## Important limitations

- High scores use this browser's `localStorage` only. They are **not** cross-device leaderboards and cannot be trusted for prizes, monetary awards, gift codes, or competitive standings.
- The score currently comes from client-side JavaScript, which players could modify. To run public contests, we must build server-authoritative challenge sessions, anti-cheat validation, session tokens, server-side time windows, immutable score submissions, and tamper-resistant game logic.
- This prototype is intentionally isolated from the live Discord Hub, the Gaming Network API, and X account. No production service is modified or deployed.
- `index.html` uses original CSS and canvas shapes; no Google Chrome Dino assets.

## Next integration

Add a separate `High Scores` navigation category to Gaming Network's website; serve this at `/high-scores/`; implement authenticated users and a validated backend leaderboard. Eventually allow approved X-triggered lobbies to select the game and time limit, then join via signed invitation links.

Tracked in https://github.com/jchev21/gaming-network/issues/2