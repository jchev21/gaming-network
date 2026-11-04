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
