# X Game Intake — isolated prototype

**Status:** Browser-only prototype. No X API credentials, X account authorization, Discord bot changes, or Railway deployment. Do not treat the demo as a live lobby.

## Temporary account handle
`@jordan__chev` — provisional and unverified. In a production integration, resolve the account's immutable X numeric user ID after authorized sign-in. Changing the handle should be a config change only.

## Proposed user experience
1. A player intentionally mentions the authorized X account in a post requesting a game.
2. The X app receives the mention through the official X API (e.g. `GET /2/users/:id/mentions` with a saved `since_id`), and validates/deduplicates each post.
3. If an opt-in request qualifies, the app sends **one** reply with a short-lived, signed setup URL. X doesn't provide arbitrary interactive mini-app popups in posts.
4. A verified user visits the linked web page to select game, platform, private code (optional), entry policy, and lobby capacity.
5. Participants join the web lobby. First-come confirms in order; timed lottery collects entries for five minutes and chooses up to five unique entrants. A server, not a browser timer, decides draws and enforces membership.
6. The backend creates/updates the authoritative game in the Gaming Network API; Discord receives a notification through a separate authenticated integration.

## Important security and product requirements
- Never publish private promo codes on X, in GitHub, or in URLs. Only accept codes for games or promotions you control or have permission to distribute. Release them to eligible players through an access-controlled server endpoint.
- Verify each X user server-side (OAuth 2.0 user context or another supported verification flow), and sign/expire mention links. Never trust just a submitted @username.
- Use official X APIs only. Observe API quotas, costs, no-spam rules, recipient opt-in, one automated response per interaction, and opt-outs.
- Require developer-app access and suitable `tweet.read`, `users.read`, `tweet.write` user permission scopes for posting replies, subject to X's current rules.
- Avoid collecting unnecessary user data. Persist server data on a durable volume/DB, add retries and idempotency keys, rate limiting and abuse controls, and audit logs.
- No automatic X replies or polling should be enabled until ownership, access and API billing are confirmed.
- The Discord bot and current Railway API services must remain untouched. Create a new isolated service after authorization.

## Preview locally
Open `demo.html` in a browser. This demo has a real local interactive form, demo-only player signup, local five-minute countdown and a manual **Test draw now** option. It makes **no** network calls, stores **no** redemption codes and does **not** create real games. State is intentionally ephemeral and resets on refresh.

## Remaining work
See the project issue: https://github.com/jchev21/gaming-network/issues/2

## Phase 2 — read-only mention listener (prepared, not deployed)

This branch now includes `listener.mjs`, `listener.test.mjs`, `package.json` and a Dockerfile. A separate Railway service named `x-game-intake` is **STAGED** in the existing Gaming Network project. It has NOT been deployed and is not polling X. The current Discord bot and website remain untouched.

**Credentials must be configured directly inside the X service's Railway Variables, not committed or sent through chat:**

- `X_API_BEARER_TOKEN`: your approved X Developer App's bearer token (read API); never a Discord token
- `X_HANDLE`: `jordan__chev` (already staged)
- `X_USER_ID`: optional; if blank, the listener resolves it from X's user lookup API on the first authorized poll
- `X_ADMIN_TOKEN`: a long random private admin token before enabling administrative endpoints
- `X_POLL_ENABLED`: `false` by default — **no automatic API requests**
- `X_POLL_SECONDS`: `120` when deliberately enabled; costs and quotas apply
- `DATA_DIR`: `/data`, backed by the staged `x-intake-data` Railway volume

When explicitly deployed, the service exposes `GET /health` for Railway health checks. It exposes `GET /admin/mentions` and `POST /admin/poll` only behind `Authorization: Bearer X_ADMIN_TOKEN`, and no public domain should be assigned. The first poll establishes a starting ID and **does not act on historical mentions**. Subsequent polls store only matching, deduplicated game requests marked `awaiting_review`. It does NOT post to X, issue codes, create games, or call the Discord API.

For the actual mention-to-lobby workflow, add owner account OAuth user authorization, a signed one-use setup link, an authenticated public website, API-backed player identity/lobby state, retry/anti-spam safeguards, and an opt-in confirmation step before posting a reply. Follow X API rate limits and pay-per-use billing before enabling scheduled polling.

Code sanity check: `node listener.test.mjs`. Docker builds run the same test automatically. Do not expose the admin endpoint or use a predictable admin token.

## Preview pages
Once a Railway service domain is assigned, browse `/setup` for the **demo-only** game picker/lobby and `/high-scores` for the original Comet Hop and Neon Targets arcade. The arcade stores scores in the browser; these are not shared, tamper-proof, or prize eligible. These routes need no X API access or credentials. **Do not send or accept real redeemable promo codes through these demos.**

## X-verified game lobbies (isolated implementation)

This next phase is prepared on branch `feature/x-verified-lobbies`. It adds `game-core.mjs`, `lobby-api.mjs`, `x-auth.mjs`, and unit tests; it does **not** change the production Discord bot or the existing Gaming Network API.

### X Developer Console: required user authentication settings
- Enable **User authentication settings** for a Web App / confidential client and OAuth 2.0 authorization code with PKCE.
- Callback URL: `https://x-game-intake-production.up.railway.app/auth/x/callback` (must match EXACTLY in X console and Railway).
- Website URL: `https://x-game-intake-production.up.railway.app`.
- Request only `tweet.read` and `users.read` for player sign-in. No `tweet.write`, no reply automation, and no access to protected APIs.
- Configure these variables **privately under the Railway x-game-intake service, never in GitHub**:
  - `X_CLIENT_ID`: your X OAuth 2.0 Client ID
  - `X_CLIENT_SECRET`: X OAuth Client Secret if provided for your confidential app
  - `X_CALLBACK_URL`: `https://x-game-intake-production.up.railway.app/auth/x/callback`
  - `X_PUBLIC_ORIGIN`: `https://x-game-intake-production.up.railway.app`
  - `X_ADMIN_TOKEN`: a separate randomly generated 32-byte+ secret for moderator actions
  - Keep `X_POLL_ENABLED=false` until you intentionally run a bounded mention test
