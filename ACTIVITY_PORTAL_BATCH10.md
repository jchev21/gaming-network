# Batch 10 — Discord Activity Portal configuration (#67)

**Application client ID:** `1566288861259108424`  
**Public proxy hostname:** `1566288861259108424.discordsays.com`  
**Shell on `main`:** single `index.html` + `activity-sdk.js` (PR #74 merged)  
**Status:** Owner portal steps required. This package does **not** claim live Talk → Activity PASS.

Official docs: [URL mappings](https://discord.com/developers/docs/activities/development-guides/local-development) · [Networking](https://discord.com/developers/docs/activities/development-guides/networking) · [How Activities work](https://docs.discord.com/developers/activities/how-activities-work)

---

## 1. Prerequisites (must be true before portal toggles)

| # | Requirement | How to verify |
|---|-------------|----------------|
| P1 | Shell is **single** HTML document (no dual `<!DOCTYPE`) | `python3 test_activity_portal_preflight.py` |
| P2 | `activity-sdk.js` imports SDK from `/sdk/@discord/embedded-app-sdk@2.5.0` | preflight |
| P3 | Client ID in shell matches portal app | `1566288861259108424` |
| P4 | Activity host serves `index.html` + `activity-sdk.js` over **HTTPS** | browser / curl |
| P5 | Host is a **directory root**, not a file path | Discord rejects file targets |

---

## 2. Developer Portal — exact URL mappings

Path: **Discord Developer Portal → Application → Activities → URL Mappings**

### Formatting rules (Discord)

- **Target must omit protocol** — use `your-host.example.com`, **not** `https://your-host.example.com`
- Target must be a **directory / host**, not `…/index.html`
- Longer prefixes before shorter ones if they share a path root
- You **cannot** enable Activities without at least one valid URL mapping

### Required mappings for Gaming Network Hub

| PREFIX | TARGET (examples) | Purpose |
|--------|-------------------|---------||
| `/` | `<your-https-activity-host>` e.g. `activity.example.com` or Railway/Cloudflare hostname **without** `https://` | Serves `index.html` at Activity root |
| `/sdk` | `cdn.jsdelivr.net/npm` | Resolves `import { DiscordSDK } from "/sdk/@discord/embedded-app-sdk@2.5.0"` |

Optional (only if the shell later calls Discord REST from the iframe):

| PREFIX | TARGET |
|--------|--------|
| `/discord` | `discord.com` |

### After mapping

1. **Activities → Settings → Enable Activities** = ON  
2. Save  
3. Ensure the app is installed / available in guild `1566290427366080612`  
4. Open Discord desktop/web → **Talk** channel → **Activity** shelf → **Hub** (or your Activity name)

### Local tunnel (dev only)

```text
cloudflared tunnel --url http://localhost:8080
# Map PREFIX /  →  <tunnel-host without https://>
```

---

## 3. Connection states (what the owner should see)

| Badge | Meaning | Action if stuck |
|-------|---------|-----------------|
| Connecting | Bootstrap started | Wait; if permanent → check `/sdk` mapping |
| SDK ready | `ready()` resolved | Should proceed to authorize |
| Discord Activity connected | `authorize(identify)` OK | Success path |
| Browser preview | Opened outside Discord iframe | Expected on plain browser; use Talk → Activity for full test |
| Connection error | SDK/authorize failed | Map `/sdk`, confirm client ID, check console |

Public feed/layout/game controls must remain clickable even on Connection error.

---

## 4. Real-user evidence checklist (D1–D9)

Fill after portal config. Do **not** mark PASS without evidence.

| ID | Step | Pass | Fail | Result | Evidence |
|----|------|------|------|--------|----------|
| D1 | Talk → Activity → Hub loads | Single shell UI | Blank / 404 / dual chrome | | |
| D2 | Connection badge | connected / authorized / explicit error | Infinite “Initializing…” | | |
| D3 | Feed buttons | Stage content changes | Dead | | |
| D4 | Layout 1 / 2 panes | Layout changes | No change | | |
| D5 | Refresh feed | Status or stage updates | No response | | |
| D6 | Games: tic-tac-toe + dice | Clicks work | Dead | | |
| D7 | Privacy | No private channel msgs / redeem codes | Private content shown | | |
| D8 | Browser open of host | “Browser preview” | False “authorized” | | |
| D9 | `/hubview` slash | Native message still works | Bot regression | | |

---

## 5. Offline commands

```bash
python3 test_activity_portal_preflight.py
python3 test_activity_interaction.py
python3 -m http.server 8080
# → http://127.0.0.1:8080  expect Browser preview badge
```

---

## 6. Out of scope / not claimed by Batch 10

- Completing D1–D9 without owner portal access  
- Changing OAuth scopes beyond `identify`  
- Member grant (#78) enablement  
- Paid X polling  

**Batch 10 delivers the portal runbook + offline preflight.** Live Talk → Activity PASS remains an owner-recorded result on the checklist above.
