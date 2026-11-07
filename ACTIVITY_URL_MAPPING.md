# Discord Activity URL mapping (Batch 2)

**Application client ID:** `1566288861259108424`  
**Activity entry files:** `index.html`, `activity-sdk.js`

## Required Developer Portal mappings

Activities are proxied through Discord (`*.discordsays.com`). Map prefixes to the HTTPS host that serves this shell:

| Prefix | Target | Notes |
|--------|--------|--------|
| `/` | `https://<your-activity-host>/` | Main document |
| `/sdk` | `https://cdn.jsdelivr.net/npm` **or** Discord’s documented SDK proxy | Required for `import { DiscordSDK } from "/sdk/@discord/embedded-app-sdk@2.5.0"` |

Exact SDK proxy target should follow current Discord Embedded App docs. If `/sdk` is unmapped, `ready()` fails and the badge shows **Connection error** — Hub feed/layout buttons still work for public/local UI.

## Connection states (UI)

| State | Meaning |
|-------|---------|
| `connecting` | Bootstrap started |
| `ready` | `discordSdk.ready()` resolved |
| `authorized` | `authorize({ scope: ["identify"] })` succeeded |
| `browser` | Opened outside Discord iframe (preview) |
| `error` | SDK/authorize failure (message shown) |

## Privacy

- Scope is **identify only** until owner approves more.
- No private channel message APIs.
- No redemption codes in public feeds.

## Local check

```bash
python3 test_activity_interaction.py
python3 -m http.server 8080
# Open http://127.0.0.1:8080 — expect "Browser preview" state
# In Discord Activity with correct mappings — expect authorized or explicit error
```

## Related

- Issue #67 regression diagnosis: branch `grok/activity-regression-diagnosis-1106`
- Native `/hubview` is a **separate** bot message path and is not replaced by this shell
