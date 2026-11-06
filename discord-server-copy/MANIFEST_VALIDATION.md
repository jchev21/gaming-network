# Discord copy manifest — offline handoff

## Additions

- discord-server-copy/manifest.json
- discord-server-copy/existing-channel-map.json
- discord-server-copy/existing-channel-inventory.example.json
- tools/validate-discord-copy.py
- tests/test_discord_copy_manifest.py
- discord-server-copy/MANIFEST_VALIDATION.md

Previous onboarding/Coming Soon markdown files are referenced, not overwritten.

No GitHub/Discord access, posting, edits, permission changes or network calls.
Python 3.9+ standard library only.

## Meaning and stable keys

Seven category definitions, eleven channel definitions and twenty-six
explicitly unresolved video URLs.

Six categories are included by default. The previously optional
accounts/providers category remains excluded.

Exactly one proposed conversation channel/category.
Information pages are read-only.
Bug/suggestion intake channels are separate operational channels,
not extra general chat.

Version-1 category/channel keys and purposes are fixed by validation.
Proposed names can change without changing stable keys.

Existing names are preserved:
name_hints are suggestions, NOT discovered channels or automatic matches.

read_only is a desired copy/layout flag, NOT an observed Discord permission.

## Reuse existing channels

1. Inventory the intended guild offline using owner-reviewed existing records.
   Start with the empty inventory example; no IDs are invented here.

2. Category records have exact keys:
   id, name.

3. Text-channel records have exact keys:
   id, name, category_id, kind, permissions_reviewed, member_posting,
   private_content_reviewed.

   kind must be text.
   member_posting is unknown, allowed or denied.
   Review flags are explicit booleans.
   These are operator attestations, not claims verified by this tool.
   IDs are strings, never numbers.

4. Populate category_map/channel_map with existing IDs, not newly desired IDs.
   Populate guild_id and configured_intake_ids from existing approved settings.
   Do not put tokens/secrets into these files.

5. One existing category/channel ID cannot fill two logical targets.
   Existing channel must already belong to the mapped category.
   The tool never moves it.

   Bug/suggestion mappings must equal existing configured intake IDs.

6. Unmapped server channels remain untouched.

   Validation enforces the proposed layout, not an assertion that the entire
   actual server already has exactly one conversation channel/category.

   Review extra existing channels manually. Do not delete, close or expose
   them to satisfy this manifest.

## Video resolution

Every unknown URL is JSON null, url_status unresolved, approved false.

Keep placeholders stable so the owner can identify the missing guide.

Resolve only genuinely available approved HTTPS videos:
- Set url.
- Set url_status to resolved.
- Set approved to true.
- Leave transcript_url null unless a transcript actually exists.

Remove references to unmade guides from active indexes/copy instead of
inventing videos.

Optional/inactive category videos do not block other indexes.

The separate planned Algo Lab preview video is referenced by its Coming Soon
copy. Resolving a link does not change the feature's Coming Soon release label.

URL checks are syntax/policy only:
no existence, reachability or access test occurs.

Normal watch queries are allowed.
Obvious credential/signature query keys, userinfo, non-HTTPS, IP hosts and
fragments are refused.

Do not use signed or credential-bearing links.
Approval markers do not authenticate provenance.

## Exact commands from repository root

python3 -m unittest discover -s tests -p test_discord_copy_manifest.py -v

python3 tools/validate-discord-copy.py

python3 tools/validate-discord-copy.py --ready

For later fully populated local review:

python3 tools/validate-discord-copy.py --inventory PATH_TO_REVIEWED_INVENTORY.json --copy-root . --ready

Exit 0:
Structurally valid draft.
With --ready, locally complete handoff.

Exit 1:
Valid structure, but --ready found unresolved/review blockers.

Exit 2:
Invalid schema, mapping, input or policy violation.

--copy-root checks the actual five previously delivered copy documents for
unresolved placeholders and preserves Coming Soon labels.

Without --copy-root, readiness always stays false.

Nothing substitutes video URLs into text automatically.

READY means local consistency plus operator-provided assertions,
NOT permission to publish or confirmation of real Discord/video access.

## Observed results

Python 3.12.8:
18 tests PASS, exit 0.

Default draft validation:
exit 0
handoff_ready false
26 unresolved videos
43 handoff blockers

Default --ready validation:
exit 1
intentionally blocked

No actual guild IDs, existing channels, video availability, permissions or
previous markdown files were externally verified.

The real copy documents were not present in this test workspace.
Ready-mode positive tests use clearly synthetic IDs, URL strings and minimal
test copy, not actual server mappings.

No deployment or Discord changes performed.

No hourly X guard implementation or coverage status is changed by this
copy-only batch.
