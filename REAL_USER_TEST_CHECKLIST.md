# Batch 4 — Real-user live-test readiness checklist

**Mission:** Discord Activity restoration (#67) + X / Discord Member live-test readiness (#68 / #46)  
**Date:** 2026-11-06  
**Status:** REVIEW ONLY — do not merge or deploy without owner sign-off  
**Official X handle under test:** `@xyzhub`

---

## 0. Branch / commit map (evidence)

| Batch | Purpose | Branch | Head SHA | PR |
|------|---------|--------|----------|-----|
| 1 | Activity regression diagnosis | `grok/activity-regression-diagnosis-1106` | `894abcef82d1ce7685776e293845efd6cd21c1fe` | (docs only) |
| 2 | Interactive Activity shell | `grok/activity-interaction-fix-1106` | `1c3cd18b174ede824cee5b7ca5e408e9687da1ff` | [#74](https://github.com/jchev21/gaming-network/pull/74) draft |
| 3 | Offline two-account acceptance (PR #68 unchanged) | `grok/two-account-acceptance-1106` | `fb1cb5aa0a6e793fb418f9eea298bc823680c681` | additive on #68 head |
| 3 base | Discord Member gate (auth contract) | `feature/discord-member-game-gate-1106` | `b4d9f32bbfb1fb8caf07366d4ae7859624b192ea` | [#68](https://github.com/jchev21/gaming-network/pull/68) draft |
| — | Change-bridge (out of scope for this mission) | `grok/ai-discord-change-proposals-1106` | (see PR) | [#71](https://github.com/jchev21/gaming-network/pull/71) draft |

**Offline evidence already collected**

| Suite | Result | How to re-run |
|-------|--------|----------------|
| Activity interaction | 12/12 PASS | `python3 test_activity_interaction.py` on Batch 2 branch |
| Activity structure / diagnosis | PASS | Batch 1 docs + offline structure tests |
| Two-account acceptance | 19/19 PASS | `cd x-integration && node two-account-acceptance.test.mjs` on Batch 3 branch |
| PR #68 package tests | included in `npm test` on #68 | `cd x-integration && npm test` |

---

## 1. Pre-flight (owner only — no production writes)

Mark each row **PASS / FAIL / BLOCKED** and paste evidence (screenshot, log line, or commit SHA).

### 1.1 Discord Activity URL mappings

| # | Check | Pass criteria | Result | Evidence |
|---|--------|---------------|--------|----------|
| A1 | Developer Portal Activity URL maps `/` to HTTPS host serving Batch 2 `index.html` | Single document loads; no dual-HTML | | |
| A2 | `/sdk` maps to Embedded App SDK proxy (jsDelivr or Discord-documented) | Module import of `@discord/embedded-app-sdk@2.5.0` succeeds | | |
| A3 | Client ID matches app | `1566288861259108424` in portal and `activity-sdk.js` | | |

### 1.2 Environment (X intake / Member gate) — still OFF by default

| # | Check | Pass criteria | Result | Evidence |
|---|--------|---------------|--------|----------|
| X1 | `GN_DISCORD_MEMBER_GATE_ENABLED` | **false** in production until owner enables | | |
| X2 | Paid X polling | **OFF** — no `since_id` migration, no live poll start | | |
| X3 | Official handle config | Storage form `xyzhub` / display `@xyzhub` only after owner confirms live account | | |
| X4 | Discord OAuth app | Client ID/secret/callback registered; redirect `https://…/auth/discord/callback` | | |
| X5 | Member role ID | Exact numeric snowflake for Member role (not Moderator) | | |
| X6 | Guild ID | `1566290427366080612` (or owner-confirmed target) | | |

---

## 2. Discord Activity real-user path (issue #67)

**Surface under test:** Talk → Activity → Hub (iframe).  
**Not under test here:** native `/hubview` (separate; only confirm it still works).

| # | Step | Pass | Fail | Result | Evidence |
|---|------|------|------|--------|----------|
| D1 | Open Talk channel → Activity shelf → Hub | Activity loads | Blank / 404 / wrong app | | |
| D2 | Connection badge | Shows **Connected** / **SDK ready** / **authorized**, or explicit **Connection error** with message | Stuck on “Initializing…” forever with no error | | |
| D3 | Feed buttons (Welcome / Public X games / Calendar / Local) | Click changes stage content | No response | | |
| D4 | Layout 1 pane / 2 panes | Stage layout changes | No change | | |
| D5 | Refresh feed | Status or stage updates (public/sample only) | No response | | |
| D6 | Games tab — tic-tac-toe + dice | Clicks register | Dead UI | | |
| D7 | Privacy | No private channel messages or redemption codes visible | Private content appears | | |
| D8 | Browser preview (optional) | Outside Discord shows **Browser preview** state; controls still work | | | |
| D9 | `/hubview` still works | Native message posts / updates independently | Regression on native path | | |

**Rollback (Activity):** Revert Activity URL mapping to previous host/commit, or point `/` at last known good static tree on `main` @ `d51cf2ebd731630dcb37858a746fdf7458edc50b`. Do not delete the draft PR branch.

---

## 3. X + Discord Member game path (PR #68) — gated

**Do not enable the gate or paid polling until A1–A3 and offline 19/19 are green and owner signs the enable checklist.**

### 3.1 Offline gate (already run)

| # | Check | Result |
|---|--------|--------|
| O1 | `node two-account-acceptance.test.mjs` | 19/19 PASS (local) |
| O2 | PR #68 auth modules unmodified by Batch 3 | Confirmed in `PR68_REVIEW_NOTES.md` |

### 3.2 Real two-account acceptance (owner + second Member)

Requires: gate enabled on a **non-production or explicitly approved** environment, two X accounts, both with Discord Member role, rules screening accepted.

| # | Step | Pass | Fail | Result | Evidence |
|---|------|------|------|--------|----------|
| M1 | Host signs in with X | Session identity only; no role grant from X alone | Create allowed without Discord Member | | |
| M2 | Host verifies Discord Member | OAuth `identify guilds.members.read`; role present; `pending=false` | Missing role accepted | | |
| M3 | Host creates game | Persisted lobby; no moderator invite required when gate on | 401/403 with valid Member | | |
| M4 | Second Member joins | Join succeeds | Member cannot join | | |
| M5 | First-come mode | Seats fill; further joins blocked when full | Overflow accepted | | |
| M6 | Lottery mode | Entries open until ~5 minutes; finalize selects winners | Selects before window / leaks X ids publicly | | |
| M7 | Wrong account / no Member | Create and join denied (403) | Allowed | | |
| M8 | Public listing | Readable without auth; **no** join codes, redeem codes, X user ids | Secrets in public JSON | | |
| M9 | Role revoked mid-session | Private join-details / protected routes fail closed | Secrets still served | | |
| M10 | Handle | Public copy / config uses `@xyzhub` | Wrong or dotted forbidden form in prod config | | |

**Rollback (Member gate):** Set `GN_DISCORD_MEMBER_GATE_ENABLED=false`. Legacy invite path remains when gate is off (per PR #68 design). No cursor migration to undo if polling was never started.

---

## 4. Explicit blockers (do not paper over)

| Blocker | Impact | Owner action |
|---------|--------|--------------|
| Activity `/sdk` mapping missing | SDK import fails → connection error badge | Map `/sdk` per `ACTIVITY_URL_MAPPING.md` |
| Gate enabled without OAuth app secrets | All Member flows 403/502 | Register Discord OAuth app; set env |
| Paid X polling still desired | Out of scope for this mission | Separate approval; do not start here |
| PR #71 change-bridge | Independent; live apply OFF | Do not couple Activity / X tests to #71 apply |
| Production `X_HANDLE` change | Account ownership / API app linkage | Confirm live `@xyzhub` ownership before any env change |
| Dual-HTML still on `main` | Production Activity still broken until Batch 2 merges | Merge #74 only after D1–D9 PASS |

---

## 5. CI / offline re-run commands

```bash
# Batch 2 — Activity shell
git checkout grok/activity-interaction-fix-1106
python3 test_activity_interaction.py

# Batch 3 — two-account (on PR #68 modules)
git checkout grok/two-account-acceptance-1106
cd x-integration && node two-account-acceptance.test.mjs

# PR #68 full package (optional)
cd x-integration && npm test
```

---

## 6. Sign-off

| Role | Name | Date | Decision |
|------|------|------|----------|
| Owner | | | ☐ Activity #74 ready to merge after D1–D9 |
| Owner | | | ☐ Member gate may be enabled on staging only |
| Owner | | | ☐ Production gate + handle change deferred |
| Owner | | | ☐ Paid X polling remains OFF |

**Mission constraints honored:** no merge forced, no deploy, no live guild mutations, no paid X polling, no production cursor migration, PR #68 authorization requirements unchanged, private Discord messages never exposed in Activity shell.
