# Issue #79 — In-person onboarding runbook (owner only)

**Do not mark this issue passed from CI or agent output.**  
Record evidence privately (screenshots / notes). Production safety flags stay OFF until you decide otherwise.

## Pre-flight

- [ ] `/onboarding-audit` still reports Screening=true, Manage Roles=true, Rules Accepted + Member assignable  
- [ ] `#rules` and `#verify-x` exist; `#verify-x` restricted as intended  
- [ ] `GN_MEMBER_GRANT_ENABLED=false` and `GN_DISCORD_MEMBER_GATE_ENABLED=false` unless this is an intentional staging enable  
- [ ] Second Discord account + second X account ready (not the owner accounts)

## Steps

| # | Action | Pass criteria | Result | Evidence |
|---|--------|---------------|--------|----------|
| 1 | Fresh Discord account joins | Sees Start Here / rules; **cannot** see `#verify-x` before screening | | |
| 2 | Accept native Membership Screening | `pending` clears | | |
| 3 | Rules acknowledgment path | **Rules Accepted** granted once | | |
| 4 | `#verify-x` visibility | Visible only to intended roles | | |
| 5 | X sign-in from `#verify-x` | Real OAuth for owned X account | | |
| 6 | Wrong / canceled X OAuth | **No** Member granted | | |
| 7 | Member still not auto from X alone | Confirm no Member if grant flag OFF | | |
| 8 | (Staging only) Enable grant path once | Member appears after S2S confirm | | |
| 9 | Host game with Member | #68 gate allows create | | |
| 10 | Second account join | Lottery / first-come OK; secrets private | | |
| 11 | Revoke Member; retry host/join | Denied | | |
| 12 | Public channels | No codes, tokens, private messages | | |

## Sign-off

- Owner: _________________ Date: _______  
- Staging grant enabled temporarily: Y/N  
- Production flags left false: Y/N  

Issue #79 remains **open** until the owner completes this sheet.
