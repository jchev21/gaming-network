# Friends & Family Night-Zero — Limited Onboarding Preflight

**Owner-only preview scope. This is not complete public launch approval.**
- Only invite trusted family/friends into a controlled Discord community with a short-lived invite, after the owner verifies rules, permissions and two-account view.
- The public website is a showcase with marked sample/demo areas. Website `/welcome` is a **local demo**, not Discord membership. The `/discord` Studio shows **sample data**, not private messages. `/live-games` is the separately hosted real X gateway and public read-only lobby listing.
- **No prizes, payments, real redemption codes, automated X mentions/polling, private cross-channel feeds or automatic third-party game joining.**
- If X A/B acceptance is not complete, label X game hosting *coming soon / supervised test only*. Do not tell members an X mention triggers a real game.

## Verified (November 5, 2026)
- Railway production status: all 4 services online, each 1/1 healthy, no active warnings or failed deployments in the preceding 24 hours; 3 persistent `/data` volumes remain mounted; no staged changes.
- Deployed frontend build CI: [GitHub Actions 42019637021](https://github.com/jchev21/gaming-network-hub/actions/runs/42019637021) PASS on production web commit `b9af7e2673`.
- External **read-only** live HTTPS smoke: [16/16 checks PASS, Actions 42146755546](https://github.com/jchev21/gaming-network/actions/runs/42146755546). Verified:
  * `/`, `/welcome`, `/games`, `/live-games`, `/discord`, `/activity`, `/high-scores` return HTTP 200 and app SSR content;
  * `/api/x-status` returns structured readiness, public lobby gateway responds with safe status;
  * X `/health` confirms running with auto-poll **OFF**; anonymous `/api/me` is unauthenticated;
  * X public lobbies are read-only and omit known private fields; admin `/admin/mentions` and `/api/my-games` both reject anonymous requests with HTTP 401;
  * invalid OAuth callback returns HTTP 400; OAuth start returns HTTP 302 to X's allowed login domain with secure, HttpOnly, SameSite state cookie.
- Discord bot's runtime gateway recorded a successful session resume; the bot has prior live slash command sync evidence. **This does not prove Discord interactions work in a real client.**
- Known issue: earlier Discord dashboard message PATCH requests saw repeated HTTP 429 warnings; newest available log subset had no further 429 after 2026-11-06 00:01 UTC, but human interaction and ongoing cooldown checks still needed.

## Owner's 10-minute in-person Discord signoff tonight
1. In the actual private/test Discord channel, run `/hubview` as an admin. Verify menu **above** content, This Channel only, X feed, Calendar, and Refresh. Take screenshots; if error/429, mark FAIL.
2. Run `/dashboard`. Verify Calendar, Leaderboard, Rewards, and **Add Event** modal using a moderator/Manage Messages account. Don't repeat-refresh rapidly.
3. Discord App Launcher -> Gaming Network -> Launch. Check banner says **Discord Activity connected**. Verify source selector above stage, Studio preserved, private panel **authorization required**. Browser preview is not enough.
4. Invite a second trusted account with member (non-admin) role. Verify rules, welcome channels, view/send permissions, access to dashboard, and **no access** to private channels/codes/moderator-only actions.
5. Verify any limited Discord invite was **created inside Discord by owner**, not guessed or posted publicly. A real moderator must confirm who can send invite links.
6. Save PASS/FAIL and screenshot names under [launch #17](https://github.com/jchev21/gaming-network/issues/17) or use the offline [20-check console](https://github.com/jchev21/gaming-network/actions/runs/42146060297).

## Optional supervised X signoff (NOT part of a Discord-only preview)
- Account A completes real OAuth callback from `https://x-game-intake-production.up.railway.app/auth/x/start?next=%2Fmy-games`, is invited/approved, creates a test FCFS lobby.
- Account B logs into a **different** X account; joins, tries duplicate/waitlist/cancellation; private join instructions visible only to authorized participants.
- Test a 5-minute lottery **after its actual close**, no early/second draw; account C/wrong-account gets no private instructions. Stop if X API billing or provider permissions become blockers.
- Avoid enabling `X_POLL_ENABLED`, paid X mention reads or automated X posting.

## Release gate and recovery
- A launch to trusted friends/family is a **narrow Discord community preview**, not global X matchmaking launch. No production PR merges are required for basic invitation; keep deployed hashes pinned tonight unless a tested, explicitly owner-approved urgent fix is necessary.
- If a user reports bot failure, stop testing, capture command/time/error; see [launch #17](https://github.com/jchev21/gaming-network/issues/17) for rollback hashes. Do not unmount or erase the live `/data` volumes.
- All unsatisfied in-person tests stay **unchecked**. Owner signoff is never inferred from CI, uptime, screenshots alone or an imported JSON document.
