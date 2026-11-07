# Gaming Network In-Person Launch Test Console

This is a **standalone offline manual acceptance tool**, not a production website page. Download the complete `tools/launch-acceptance-console/` directory or the reviewed ZIP from the coordinator, keep the files together, and open `index.html` locally in a browser. No npm, API keys, paid Perplexity credits, external service, OAuth, remote data or GitHub sign-in are needed. The original ZIP was delivered by Perplexity for review; this branch ports its sources under a separate repository path.

## What to do during the in-person session

The owner and a trusted second tester perform all 20 real Discord and X checks **in person**, following each case's action and expected result. Every case begins **NOT TESTED**; the console never calls Discord/X, verifies their services or grants PASS automatically. A human explicitly selects PASS, FAIL or BLOCKED, records safe details and a reference to evidence. Do not paste codes, passwords, OAuth tokens, private joining instructions or screenshots containing secrets.

Run `/hubview`, `/dashboard` and the embedded Activity inside Discord. Test member permissions with a separate trusted Discord account. For X tests, complete actual OAuth as Account A (host), a second X identity Account B (player), and Account C/anonymous access-denial checks. Exercise the FCFS join and waitlist flows and an **actual five-minute elapsed lottery** with enough entrants to observe both winners and non-winners. Check privacy and rate limits. Do not restart production systems, turn on paid X polling or use unapproved moderator credentials for a test.

All cases must explicitly PASS, a responsible owner must be named, and owner must check personal acknowledgement and click **Record manual signoff**. Any edit revokes signoff. READY only records human acceptance evidence and **does not merge, deploy or constitute launch authorization**. The GitHub issue #17 is the source of truth, and remains open until the owner explicitly approves launch.

## Save and export

Local browser storage keeps results where available; file:// storage can vary by browser and is not encrypted. Export both JSON and Markdown; some browsers ask to allow multiple downloads. Import JSON validates schema, sizes, required IDs, statuses and basic text limits; imported records are previous human claims, not independently verified. Reset requires confirmation. Export files can be uploaded to ChatGPT for review. The console makes no external network calls.

## QA

From this folder run `node test-console.mjs` to check only the console's local logic. **13 local tests on the reviewed ZIP passed**. The GitHub branch contains a readable port of this logic and should run its own tests in a checkout before integration. No browser acceptance or live Discord/X testing has been certified. Keep this draft PR unmerged until review and operator approval.

## Safety boundaries

- `X_POLL_ENABLED=false`: automatic X mention polling stays OFF.
- Private Discord channel viewer remains OFF until a separately approved post-launch issue #30.
- No secrets, private redemption codes or account identifiers in reports.
- No production deployment, hosting, paid API operations or live OAuth calls are triggered by this tool.
- Preserve all four currently running Railway services and the existing Discord bot.
- Source-of-truth launch issue: https://github.com/jchev21/gaming-network/issues/17
