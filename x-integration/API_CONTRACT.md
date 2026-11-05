# Games + X API contract for the website

This contract describes the existing `x-integration/lobby-api.mjs` endpoints on the selected branch. This backend currently uses X OAuth session cookies and a JSON file with a per-process serial queue. It is a preview API contract, not a claim of multi-instance transactional behavior.

## Common behavior

- JSON responses use `Cache-Control: no-store`; errors are `{ "error": "CODE", "message": "Human-readable explanation" }` except unauthenticated/forbidden moderator responses, which currently use a message-only object. Clients should safely handle both forms.
- Mutating browser requests require the exact configured `Origin` (`X_PUBLIC_ORIGIN`), authenticated X session where specified, `Content-Type: application/json`, and same-site session cookies. The application must keep credentials server-side; do not send X IDs, usernames, invite ownership, or roles in request bodies.
- Request bodies are capped at 8 KiB. Per-user rate limits return HTTP 429 with `RATE_LIMIT`.
- A valid X OAuth session is server-side identity authority. Browser-submitted display identity is not trusted.
- Public lobby data excludes account IDs, invite tokens, and private joining instructions. `entries[].name` may contain user-chosen display text and should be treated as unverified, user-generated content.

## Routes currently present

### Lobby list / discovery

`GET /api/lobbies` is **not present on this branch**. Draft PR #16 proposes a public, unauthenticated paginated feed with `game`, `platform`, `status`, `limit`, and `cursor`; coordinate its exact schema and sanitized `publicLobby()` source before using it. Until that is integrated, the frontend must use its sample provider or an explicitly approved alternate feed.

### Lobby detail

`GET /api/lobbies/{lobbyId}` — no login required.

200:
```json
{
  "game": {
    "id": "preview-lobby-1",
    "title": "SAMPLE Squad Night",
    "game": "fortnite",
    "host": { "mode": "Duos", "region": "na-east", "crossplay": "on", "islandCode": "" },
    "platform": "pc",
    "mode": "first",
    "seats": 4,
    "roundSeconds": 60,
    "status": "open",
    "entryClosesAt": 1793837100000,
    "entryCount": 1,
    "waitlistCount": 0,
    "waitlist": [],
    "confirmedCount": 1,
    "entries": [{ "name": "SAMPLE player", "selected": null, "seat": null }]
  }
}
```

404 for an unknown lobby. Status is finalized against the server clock while reading; do not infer openness solely from a cached browser timer.

### Create

`POST /api/lobbies` — verified X session + exact Origin + valid single-use setup invite.

Example request (synthetic):
```json
{
  "inviteToken": "REDACTED_SYNTHETIC_43_CHAR_TOKEN",
  "game": "fortnite",
  "platform": "pc",
  "mode": "first",
  "seats": 4,
  "roundSeconds": 60,
  "title": "SAMPLE Squad Night",
  "host": { "mode": "Duos", "region": "na-east", "crossplay": "on", "islandCode": "" }
}
```

201: `{ "game": <public-lobby>, "lobbyUrl": "https://example.test/lobby?id=..." }`. Invite must belong to the authenticated user and can be consumed only once. The request's token above is deliberately invalid and must not be sent to a running service.

### Join, waitlist, withdraw

- `POST /api/lobbies/{id}/join` — signed-in user; body ignored/empty. Identity and display name come from authenticated server profile. 200 `{ "game": <public-lobby> }`.
- `POST /api/lobbies/{id}/waitlist` — signed-in user; first-come lobby must be full and ready. 200 `{ "game": <public-lobby> }`.
- `POST /api/lobbies/{id}/withdraw` — signed-in user; 200 `{ "game": <public-lobby> }` when allowed.
- Duplicate, closed, withdrawn, waitlisted, or removed actions return 409 with a stable error code when implemented by the domain layer.

### Viewer-scoped `me` and My Games

- `GET /api/lobbies/{id}/me` — signed-in user. 200 fields: `isHost`, `joined`, `selected`, `waitlistPosition`, `withdrawn`, `removed`, `canCancel`, `canReplace`, `canWaitlist`, `canWithdraw`. These flags are hints only; the server rechecks authorization on mutation.
- `GET /api/my-games` — signed-in user. 200 `{ "games": [<public-lobby plus viewerRole and viewerSelected>] }`. Results are capped at 50 and only include games involving the viewer. `viewerRole` is one of `host`, `player`, `waitlisted`, `withdrawn`, `removed`.

### Host cancel / no-show replacement

- `POST /api/lobbies/{id}/cancel` — host only, exact Origin. 200 `{ "game": <public-lobby> }`; private instructions are deleted and selected-player access is revoked.
- `POST /api/lobbies/{id}/replace` — host only, exact Origin; request `{ "seat": 0 }` where seat is a selected seat index. Promotes the FIFO waitlist head or reopens the lobby for a new signup window.

### Protected joining instructions

`/api/lobbies/{id}/join-details`:
- `GET` — host or currently selected player. 200 `{ "role": "host"|"selected", "ready": true, "instructions": "..." }`. Other users receive 403. A removed/no-longer-selected participant loses access.
- `POST` — host only, exact Origin, body `{ "instructions": "5–700 characters" }`. Stored encrypted with the dedicated `X_JOIN_SECRET_KEY`; never include this response in public lobby lists or lifecycle announcements.

### Mention approval / invite issuance

- `GET /api/moderation/mentions` — configured moderator X session; returns up to 100 recognized requests with excerpt and status.
- `POST /api/moderation/approve` — configured moderator X session + exact Origin; request `{ "post_id": "synthetic-numeric-id" }`; returns 201 `{ "setupUrl": "...", "expiresAt": 0 }`.
- `POST /admin/invites` is a server-admin Bearer route and must never be called from the website browser.

## Error and privacy handling

Typical statuses: 400 invalid input, 401 missing session, 403 forbidden origin/identity/role/invite, 404 missing lobby/mention, 409 invalid transition/duplicate, 413 body too large, 429 rate limit, 503 unavailable configuration/storage. Never log full request bodies from join-details, OAuth cookies, invite tokens, or authorization headers. Do not cache viewer-scoped endpoints or private instructions.

## Status semantics

`open`: accepting entries until the server-controlled close time; first-come may become ready as soon as seats fill. `ready`: selection has completed; first-come winners are seated and lottery winners are selected. `closed`: signup expired without a ready first-come lobby or without lottery winners. `cancelled`: host cancelled; no confirmed seats or private selected-player access.