- A bearer token alone cannot verify the identity of visitors or authorize posts as the account.

### Flow after credentials and a fresh mention
1. A qualifying new mention of `@jordan__chev` is saved by the read-only listener, with the immutable X author ID and post ID. There are **no automatic X replies**.
2. A trusted moderator explicitly approves that post through `POST /admin/invites`, using the private `X_ADMIN_TOKEN` bearer authorization. Body: `{"post_id":"POST_ID"}`.
3. The server creates a one-time, 24-hour setup URL tied to the **author's X user ID**, not their display name. Only the moderator receives the returned URL; it is **not posted** anywhere automatically.
4. After the original author signs in to X via PKCE, the setup page creates a persistent server-side lobby and consumes the invitation. Any other X account is rejected.
5. Participants sign in to X and may join a lobby **once per X user ID**. First-come seating closes when full; five-minute random entry closes after five minutes and is drawn using server-side cryptographic randomness.
6. The public `GET /api/lobbies/:id` returns only safe game status and display names, never raw X account IDs or any private promo/redeem code.

### Not completed
- This is not yet connected to sending replies on X, the old Poker Now challenge API, or Discord notifications.
- No X Client ID/Client Secret has been provided to Railway, so verified login is **not yet enabled**.
- A real host must supply/authorize any externally hosted poker table. This app does not book Poker Now seats automatically.
- No verified arcade scoring, prizes, payouts, or real redemption; never trust a browser's score as proof.
- Multiple live replicas must not concurrently edit the JSON state volume; this phase expects **one** Railway replica. Move to transactional database before horizontal scaling.
- Backups, moderation UI, privacy policy and rate/abuse controls need additional hardening before public launch.

### Tests
Run `node listener.test.mjs && node game-core.test.mjs && node x-auth.test.mjs && node lobby-api.test.mjs`. The Dockerfile runs all four test suites during build.

### Multi-title Host a Game options (signup only)
The X game picker now offers Fortnite, Call of Duty: Warzone, Apex Legends, Rocket League, Minecraft, Roblox, Valorant and Other Multiplayer Game. These titles are supported as **Gaming Network signup lobby categories**, not as direct integrations with the games' matchmaking systems. The backend validates their enumerated IDs. The host still creates each external game session and privately shares its join details with eligible participants, subject to the game's rules. No Epic/Activision tokens, in-game lobby automation, or new score verification are enabled.


### Multiplayer hosting batch — private instructions
On the isolated `feature/x-host-workflow` branch, the X game picker lets a host choose mode, region, crossplay and a public Fortnite island identifier. The real server validates all public settings before accepting an X-authenticated invitation. Private game joining instructions are sent only through `POST /api/lobbies/:id/join-details` by the verified host and delivered via `GET /api/lobbies/:id/join-details` to that host or a selected player after the lobby is ready. Instructions are encrypted at rest with AES-256-GCM and the secret key from `X_JOIN_SECRET_KEY` or the existing high-entropy `X_ADMIN_TOKEN`. Public lobby responses never include private instructions or X user IDs. Actual Fortnite/Warzone game creation remains manual; this is only Gaming Network signup management.


### Cancellation and withdrawal UX (not deployed yet)
The browser lobby now exposes X-authenticated host cancellation and entrant withdrawal controls, and uses server-side viewer state to avoid duplicate submissions. Cancelled lobbies show a warning and hide join details; updates to encrypted joining instructions are rejected after cancellation. Withdrawals are one-way before selection closes; public lobby data does not expose internal X IDs. Changes are isolated to `feature/x-host-workflow` beyond the pinned deployed release.


### My Games — private signed-in dashboard (development branch)
`GET /api/my-games` requires an X-authenticated session and returns only lobbies the current immutable X user owns, entered, or withdrew from; it caps output at 50 games and excludes private matchmaking instructions and user IDs. The `/my-games` page links to the user's games and uses `/auth/x/start?next=/my-games` for sign-in when configured. The page and API are on the isolated branch; there is no automatic X posting, scanning, or live provider integration.


### FIFO waitlist and host no-show replacement (unreleased)
Full first-come lobbies can accept up to 100 additional authenticated players on a public-name-only waitlist. The server maintains immutable X account IDs privately, blocks duplicate/withdrawn/removed entries, and lets the host replace a selected no-show with the earliest standby player. If no standby player exists, the seat reopens for five minutes. Standby players may withdraw without losing any seats. Random-draw lobbies are intentionally excluded until a properly randomized standby order is implemented. This feature is not connected to external game matchmaking or X posting. It is only in `feature/x-host-workflow`; Railway's pinned release remains unchanged.


### Imported security hardening (isolated host branch)
Reviewed and manually ported from Claude draft PR #8: bounded OAuth pending flows (maximum 2,000; HTTP 429), constant-time hashed admin authorization, and mutation-aware persistence for public lobby and private join-details reads. These changes do not enable X polling, replies, or any production deployment. The JSON store is still single-replica; Grok is drafting a transactional storage migration in issue #10. Dedicated instruction-key rotation remains a separate planned security change.
