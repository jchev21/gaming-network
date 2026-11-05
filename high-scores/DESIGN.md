# Authenticated leaderboard design (draft)

**Status:** design + validation core only. Nothing here is wired to the live site, X, Discord, or Railway.
**Prize policy:** browser scores are client-reported and are **never prize-grade**. Every accepted entry is `tier: "unverified"`, `prizeEligible: false`.

## Flow
1. Player signs in (verified X id from the x-integration OAuth — read-only scopes).
2. `POST /api/arcade/start {game,duration}` → server returns an HMAC-signed run token binding player, game, duration, start time, random nonce.
3. Round plays in the browser.
4. `POST /api/arcade/submit {token,score}` → `validateSubmission`:
   - signature valid (constant-time), token belongs to the authenticated player
   - not expired (duration + 15 min), nonce unused (replay → 409)
   - integer score ≥ 0 and ≤ per-game ceiling × real elapsed time (server clock, not client)
   - ≤ 30 submissions/player/hour; best 5 entries kept per player per board
5. `GET /api/arcade/top?game&duration` → ranked names + scores only (no ids/nonces); names stripped of control chars and `<>`.

## What this stops / doesn't stop
Stops: forged or edited scores beyond the physical ceiling, replayed submissions, stolen tokens, instant-submit, spam, anonymous submissions, XSS via names.
Does **not** stop: a cheater submitting a plausible-but-fake score, or a bot playing well. Hence no prizes.

## Path to prize-grade scoring (future, needs approval)
- Server-side deterministic simulation from a seeded run + recorded input log (replay and re-score), or signed per-event telemetry checked for human-possible timing.
- Seed issued by the server at `start`; reject runs whose replay differs.
- Manual review queue for top-N before any payout; legal/rules review per game.

## Tunables
`GAME_RULES.maxPerSecond` are conservative ceilings derived from `index.html` scoring (runner: 16/s + 85/obstacle, ≤2 obstacles/s; targets: ≤309/hit, ≤5 hits/s). Re-derive if game rules change.

## Config
`ARCADE_SIGNING_SECRET` (≥32 random chars) from env only; never committed. Storage: swap the `persist` callback / `state` for a DB table.

## Known gaps
No HTTP routes, persistence, or front-end changes yet (kept isolated so the page remains a static demo); runner minimum-play-time for non-crash finishes is not enforced; in-memory rate limits reset on restart.
