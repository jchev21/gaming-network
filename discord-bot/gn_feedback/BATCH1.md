# Batch 1: feedback intake / GitHub issue outbox

New files only. bot.py, commands, dashboards, Railway setup and other
/data files are unchanged. Defaults OFF. No live request, AI call,
push, deployment or X action was performed.

Batch 2 adds worker handoff/owner controls; Batch 3 integrates actual
lifecycle. Do not enable production delivery before those reviews.

## Architecture

Additional commands.Bot listener -> redaction -> SQLite receipt and
deduplication -> one durable issue outbox -> fixed PRIVATE
jchev21/gaming-network repository.

Classification is channel-based; reports are unverified.
Steps/expected/actual stay in the description when supplied.
Priority/category remain untriaged/general, not invented AI judgments.

## Configuration and permissions

Use .env.feedback.example as names/placeholders only.
Real values belong in owner-managed secrets.

Hash key: stable random private value >=32 characters.
Changing it resets member rate identities.

GitHub least privilege: Issues read/write and Metadata read on this
repository only. No Contents/PR/Actions/admin permission.

Labels bug, enhancement, discord-feedback and needs-triage must
already exist. Public repositories are refused.

## Privacy and attachments

Redaction removes known environment secrets/common credential
patterns, prose URLs, emails and mentions. It cannot identify every
unknown secret or personal detail. Channels must be opt-in with a
pinned no-secrets notice.

Attachment metadata only:
- At most four PNG/JPEG/WebP/TXT/LOG references.
- At most 2 MiB each.
- Approved Discord CDN paths/suffix/MIME.
- Never downloaded or executed.
- Signed queries are stripped; references can expire.
- Return to the original Discord message for evidence.

No raw display names/author IDs are stored: rate keys use HMAC.
Message/channel IDs and source URLs are necessary traceability
identifiers, not anonymous data.

## Persistence and limits

SQLite WAL, synchronous FULL, schema v1, transactional receipts,
exclusive process flock, new files mode 0600.

One Linux bot process/replica on /data only.
No distributed-replica support.
No silent corrupt-database reset.

Limits:
- 3 reports/member/10 minutes.
- 30 total reports/hour.
- 10000 receipts.
- 1000 groups.
- 200 unfinished groups.

No automatic deletion of idempotency receipts.
Owner must define retention/maintenance before caps are reached.
Queue versions preserve reports arriving during delivery.

## GitHub creation and retries

Persist CREATE intent before POST.
Unknown outcome -> reconcile marker, NEVER blindly repeat POST.

Search at most 500 newest issues.
No/multiple matches or inaccessible history -> manual dead-letter.

Five failed attempts maximum, durable backoff, Retry-After/reset
respected, serialized writes >=1 second apart, all redirects refused.

This sacrifices availability rather than claiming exactly-once
remote POST.

Dead/uncertain receipts must not be cleared to force new creation.

## Managed updates and acknowledgements

Updates replace a managed body block.
Append human notes after its end marker or use comments.
Labels/state/assignments are preserved.

Concurrent human BODY edits between GET/PATCH can race: not atomic.
Review this limitation before production.
Batch 2 decisions must use protected job state/comments, not report
instructions.

Acknowledgements use at-most-once durable send intent.
A crash/send failure can lose an acknowledgement rather than spam
duplicates; the receipt survives.

No private GitHub URL or raw error appears in acknowledgements.
Batch 2 supplies owner/status/reconciliation controls; not faked here.

Diagnostic SQL:
SELECT id,state,issue,attempts,error FROM groups;

Do not dump member content or secrets.

## Existing bot integration boundary

This is an integration seam, NOT a verified patch.

Requires:
- discord.py 2.x commands.Bot/AutoShardedBot.
- Approved Message Content intent.
- View/Send permissions in the configured channels.

Add a listener; never replace on_message or double-call
process_commands.

In the real async startup hook:
1. Call build_feedback(actual_bot).
2. If not None, call start() once.
3. Retain the instance.
4. Await stop() during the existing shutdown lifecycle.

Do not start unguarded on reconnecting on_ready.

Actual bot/dependencies were not inspected.
Provide discord-bot/bot.py as text for Batch 3's precise diff.
No insertion line or existing variable name is invented.

## Exact local test command

From repository root:

python3 -m unittest discover -s discord-bot/tests -p 'test_gn_feedback.py' -v

Observed Python 3.12.8:
19 tests PASS, exit 0.

Temporary SQLite + mocked GitHub/Discord, no network.

NOT RUN:
- Real discord.py lifecycle and permissions.
- GitHub token/labels/private metadata checks against real GitHub.
- Railway version/mount/backups/replica.
- Live acceptance.

## Optional Linux Docker command

NOT RUN. Image must already be available; any pull is separate:

docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD:/src:ro" -w /src python:3.12-slim python -m unittest discover -s discord-bot/tests -p test_gn_feedback.py -v

No new core dependencies.
No existing Docker/start command is modified.

## Rollback

Disable both flags.
Stop the listener.
Back up with SQLite backup API or after clean shutdown.
Do not copy only the DB while WAL is active.

Remove only the reviewed integration hook.
Retain receipts/markers.

Restoring an older database can resurrect create attempts:
reconcile remote issues before re-enabling.

Never delete the database to clear failures.
Do not touch other /data files.

No automatic X polling/private feeds, merge/deploy or permissions
changes.

Batch 1 is an offline-tested foundation, not complete production
acceptance.

Stop before Batch 2.
