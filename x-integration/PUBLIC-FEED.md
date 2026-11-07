# Public live-lobby feed API

**Source:** Grok PR #16 (`grok/public-lobby-feed`); selectively reused on `launch/public-lobby-feed-integration`  
**Issue:** #15  
**Status:** Draft API only — not deployed. Website should keep showing sample/demo data until integration is verified.

## Endpoint

```
GET /api/lobbies
```

Read-only. **No authentication.** Suitable for the Gaming Network website to list live games.

### Query parameters

| Param | Values | Notes |
|-------|--------|-------|
| `game` | see `GAME_TYPES` in `game-core.mjs` | optional filter |
| `platform` | `web`, `discord`, `pc`, `playstation`, `xbox`, `mobile` | optional |
| `status` | `open`, `ready`, `closed`, `cancelled` | optional |
| `limit` | 1–50 (default 20) | hard cap 50 |
| `cursor` | opaque string from prior `nextCursor` | newest-first pagination |

Invalid filters → **400** with `{ error, message }` (never 500).

### Response shape

```json
{
  "source": "live",
  "games": [
    {
      "id": "…",
      "title": "Friday Fortnite",
      "game": "fortnite",
      "platform": "pc",
      "mode": "first",
      "seats": 4,
      "roundSeconds": 60,
      "status": "open",
      "entryClosesAt": 1700000300000,
      "entryCount": 2,
      "waitlistCount": 0,
      "confirmedCount": 2
    }
  ],
  "count": 1,
  "limit": 20,
  "nextCursor": null
}
```

`source: "live"` means the backend is the real X intake store. Until this is deployed and verified, the website should continue labeling its cards as **sample/demo**.

### Privacy guarantees

Never returned:

- `ownerXId` or any player `xId`
- Invite tokens / hashes
- Join instructions or ciphertext
- Session cookies, admin tokens, OAuth state
- Internal database paths

The public **discovery index** intentionally excludes all player lists, public names, X identities, waitlist identities and host configuration. Only anonymous counts and game metadata appear. The individual `GET /api/lobbies/:id` endpoint has a separate viewer contract; keep private joining instructions behind authenticated authorization.

### Caching / CORS

- `Cache-Control: public, max-age=5, stale-while-revalidate=15`
- `Access-Control-Allow-Origin: *` (GET only; no credentials)
- An in-process aggregate safety ceiling of 6000 public feed requests/minute currently protects the origin. Railway's reverse proxy can make many real viewers share one socket IP; untrusted forwarded headers are deliberately ignored. For a larger rollout, configure trustworthy per-client edge rate limiting and caching before raising origin capacity.

### Related private routes (unchanged)

- `GET /api/lobbies/:id` — same sanitized `publicLobby` object
- `GET|POST /api/lobbies/:id/join-details` — **authenticated**, host/selected only
- `GET /api/my-games` — **authenticated**, viewer-scoped

### Frontend integration note (Lovable `gaming-network-hub`)

Do **not** edit the private UI repo from this branch. When wiring:

1. Point the live feed client at `GET /api/lobbies` only after staging verification.
2. Keep a `source` check: if not `"live"`, or if the request fails, fall back to demo cards.
3. Never request join-details from the public marketing site without X sign-in.

### Tests

```bash
cd x-integration
node public-feed.test.mjs
node lobby-api.test.mjs
```

## Launch integration note
This continuation is independent of Grok's original branch. The endpoint is not production/live until the separately pinned Railway X intake service has a manually approved verified deployment. Never replace private join-detail permissions with public feed permissions.
