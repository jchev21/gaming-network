# Public live-lobby feed API

**Branch:** `grok/public-lobby-feed`  
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
      "waitlist": [],
      "confirmedCount": 2,
      "host": { "mode": "Reload", "region": "na-east", "crossplay": "on", "islandCode": "" },
      "entries": [
        { "name": "@alice", "selected": null, "seat": null }
      ]
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

Display names in `entries` / `waitlist` are the public names players chose when joining.

### Caching / CORS

- `Cache-Control: public, max-age=5, stale-while-revalidate=15`
- `Access-Control-Allow-Origin: *` (GET only; no credentials)
- In-process rate limit (~60 req/min per client key)

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
