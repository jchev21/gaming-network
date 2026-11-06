# Batch 3 — PR #68 review notes (no auth changes)

**PR:** [#68](https://github.com/jchev21/gaming-network/pull/68) — DRAFT: Discord Member-only authorization for X game hosting and joins  
**Head:** `feature/discord-member-game-gate-1106` @ `b4d9f32bbfb1fb8caf07366d4ae7859624b192ea`  
**This branch:** `grok/two-account-acceptance-1106` adds offline acceptance only.

## Authorization contract (unchanged)

| Rule | PR #68 behavior | Batch 3 action |
|------|-----------------|----------------|
| X sign-in = identity only | Required session cookie + user id | Verified offline |
| Discord Member role = permission | `guilds.members.read` + exact role ID; `pending=false` | Verified offline |
| Gate flag | `GN_DISCORD_MEMBER_GATE_ENABLED` default **off** | Not enabled |
| No bot token / role grants | Documented in module header | Not altered |
| Fail closed | Missing role, pending rules, bad OAuth state | Covered by suite |
| Public listings | Readable without Member | Covered |
| Private join details | Require current Member | Covered |

**No modification** was made to `discord-member-auth.mjs`, lobby gate wiring, or OAuth scope list.

## Official handle

Owner mission handle: **`@xyzhub`**.  
PR body notes X restrictions on dotted forms (`@xyz.hub`); acceptance suite asserts storage form `xyzhub` / display `@xyzhub`. Production `X_HANDLE` must not be changed until owner confirms the live account.

## Suite file

`x-integration/two-account-acceptance.test.mjs`

Covers:
1. Host X sign-in before Discord OAuth  
2. Host Discord Member authorization  
3. Authorized game creation (HTTP Member gate)  
4. Second account Member join  
5. First-come fill + five-minute lottery finalize  
6. Wrong-account / revoked role privacy (no X ids, no secrets on public; join-details 403)  
7. `@xyzhub` handle fixture  
8. Missing Member role fails closed  

Run (from `x-integration` on this branch):

```bash
node two-account-acceptance.test.mjs
```

## Explicit non-actions

- No paid X polling  
- No production cursor / `since_id` migration  
- No posts on X  
- No merge or deploy of PR #68  
- No live Discord API calls in the suite (mocked `fetchImpl`)
