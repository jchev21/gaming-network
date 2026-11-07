# Gaming Network Discord Bot — Railway deployment package

The original local bot, challenge commands, and renderer are retained. Only safe
cloud data storage paths and the API URL override were updated.

## IMPORTANT: prerequisites before launch

- **Rotate** any Discord bot token that was previously posted in a chat or terminal screenshot.
- Keep this bot's `DISCORD_TOKEN` exclusively in Railway Variables (sealed if available).
- In Discord Developer Portal, enable the required **Message Content** and **Server Members** privileged intents if your approved bot needs the features that use them.
- Shut down the Mac bot using this same token before enabling the hosted bot, to avoid two running instances.

## Deploy into the existing Railway project (not a second project)

1. Add this complete `discord-bot` directory to the EXISTING
   `jchev21/gaming-network` GitHub repo. Do not overwrite its web files.
   Do NOT commit `config.json`, `.env`, `hub_data.json`, `state.json` or tokens.
2. In the existing Railway service **discord-hub-bot**, connect that
   GitHub repository on `main`, with Root Directory `discord-bot`.
   The included Dockerfile installs dependencies and runs `python -u bot.py`.
3. Under Variables set:
   - `DISCORD_TOKEN`: freshly rotated Discord bot token (keep secret)
   - `DATA_DIR`: `/data`
   - `API_SERVICE_TOKEN`: Railway reference to the API's secret
   - `GAMING_API_URL`: `https://gaming-network-api-production.up.railway.app`
   - `PYTHONUNBUFFERED`: `1`
   Existing values other than `DISCORD_TOKEN` were preconfigured on Railway.
4. Keep the already attached **discord-hub-data** volume mounted at `/data`.
   This package stores its `config.json`, `hub_data.json`, and
   `challenge-settings.json` there after boot. Existing Mac files are unchanged.
5. **Do not add a public domain to the bot service.** Its embedded dashboard
   has unauthenticated chat read and message send routes and is intentionally
   loopback-only. We can build a separate authenticated public dashboard later.
6. Deploy once the secret is configured. Inspect deployment logs for
   `Hub connected as ...` and `Guild commands synced` / command sync result.

## Discord challenge setup after it connects

As an admin, run `/challenge_setup` and select the Affiliate role. Give that
role to trusted hosts. Hosts use `/challenge_create` with a pre-created Poker
Now table URL. Players use `/challenge_join`, up to five unique Discord users.
Reservations and table link sharing work; the host still seats players manually.
Reward issuance, verified game results, X mentions, and actual promo code
redemption are not implemented by this package.

## Persistence and migration

The hosted Railway volume is separate from your Mac's local folder. The hosted
bot starts with defaults if `/data/config.json` does not already exist.
To import your Mac's existing private config or bot data, copy those files into
`/data` by an authenticated Railway shell or another secure migration method.
Never commit them to a public repo. This package does not overwrite saved data.

## Verify

Run `python -m py_compile bot.py challenge_commands.py render.py` before upload.
Do not test with a real bot token in a public file or GitHub Actions log.
