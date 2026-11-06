# Target structure (idempotent plan — approval-gated)

Guild ID default: `1566290427366080612` (override via plan config).

## Principles
1. **Preserve** all existing channels, messages, roles, bot installation, and permission overwrites unless an item is explicitly listed as additive.
2. **Never open** private/staff channels to @everyone or Member.
3. **Additive only** by default: create missing public categories/channels; do not delete or rename user-created content.
4. **Coming Soon** channels are member-visible, **read-only** for @everyone/Member, with a pinned label in the channel topic.
5. **One member-visible voice/video channel** per agreed public category.
6. **Start Here** uses Discord **native Rules Screening** (owner enables in Server Settings → Safety). Bot only posts guidance + hub links.

## START HERE
welcome, rules, announcements, how-to-start (hub links), roles-and-interests, support, **start-here-voice**

Hub links (public): `/get-started`, `/hubview`, `/dashboard`, `/hubpanel`; X `https://x-game-intake-production.up.railway.app/auth/x/start?next=%2Fmy-games`; site live-games URL.

## GAMING NETWORK
games-and-events, find-a-game, live-lobbies, tournaments, winners-and-highlights, game-help, **gaming-voice**

## LIVE DASHBOARD
dashboard, giveaways, promo-codes, alerts, leaderboards, rewards-and-points, **dashboard-voice**

## EDUCATION (Coming Soon read-only previews)
education-start, course-library, algo-lab (topics `COMING SOON — …`), education-questions, **education-voice**

## AFFILIATES & PARTNERS
affiliate-help, affiliate-news, affiliate-links, affiliate-reports, **affiliate-voice**  
`manager-controls` stays staff-only — planner will not open it.

## COMMUNITY
general, introductions, suggestions, bug-reports, **community-voice**

## Non-goals
No deletion/rename, no mass permission reset, no private exposure, no paid X, no live apply from Grok.
