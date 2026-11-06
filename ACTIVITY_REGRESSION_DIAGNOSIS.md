# Batch 1 — Discord Activity regression diagnosis (issue #67)

**Repo context**
- Backend / Activity static shell: `jchev21/gaming-network`
- React site / hub UI: `jchev21/gaming-network-hub`
- Issue: [#67](https://github.com/jchev21/gaming-network/issues/67) — Talk → Activity → Hub loads view-only
- Official X handle (separate from this batch): `@xyzhub`
- Constraint: no mutation of PR #71; no live Discord server edits; no paid X polling

**Referenced SHAs from issue #67**
- Frontend (hub): `76c37237e41f600125776067e81b252d4c628765` (PR #35 — launch shortcuts to Live Games)
- Bot: `4f4397dab18df198c116ac46695b5f3f2f12d825` (LayoutView refresh collision fix)

---

## 1. Two different “Hub” surfaces (must not be conflated)

| Surface | Where it lives | How user reaches it | Interaction model |
|--------|----------------|---------------------|-------------------|
| **Embedded Discord Activity** | Web app in Discord iframe (`*.discordsays.com` proxy) | Talk channel → Activity shelf / App Launcher → Hub | Requires Embedded App SDK `ready()` + authorize + scopes; controls are ordinary DOM in the iframe |
| **Native `/hubview`** | Discord bot message (Components V2) in a text channel | Slash command `/hubview` | Discord message components / views registered on the bot; no iframe |

Issue #67 is specifically the **embedded Activity** path. `/hubview` is a separate native bot message and is out of scope for “Activity is view-only” unless proven broken independently.

Evidence of separation:
- `gaming-network` root ships static `index.html` + `activity-sdk.js` and README-DISCORD.txt (“Configure the Discord Activity URL”).
- `gaming-network-hub` ships React routes (`/`, `/discord`, `/games`, `/host`, …) with **no** `@discord/embedded-app-sdk` dependency and **no** Activity entry bootstrap in the route tree.
- Issue #17 historical notes explicitly distinguish “Discord Activity” (iframe Hub with feed tiles) from “`/hubview`” (native Components V2 message).

---

## 2. What is actually deployed as the Activity URL today

### 2.1 Static Activity shell (`gaming-network` main)

`activity-sdk.js` (current main):

```js
import { DiscordSDK } from "/sdk/@discord/embedded-app-sdk@2.5.0";
const discordSdk = new DiscordSDK("1566288861259108424");
async function connectActivity() {
  await discordSdk.ready();
  // status → "Connected to Discord!"
  const auth = await discordSdk.commands.authorize({
    client_id: "1566288861259108424",
    response_type: "code",
    state: "",
    prompt: "none",
    scope: ["identify"]   // ← only identify
  });
}
connectActivity();
```

`index.html` (current main) is a **duplicated** document (two full HTML documents concatenated). Symptoms of that alone:
- Second document’s scripts/DOM can be ignored or partial depending on browser parse recovery.
- `#discord-status` appears only in the second fragment; the first fragment’s UI is the one users mostly see.
- Local games (tic-tac-toe / dice) are present in both fragments but are **not** wired to Discord session state, channels, or Hub feed selectors.

`index.before-sdk.html` used a CDN script + placeholder `YOUR_DISCORD_APPLICATION_ID` — not production-ready.

README-DISCORD.txt still says Activity URL must be configured and does not document URL mappings, proxy paths, or scopes beyond the minimal SDK call.

### 2.2 React hub (`gaming-network-hub`)

- Route tree has **no** `/activity` route.
- `/discord` is labeled “Discord Activity” in UI copy but is a **sample-data only** page:

  > “A preview of what the Gaming Network bot will show. Nothing here is read from Discord”

- Provider is hard-coded mock:

  ```ts
  export const gn: GamingNetworkProvider = createMockProvider();
  // getIntegrationStatus → discordVerified: false, gamesVerified: false, signInConfigured: false
  ```

- Channel selector / message list buttons work in the browser against **seed data**; they do not call Discord APIs or the bot.
- No Embedded App SDK import, no `discordSdk.ready()`, no `authorize`, no instance/channel context from Discord RPC.

Conclusion: even if Discord’s Activity URL mapping pointed at the React app, the app is intentionally a **preview**, not an interactive live Hub. If the mapping points at the static `gaming-network` root, the page is a thin shell with minimal SDK handshake and no Hub controls.

---

## 3. Root-cause analysis (evidence-based, not speculative)

### Primary cause (code-level)

**The surface launched by Talk → Activity → Hub is not the interactive Hub the owner previously used.**

Supporting facts:
1. Static Activity shell has no feed selector, no layout controls, no public-X / calendar tiles, no “This Channel” integration — only basic navigation + local toy games + minimal `identify` authorize.
2. React `/discord` route that *looks* like a Hub uses mock data and never attaches Embedded App SDK, so inside Discord’s iframe it cannot obtain channel/guild context or drive live controls.
3. Native `/hubview` (bot Components V2) is a different product path; regression reports that only mention Activity do not automatically imply `/hubview` is broken.

### Contributing causes (verifiable in code / config)

| Factor | Evidence | Effect |
|--------|----------|--------|
| **Minimal OAuth scopes** | `scope: ["identify"]` only in `activity-sdk.js` | No channel, guild, or RPC activity write scopes; cannot drive interactive Discord-aware Hub features that need more than user id |
| **Broken / dual HTML document** | `index.html` contains two complete `<!DOCTYPE html>` trees | Parse ambiguity; status element and second UI may not mount as intended |
| **SDK path dependency** | Import from `/sdk/@discord/embedded-app-sdk@2.5.0` | Requires Discord proxy URL mapping for `/sdk/...`; if mapping missing or wrong, `ready()` fails → status becomes “Discord connection failed” and UI stays inert |
| **No Activity-specific route in hub** | `routeTree.gen.ts` has no activity entry | Deploying hub to Activity URL serves website chrome, not an Activity bootstrap |
| **Mock provider always** | `gn.mode === "mock"`, `discordVerified: false` | Any hub UI opened in Activity still advertises sample-only behavior |
| **Bot vs Activity deploy drift** | Issue #67 cites frontend `76c37237` and bot `4f4397d` | Bot LayoutView fix does not change Activity iframe content; frontend PR #35 was “launch shortcuts to Live Games,” not Activity SDK/control restoration |

### Explicit non-causes (ruled out by inspection)

- Not caused by change-bridge / PR #71 work (different package; issue predates / is orthogonal).
- Not caused by private-channel message leakage (static shell and mock provider never read private Discord messages).
- Not proven to be a pure Discord client bug without first fixing URL mapping + SDK bootstrap + dual HTML.

---

## 4. Distinction: what “view-only” means in practice

Observed product states that match “view-only”:

1. **Activity iframe loads static shell** → user sees Welcome / Poker Lobby / Games cards; local buttons may work (DOM), but nothing Discord-session-aware works → feels “view-only Hub.”
2. **Activity iframe loads React site** → user sees Launch Panel / Discord hub with sample badges; selectors change sample messages only → still not live interactive Hub.
3. **SDK `ready()` fails** (wrong mapping, wrong client id, CSP) → status text “Discord connection failed”; remainder of page still static → view-only.
4. **`/hubview` still works** (possible) while Activity does not — confirms surfaces are independent.

---

## 5. Reproducible regression tests (no live guild mutation required for steps 1–4)

### T1 — Static shell structure (offline)

See `test_activity_regression_offline.py`.

**Pass criteria:** dual document detected; only `identify` scope; client id present.

### T2 — Hub frontend is mock-only for Discord (offline)

```bash
# From gaming-network-hub
rg -n "embedded-app-sdk|DiscordSDK|discordsays" src || echo "no SDK usage"
rg -n "createMockProvider|discordVerified: false" src/lib/gn
rg -n "Nothing here is read from Discord" src/routes/discord.tsx
```

**Pass criteria:** zero Embedded App SDK imports; mock provider; explicit sample disclaimer on `/discord`.

### T3 — Route tree has no Activity bootstrap (offline)

```bash
rg -n "path: '/activity'|createFileRoute(\"/activity\"" src || echo "no /activity route"
```

**Pass criteria:** no `/activity` route in generated tree.

### T4 — SDK handshake simulation (local browser, not Discord)

1. Serve static shell over HTTPS (or Discord’s local proxy per docs).
2. Open outside Discord: expect `ready()` to fail or hang (no RPC parent) → status not “Connected to Discord!”.
3. Open inside Discord Activity with correct URL mapping: expect `ready()` success **or** explicit failure logged; capture console.

**Pass criteria:** documented status string + console error captured; no silent success without parent frame.

### T5 — In-Discord comparison (owner-only; no server structure changes)

| Step | Action | Expected if regression present |
|------|--------|--------------------------------|
| A | Text channel → `/hubview` | Native message with feed selector **above** content; Refresh works |
| B | Voice/Talk → Activity → Hub | Iframe loads; either static shell or React sample UI; **no** live feed tiles / layout controls matching historical interactive Hub |
| C | DevTools console inside Activity iframe | SDK errors, failed module load for `/sdk/...`, or authorize errors |
| D | Confirm Application → Activities → URL Mapping in Developer Portal | Map prefix `/` (and `/sdk` if used) to actual host; client id `1566288861259108424` |

Record PASS/FAIL with screenshot + exact console text. Do not change guild channels or roles for this test.

### T6 — Privacy guard (must remain true)

- Activity UI must not display private channel message bodies or redemption codes.
- Static shell and mock provider currently satisfy this by **not** loading live Discord content.

---

## 6. What Batch 2 must fix (preview of repair scope)

On a **new isolated frontend branch** (not PR #71):

1. Single Activity entry document (remove dual HTML).
2. Correct Embedded App SDK bootstrap: `ready()` → authorize with required scopes only after owner-approved scope list → clear connection state UI.
3. URL mapping documentation + `/sdk` proxy path if using module import form.
4. Interactive controls that work **without** reading private Discord messages (public feeds, layout toggles, error states).
5. Preserve existing public routes `/`, `/discord`, `/games`, `/host`, website chrome.
6. Automated tests for bootstrap states + interaction smoke; draft PR only.

Batch 2 must not enable private channel reads or paid X polling.

---

## 7. Batch 1 deliverable status

| Item | Status |
|------|--------|
| Distinguish Activity vs `/hubview` | Done |
| Inspect Activity shell + hub frontend | Done |
| Root cause from code evidence | Done — Activity surface is not an interactive live Hub implementation |
| Reproducible offline regression tests | Done (T1–T4, T6); T5 owner in-Discord |
| Live Discord mutation | Not performed |
| PR #71 changes | Not performed |

**Verdict:** Regression is consistent with the **wrong or incomplete Activity application surface** (static dual-HTML shell with identify-only SDK, and/or React mock `/discord` without SDK), not with a single-line bot regression alone. Batch 2 should restore a real Activity entry with verified SDK connection states and interactive public controls.
