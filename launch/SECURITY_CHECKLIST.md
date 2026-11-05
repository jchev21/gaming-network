# Security Checklist — Gaming Network Launch

Offline checklist for operators. Complete before any public invite expansion.

## Secrets and credentials

- [ ] `DISCORD_TOKEN` lives only in Railway Variables (sealed if available). Never in git, chat, or screenshots.
- [ ] Rotate any token that was previously exposed in terminals, logs, or messages.
- [ ] `API_SERVICE_TOKEN` and any MFP / partner keys are Railway-only; not committed.
- [ ] No `.env`, `config.json` with secrets, or `hub_data.json` committed to the public repo.
- [ ] CI workflows do not echo secret values (this package's workflows use no secrets).

## Discord application

- [ ] Privileged intents (Message Content, Server Members) enabled only if required and approved in Developer Portal.
- [ ] Bot permissions invite URL uses least privilege (avoid Administrator invite unless intentional).
- [ ] Slash commands registered to the hub guild only where possible (guild sync preferred over global).
- [ ] No public domain attached to the discord-hub-bot service. Dashboard stays on `127.0.0.1:8765`.

## Guild permissions

- [ ] Existing channel and role **IDs** preserved; renames preferred over deletes when changing structure.
- [ ] Moderator role lacks Administrator, Manage Guild, and Manage Roles unless explicitly required.
- [ ] Restricted channels (e.g. affiliate-reports, manager logs) deny @everyone and Guest/New.
- [ ] Promo codes and prize details never auto-posted to unrestricted public channels without review.
- [ ] Webhook URLs (if any) are treated as secrets.

## Anti-raid / abuse

- [ ] Verification level reviewed (Medium or higher recommended for public growth).
- [ ] Slowmode on high-traffic channels.
- [ ] AutoMod rules for mass mentions, spam, and suspicious links.
- [ ] New members start as Guest/New with limited send access until onboarding completes.
- [ ] Ban / timeout workflows documented for moderators.

## Privacy

- [ ] Do not log or export private channel contents in this package.
- [ ] Points / leaderboard data is participation-oriented; avoid collecting unnecessary PII.
- [ ] Partner promo codes follow partner terms; hub does not claim redemption authority it does not have.

## Phishing and social engineering

- [ ] Official announcements only from designated channels and staff roles.
- [ ] Members warned that staff will never DM asking for tokens, seed phrases, or passwords.
- [ ] Affiliate links only in approved channels; no unsolicited DMs with "claim your reward" links from the bot unless explicitly designed and reviewed.

## Moderator response

- [ ] Escalation path: Moderator → Manager → Admin/Owner.
- [ ] Evidence retention for bans (message IDs, screenshots) follows your policy.
- [ ] `#bug-reports` and `#support` monitored during launch windows.

## Deployment surface

- [ ] Railway volume `/data` backed up or exportable before risky changes.
- [ ] Rollback target: previously verified Railway deployment pin (see `ROLLBACK.md`).
- [ ] X intake remains disabled unless a separate owner-approved task enables it.
- [ ] No merge of this branch to production without owner review of the draft PR.

## Sign-off

| Item | Owner | Date | Status |
|------|-------|------|--------|
| Token rotation | | | |
| Intent confirmation | | | |
| Role permission audit | | | |
| Public invite decision | | | |
| Smoke tests complete | | | |
