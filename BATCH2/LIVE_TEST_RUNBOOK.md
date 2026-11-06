# Batch 2 — Live-test runbook: host/player authorization + public feed privacy

**Refs:** #17 (launch gates) · #2 (master) · PUBLIC-FEED.md · MODERATION.md  
**Status:** Offline / operator checklist only. Does not enable paid X polling.  
**Owner action required** for every PASS/FAIL that touches real X or Discord accounts.

## Preconditions (must be true before any live step)
- [ ] X polling remains `X_POLL_ENABLED=false` (or absent).
- [ ] `X_MODERATOR_USER_ID` set to the numeric X ID of the owner/moderator account only.
- [ ] Four Railway services online; no staged unpaid billing surprises.
- [ ] Operator has two distinct X accounts (A = host candidate, B = player) and one Discord Manage-Server identity.
- [ ] Browser session cookies isolated (separate profiles or private windows).

## 1. Public feed privacy (no auth)
1. Unauthenticated GET `https://x-game-intake-production.up.railway.app/api/lobbies` (or current public origin).
2. Confirm response shape matches PUBLIC-FEED.md (`source`, `games[]` with only id/title/game/platform/mode/seats/roundSeconds/status/entryClosesAt/entryCount/confirmedCount/waitlistCount).
3. Confirm **never** present: `ownerXId`, any player `xId`, invite tokens, join instructions, ciphertext, session/admin tokens, internal paths.
4. GET `/api/lobbies/:id` for a known open lobby — same sanitized public object; no secrets.
5. Wrong/unknown id → clean 404/400, no stack traces or data leakage.
6. Record: PASS / FAIL + response sample (redact if any accidental PII).

## 2. Host authorization path (Account A)
1. Account A: open `/auth/x/start?next=%2Fmy-games` and complete real OAuth callback (not just the 302 start).
2. Confirm session persists on `/my-games` and `/api/me` returns the expected X user.
3. Without moderator approval: A must **not** be able to create a production lobby that appears on the public feed as authorized host flow (or document current gate behavior exactly).
4. Moderator (configured `X_MODERATOR_USER_ID`): open `/moderation`, refresh requests, Approve a pending eligible mention (or use the documented invitation flow if no live mention is present).
5. Invitation link is single-use, 24h, bound to **original mention author X ID** (not the moderator). Deliver privately to A.
6. A redeems invitation with the **same** X identity, creates lobby (game, platform, seats, FCFS or lottery).
7. Confirm public listing appears with sanitized fields only; private join instructions never in public JSON.

## 3. Player authorization path (Account B)
1. Account B signs in with a different X identity.
2. B joins A's lobby via the public lobby URL / join flow.
3. Confirm: seats / waitlist / duplicate prevention behave as designed.
4. B can view **only B's** authorized join details; A (host) can view host-side instructions; unauthenticated and wrong-account requests receive 401/403 and never see codes.
5. Cancel / leave / waitlist replacement paths leave public counts consistent and secrets unexposed.

## 4. Lottery privacy (if testing five-minute mode)
1. Create lottery lobby with ≥2 valid entries before close.
2. After configured close: exactly one selection; no early selection.
3. Winner receives authorized instructions; non-winners do not.
4. Public payload remains count-only; no identity leakage.

## 5. Negative / threat cases
- Unauthenticated visitor to join-details or moderation APIs → 401/403.
- Wrong-account session to another player's join-details → 403.
- Moderator endpoints with non-moderator session → 403.
- Replay of a spent invitation → rejected.
- Public feed never includes invite URLs or redemption codes.

## 6. Discord cross-check (same session window as #17)
- After a public lobby exists, `/hubview` → Public X games feed shows the sanitized listing (or documents current wiring gap honestly).
- No private codes appear in any Discord channel message.

## Recording template
```
Date/time (UTC):
Operator:
Account A X id (last 4): 
Account B X id (last 4):
Public feed GET: PASS/FAIL — notes
OAuth callback A: PASS/FAIL
Moderator approve + invite: PASS/FAIL
Lobby create + public sanitize: PASS/FAIL
B join + join-details isolation: PASS/FAIL
Lottery (if run): PASS/FAIL / SKIP
Negative authz: PASS/FAIL
Discord /hubview X feed: PASS/FAIL / N/A
Blockers:
SHA / service pins observed:
```

## Non-goals for this batch
- Paid X mention polling or automatic replies (#54).
- Frontend onboarding changes.
- Merging or deploying without owner sign-off on #17.
