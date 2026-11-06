# Rollback Guide — Gaming Network Hub

**Principle:** Prefer reversible, data-preserving actions. Do not delete the Railway volume or rotate tokens as a first response.

## What this package does **not** change

- Live Discord guild structure (planner is dry-run only)
- Railway environment variables
- Production deployment pins (unless owner deploys)
- Bot identity / application ID

## If a bad deploy reaches Railway

1. **Do not** delete the `discord-hub-data` volume.
2. In Railway, open the `discord-hub-bot` service → Deployments.
3. Redeploy the **last known good** deployment (pinned commit / previous successful image).
4. Confirm logs show `Hub connected as ...` and command sync.
5. Spot-check `/points` and a dashboard open on a test account.

## Data backup / recovery

| Asset | Location | Recovery notes |
|-------|----------|----------------|
| `config.json` | `/data/config.json` on Railway volume | Export via Railway shell or volume backup before risky changes |
| `hub_data.json` | `/data/hub_data.json` | Same; contains points, feed, codes metadata |
| Challenge settings | `/data` (if present) | Preserve alongside hub data |
| Mac local copies | Operator machine | Not overwritten by Railway package |

Before any experimental migration:

```text
# Conceptual — run only in an authenticated Railway shell under owner control
cp /data/config.json /data/config.json.bak.$(date +%Y%m%d)
cp /data/hub_data.json /data/hub_data.json.bak.$(date +%Y%m%d)
```

This package does not automate those copies.

## Discord guild rollback

- Channel/role creates performed **manually** by the owner can be deleted or renamed manually.
- Prefer **hiding** or permission-locking a mistaken channel over immediate hard delete if messages matter.
- Role permission mistakes: restore previous permission overwrites from your notes or audit log.
- Never mass-delete channels based on the planner alone.

## Application / token incidents

| Incident | Action |
|----------|--------|
| Token leaked | Rotate in Discord Developer Portal → update Railway Variable only → restart service |
| Two bots online with same token | Shut down the unintended instance (Mac or extra service) |
| Privileged intent disabled by accident | Re-enable in Developer Portal; bot will reconnect on next ready |

## Git / PR rollback

- This work lives on branch `ai/launch-readiness`.
- Draft PR targets `fix/discord-dashboard-response`.
- To abandon: close the draft PR; leave production branch untouched.
- Do not force-push over shared history without owner agreement.

## What to avoid

- Deleting the Railway project or volume
- Committing secrets "to fix" a deploy
- Re-inviting a second bot application
- Enabling X intake as a rollback step
- Claiming data loss is impossible — always backup first

## Verification after rollback

1. Bot online, single session.
2. Slash commands respond.
3. Points / feed data consistent with pre-incident expectation.
4. Dashboard loopback still not public.
5. Record outcome in `TEST_RESULTS.txt` or operator notes.
