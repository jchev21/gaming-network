# Gaming Network — native verified X host moderation

**Scope:** an owner-only, read-only queue and a controlled host-invitation action. UI runs at `https://x-game-intake-production.up.railway.app/moderation`. It is a browser page for administrating X-hosted games; the separate Discord slash commands `/hubview` and `/dashboard` are unchanged.

## Configure owner identity once
1. Sign into the X game service through `/my-games` with the **actual owner/moderator X account**.
2. Check your signed-in account ID from the existing read-only `/api/me` endpoint. Do not paste OAuth session cookies or admin bearer tokens into chat.
3. In Railway, set `X_MODERATOR_USER_ID` to that **verified numeric X account ID** on the existing `x-game-intake` service. An explicit match is required; the configured `X_HANDLE` is **not** used to automatically grant moderator authority.
4. Visit `/moderation`. You must have a valid X sign-in session for exactly that account. All other sessions receive 403 on moderation APIs.
5. Confirm users receive the correct server rules, X sign-in and moderator account permissions.

## Game approval workflow
1. The X mentions listener must have **completed** a real read and recognized an eligible mention. It never posts to X by itself.
2. Open `/moderation`, click Refresh requests. A pending post shows its public excerpt and link. Only the owner sees these via the authenticated moderation API.
3. Click Approve request. The server creates a 24-hour, single-use invitation bound to the **original mention author's X ID**, never to the approving moderator.
4. Click Copy invitation link and **privately deliver** it to that original X account. If the host signs in with a different X account, they cannot use it.
5. The host creates the real persistent signup lobby and sends its **public** lobby URL to players. Players sign in with X and join first-come or five-minute lottery. Private joining instructions remain separate behind the authorization checks.
6. Confirm public lobbies never expose invitation tokens, X internal IDs, host's secret instructions or redemption codes.

## Safety rules
- `/moderation` HTML itself is public, but its queue and approval **API** enforce a configured numeric moderator X ID; a generic player receives 403. No privilege fallback to handle ownership.
- Same-origin POST is enforced by the server to prevent cross-site approval.
- Invitation URLs are confidential bearer capabilities; do not put them in public channels or copy logs.
- No automatic X messages, retweets, paid API polling, credential writes, Discord bot changes, prize payments or third-party multiplayer creation.
- For real live X mentions pagination and request limits, see [issue #54](https://github.com/jchev21/gaming-network/issues/54); the service's paid polling remains disabled until bounded operator approval.

## Validation
Run `npm test` from `x-integration` or the GitHub Actions X Host Workflow Tests. `moderation.test.mjs` uses synthetic X accounts, fake X sign-in and a loopback HTTP server; these are **offline tests, not successful real X login or real-user game acceptance**.

Rollback: restore the last known healthy Railway X service commit; preserve the `/data` volume and existing secrets. Remove `X_MODERATOR_USER_ID` or disable its value to revoke moderator access.
