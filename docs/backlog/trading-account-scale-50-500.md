# Trading account registry: staged 50 → 100 → 200 → 500 plan

Status: **DESIGN ONLY**. No accounts connected, no credentials stored, no brokerage orders, no provider integrations, no production deployment. This proposal addresses the LATER/DEFERRED section of master issue #2.

## Product boundary
An opt-in, read-only inventory and reporting dashboard for accounts the member owns or is explicitly authorized to view. Do not build account creation, trading, order replication, credential scraping, or automated provider sign-in. Manual/synthetic data is always labeled as such. Any provider connection requires a separately reviewed terms/permissions matrix and explicit owner consent.

## Data model (proposed, not implemented)
- `members`: internal opaque member ID, tenant ID, status.
- `firms`: stable internal firm ID, display name, connection policy, source documentation and last terms review date.
- `accounts`: UUID, tenant ID, firm ID, **encrypted or keyed-hash provider identifier** plus masked display suffix, display label, owner authorization record, strategy group, lifecycle status, created/updated timestamps. Unique (tenant, firm, normalized provider ID) enforced server-side; do not expose identifiers to public APIs.
- `account_snapshots`: account ID, observed-at UTC, imported-at UTC, source (manual / approved API / synthetic), currency, allocated size, equity, cash balance, daily/weekly realized and unrealized P&L, payout totals, freshness/quality flags, source event ID. Append-only snapshots with deterministic deduplication.
- `sync_jobs`: tenant, account, provider, status, attempt count, next-attempt, retryable failure class, last success, source request ID. No tokens or provider payloads in logs.
- `audit_events`: actor, tenant, action, affected resource ID, timestamp, request correlation ID; no secrets or unmasked account identifiers.

**Calculations:** distinguish allocated/funded capital from equity/balance. Sum the latest valid snapshot per unique account, never sum all historical snapshots. Account status and source freshness accompany each number. Never aggregate different currencies without a displayed FX source, conversion timestamp and clear conversion methodology; otherwise group totals by currency. Payouts are separate cashflows and must not be silently added to equity. Do not conflate reported equity with verified broker equity.

## Staged delivery and acceptance gates

| Stage | Safe scope | Testable acceptance (all synthetic first) |
| --- | --- | --- |
| 50 | Manual account registry, masking, firm grouping, allocation vs equity, freshness and source badges, basic alerts | 50 unique fixture accounts; duplicate import rejected; unauthorized tenant cannot read/write; one snapshot per account in totals; mixed-currency totals separated; zero secrets in exports |
| 100 | Search/filter by firm, strategy, owner and status; audited CSV import/export; responsive list | 100 synthetic accounts; malformed CSV rejected with row-specific errors; repeated import idempotent; masked exports; mobile/keyboard tests; aggregate reconciliation against independent fixture oracle |
| 200 | Approved read-only sync adapter interfaces, bounded queues, retry/backoff, provider rate limits, reconciliation | 200 synthetic accounts with injected 429/500/timeouts; bounded concurrency; exponential backoff + jitter; no duplicate snapshot on retry; failed provider cannot block other firms; sync freshness and errors visible |
| 500 | Server pagination or virtualization, tenant-aware RBAC, recovery drills, observability and capacity estimates | 500 synthetic accounts; measurable p50/p95 response times and memory/queue depth under representative load; cross-tenant isolation; restart/retry recovery; report infrastructure costs rather than assuming targets |

## Metrics and SLO proposal
- Inventory: total / active / connected / stale / disconnected accounts, grouped by firm and tenant.
- Quality: reconciliation mismatch count, import reject count, duplicate-suppression count, missing snapshot count.
- Sync: success/failure percentage, latest successful observed-at, p95 sync lag, retry queue age, provider 429 count.
- Finance: allocation, equity, P&L and payouts with currency and provenance; verify exact totals using fixture oracle.
- Performance: p50/p95 dashboard API latency, DB query time, browser render time, memory and sync-worker concurrency for 50/100/200/500 fixture sizes. Record actual numbers during implementation, not invented thresholds.

## Provider integration matrix (template; **no approvals implied**)
| Firm/provider | Official read-only API | Allowed scopes/terms | Rate limits/cost | Reconciliation fields | Approval |
| --- | --- | --- | --- | --- | --- |
| Each proposed firm | **UNVERIFIED — research per firm** | **UNVERIFIED** | **UNVERIFIED** | **UNVERIFIED** | **NOT AUTHORIZED** |

Do not claim an integration exists based on a marketing website or unofficial endpoint. Explicitly verify API access, firm rules, data retention, payout semantics, rate limits, fees and permitted automation before writing an adapter.

## Threat model / safeguards
- **Account takeover and cross-tenant leaks:** authenticate server-side; authorize every account/snapshot/export; test tenant A cannot enumerate B by ID or cursor.
- **Sensitive financial records:** encrypt at rest and in transit, limit retention, mask identifiers, audit reads/exports, define deletion and backup retention.
- **Secrets:** only server-side secret manager; never raw passwords, tokens in client, logs, GitHub, exports or Discord.
- **Untrusted imports:** CSV size/row limits, schema validation, formula injection prevention, safe decimal parsing, explicit timezone/currency.
- **Bad totals:** use integer minor units or decimal arithmetic, reject NaN/Infinity, avoid double-counting and unsupported FX conversion.
- **Provider abuse:** enforce approved scopes, quotas and backoff; no unattended login automation or prohibited cross-account trading.
- **Deployment:** separate review, test and owner approval required before any persistent schema or live service changes.

## Implementation sequence
1. Review this document and confirm supported firms, account ownership model and reporting definitions.
2. Add synthetic fixtures, independent aggregation oracle and contract tests in a separate implementation PR.
3. Build read-only/manual registry UI behind a disabled feature flag, with no connection to existing Discord bot or X hosting.
4. Validate full CI, accessibility and load tests before any rollout; later request explicit owner authorization for production or provider OAuth.

## Non-goals
No brokerage password collection, live trading, account replication, funded-account rule circumvention, prize eligibility, public financial leaderboards, live Discord feed access or production changes.
