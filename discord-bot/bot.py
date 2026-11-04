"""
Discord Hub v2 - clean rewrite.
Reads existing config.json (never overwrites it) and hub_data.json.
Slash commands: /setuphub /hubpanel /code-drop /giveaway /points /leaderboard
                /awardpoints /affiliate /game /feed /dashboard
Local TV dashboard: http://127.0.0.1:8765
Requires discord.py 2.4+ and aiohttp.  Set DISCORD_TOKEN in Terminal first.
"""
import os, json, asyncio, datetime, random
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import web

ROOT = Path(__file__).resolve().parent
# On Railway, settings and data survive deployments on the /data volume.
# Without DATA_DIR, continue to use the original folder (Mac compatibility).
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT))).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = DATA_DIR / "config.json"
DATA_PATH = DATA_DIR / "hub_data.json"
PORT = 8765

DEFAULT_CONFIG = {
    "hub_guild_id": 0, "codes_channel_id": 0, "watch_guild_ids": [], "watch_channel_ids": [],
    "timezone": "America/Chicago", "accent": "#a78bfa",
    "code_keywords": ["code", "promo", "redeem", "coupon"],
    "giveaway_keywords": ["giveaway", "raffle", "drop"],
    "important_keywords": ["giveaway", "payout", "launch", "finale", "closes"],
    "promo_dm_cooldown_hours": 24,
}
if not CONFIG_PATH.exists():
    prior = ROOT / "config.json"
    if prior != CONFIG_PATH and prior.exists():
        CONFIG_PATH.write_bytes(prior.read_bytes())
    else:
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
if not DATA_PATH.exists():
    prior = ROOT / "hub_data.json"
    if prior != DATA_PATH and prior.exists():
        DATA_PATH.write_bytes(prior.read_bytes())
config = json.loads(CONFIG_PATH.read_text())
for k, v in DEFAULT_CONFIG.items():  # in-memory defaults only; file is never rewritten
    config.setdefault(k, v)


# ---------------------------------------------------------------- data
def load_data():
    try:
        d = json.loads(DATA_PATH.read_text())
    except Exception:
        d = {}
    for k, v in {"users": {}, "feed": [], "codes": [], "affiliates": {}, "games": {}, "events": [], "poker": {}, "rewards": [], "redemptions": [], "dashboards": {}}.items():
        d.setdefault(k, v)
    return d

data = load_data()

def save_data():
    DATA_PATH.write_text(json.dumps(data, indent=2))

def user_record(uid):
    return data["users"].setdefault(str(uid), {"server_points": 0, "affiliate_points": {}, "codes_claimed": 0, "games_played": 0})

def add_feed(guild, channel, author, content, kind="message"):
    item = {"time": datetime.datetime.now(datetime.timezone.utc).isoformat(), "guild": guild,
            "channel": channel, "author": author, "content": (content or "")[:500], "kind": kind}
    data["feed"].insert(0, item)
    data["feed"] = data["feed"][:250]
    save_data()


# ---------------------------------------------------------------- bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

def accent_color():
    try:
        return discord.Color(int(config.get("accent", "#a78bfa").replace("#", ""), 16))
    except Exception:
        return discord.Color.from_str("#a78bfa")

def gname(interaction):
    return interaction.guild.name if interaction.guild else "DM"

def cname(interaction):
    return getattr(interaction.channel, "name", "dm")

@bot.event
async def setup_hook():
    asyncio.create_task(start_web())
    bot.add_view(DashboardView())
    for _gid, _g in data.get('poker', {}).items():
        if _g.get('status') == 'open':
            bot.add_view(JoinView(_gid))

@bot.event
async def on_ready():
    print(f"Hub connected as {bot.user} | guild={config.get('hub_guild_id')}")
    print("Servers the bot can see:", ", ".join(f"{g.name} ({g.id})" for g in bot.guilds) or "none")
    try:
        if not refresh_dashboards.is_running():
            refresh_dashboards.start()
    except Exception as e:
        print("Dashboard refresh:", e)
    try:
        export_channel_ids()
        print("Channel IDs saved to channel_ids.txt")
    except Exception as e:
        print("Channel export:", e)
    try:
        gid = int(config.get("hub_guild_id", 0))
        if gid:
            guild = discord.Object(id=gid)
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
            print("Guild commands synced.")
        else:
            await tree.sync()
    except Exception as e:
        print("Command sync:", e)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.guild:
        name = getattr(message.channel, "name", "?")
        add_feed(message.guild.name, name, message.author.display_name, message.content)
        text = message.content.lower()
        if any(k.lower() in text for k in config.get("code_keywords", [])):
            add_feed(message.guild.name, name, message.author.display_name, message.content, "code-watch")
        if any(k.lower() in text for k in config.get("giveaway_keywords", [])):
            add_feed(message.guild.name, name, message.author.display_name, message.content, "giveaway-watch")
    await bot.process_commands(message)


# ---------------------------------------------------------------- slash commands
async def ensure_category(guild, name):
    c = discord.utils.get(guild.categories, name=name)
    return c or await guild.create_category(name, reason="Discord Hub setup")

@tree.command(name="setuphub", description="Create the Discord Hub channel structure")
@app_commands.checks.has_permissions(manage_channels=True)
async def setuphub(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message("Run this inside your server.", ephemeral=True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    groups = {
        "PERSONAL HUB": ["dashboard", "announcements", "calendar", "promo-codes", "giveaways", "alerts", "games-and-events", "code-drops", "rewards-and-points", "affiliate-help"],
        "TRADING": ["trading-alerts", "trade-setups", "watchlist", "trading-journal", "prop-firm-feed"],
        "AFFILIATES & MANAGERS": ["affiliate-news", "affiliate-reports", "manager-controls", "affiliate-links"],
        "EDUCATION": ["education", "algo-lab", "payout-reports", "scaling-vs-payouts"],
        "BOT COMMANDS": ["bot-commands", "suggestions"],
    }
    created, existing = [], []
    for catname, names in groups.items():
        cat = await ensure_category(guild, catname)
        for name in names:
            if discord.utils.get(cat.text_channels, name=name):
                existing.append(name)
            else:
                await guild.create_text_channel(name, category=cat, reason="Discord Hub setup")
                created.append(name)
    try:
        dch = discord.utils.get(guild.text_channels, name="dashboard")
        if dch and not any(r["channel_id"] == dch.id for r in data["dashboards"].values()):
            await post_dashboard(dch)
            created.append("live dashboard post")
    except Exception as e:
        print("Dashboard post:", e)
    await interaction.followup.send(f"**Hub structure ready.**\nCreated: {len(created)} channels\nAlready existed: {len(existing)}\n\nNext: use `/hubpanel` in #bot-commands.", ephemeral=True)

@tree.command(name="hubpanel", description="Post a quick Discord Hub control panel")
async def hubpanel(interaction: discord.Interaction):
    e = discord.Embed(title="✨ DISCORD HUB CONTROL CENTER", description="Games • Codes • Points • Affiliates • Education", color=accent_color())
    e.add_field(name="Member", value="`/points` • `/leaderboard` • `/feed`", inline=False)
    e.add_field(name="Games & codes", value="`/game` • `/code-drop` • `/giveaway`", inline=False)
    e.add_field(name="Affiliate / manager", value="`/aff register|report|stats|join|collab|link|leaderboard` • `/mgr assign|overview|advise|payout` • `/awardpoints`", inline=False)
    e.add_field(name="Dashboard", value=f"Live TV wall at http://127.0.0.1:{PORT} (on the host computer).", inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True)

@tree.command(name="code-drop", description="Publish a partner-approved code drop")
@app_commands.describe(code="Code to publish", details="Eligibility, expiry, and terms")
@app_commands.checks.has_permissions(manage_messages=True)
async def code_drop(interaction: discord.Interaction, code: str, details: str = "Check partner terms"):
    embed = discord.Embed(title="🎁 CODE UNLOCKED", description=f"```{code}```\n{details}", color=accent_color())
    embed.add_field(name="Claim", value="Use the partner's official redemption process.")
    await interaction.response.send_message(embed=embed)
    add_feed(gname(interaction), cname(interaction), "Hub Bot", f"Code drop: {code}", "code")
    data["codes"].insert(0, {"code": code, "details": details, "time": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    data["codes"] = data["codes"][:100]
    save_data()

@tree.command(name="giveaway", description="Post a giveaway announcement (manual winner selection)")
@app_commands.describe(prize="Prize description", ends="End time or date", rules="Entry rules")
@app_commands.checks.has_permissions(manage_messages=True)
async def giveaway(interaction: discord.Interaction, prize: str, ends: str, rules: str = "React 🎉 to enter"):
    e = discord.Embed(title="🎉 GIVEAWAY", description=f"**Prize:** {prize}\n**Ends:** {ends}\n**Rules:** {rules}\n\nWinner selection is manual and transparent.", color=accent_color())
    await interaction.response.send_message(embed=e)
    msg = await interaction.original_response()
    try:
        await msg.add_reaction("🎉")
    except Exception:
        pass
    add_feed(gname(interaction), cname(interaction), "Hub Bot", prize, "giveaway")

@tree.command(name="points", description="View your participation points")
async def points(interaction: discord.Interaction):
    u = user_record(interaction.user.id)
    e = discord.Embed(title="⭐ YOUR HUB POINTS", color=accent_color())
    e.add_field(name="Server-wide", value=f"**{u['server_points']:,}**", inline=True)
    e.add_field(name="Affiliate groups", value=f"**{sum(u['affiliate_points'].values()):,}**", inline=True)
    e.add_field(name="Codes claimed", value=str(u["codes_claimed"]), inline=True)
    await interaction.response.send_message(embed=e, ephemeral=True)

@tree.command(name="awardpoints", description="Award participation points to a member")
@app_commands.checks.has_permissions(manage_roles=True)
@app_commands.describe(member="Member", amount="Points", affiliate="Affiliate group name", reason="Approved activity")
async def awardpoints(interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, 100000], affiliate: str = "general", reason: str = "Participation"):
    u = user_record(member.id)
    u["server_points"] += amount
    u["affiliate_points"][affiliate] = u["affiliate_points"].get(affiliate, 0) + amount
    save_data()
    await interaction.response.send_message(f"⭐ Awarded **{amount}** points to {member.mention} ({affiliate}). Reason: {reason}", ephemeral=True)

@tree.command(name="leaderboard", description="Show top server participation points")
async def leaderboard(interaction: discord.Interaction):
    rows = sorted(data["users"].items(), key=lambda x: x[1].get("server_points", 0), reverse=True)[:10]
    lines = []
    for i, (uid, u) in enumerate(rows, 1):
        member = interaction.guild.get_member(int(uid)) if interaction.guild else None
        lines.append(f"**{i}.** {member.display_name if member else 'Member ' + uid[-4:]} — {u.get('server_points', 0):,} pts")
    e = discord.Embed(title="🏆 HUB LEADERBOARD", description="\n".join(lines) or "No points yet.", color=accent_color())
    await interaction.response.send_message(embed=e)

@tree.command(name="affiliate", description="View or set your affiliate group")
@app_commands.describe(group="Your branded affiliate channel/group")
async def affiliate(interaction: discord.Interaction, group: str):
    u = user_record(interaction.user.id)
    u["affiliate"] = group.lower().replace(" ", "-")
    save_data()
    await interaction.response.send_message(f"Your affiliate group is now **{group}**. Points earned can be attributed to this group.", ephemeral=True)

@tree.command(name="game", description="Start a simple engagement game")
@app_commands.describe(game="Game type", rounds="Number of rounds/questions")
@app_commands.choices(game=[app_commands.Choice(name="Trivia", value="trivia"), app_commands.Choice(name="Number hunt", value="hunt"), app_commands.Choice(name="Quick poll", value="poll")])
async def game(interaction: discord.Interaction, game: str, rounds: app_commands.Range[int, 1, 10] = 1):
    if game == "hunt":
        data["games"][str(interaction.channel_id)] = {"answer": random.randint(1, 20), "host": interaction.user.id}
        save_data()
        await interaction.response.send_message("🔎 **NUMBER HUNT** — Guess a number from 1–20 by replying in chat. Host can award points with `/awardpoints`.")
    elif game == "poll":
        await interaction.response.send_message("🗳️ **QUICK POLL** — React 👍 or 👎 to vote.")
        m = await interaction.original_response()
        await m.add_reaction("👍")
        await m.add_reaction("👎")
    else:
        q = random.choice([("What does EMA stand for?", ""), ("What does R:R mean?", ""), ("What is a code drop?", "")])
        await interaction.response.send_message(f"🧠 **TRIVIA**\n{q[0]}\nHost may award participation points after reviewing responses.")

@tree.command(name="feed", description="Show the latest watched community activity")
@app_commands.describe(count="Number of items (1–10)")
async def feed(interaction: discord.Interaction, count: app_commands.Range[int, 1, 10] = 5):
    e = discord.Embed(title="📺 LIVE COMMUNITY FEED", color=accent_color())
    items = data["feed"][:count]
    if not items:
        e.description = "No activity captured yet."
    for x in items:
        e.add_field(name=f"{x['kind']} • {x['guild']} / #{x['channel']}", value=f"**{x['author']}**: {x['content'][:180] or '—'}", inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True)

@tree.command(name="hubsummary", description="Post a quick text summary")
async def dashboard(interaction: discord.Interaction):
    e = discord.Embed(title="📡 HUB LIVE DASHBOARD", description=f"Captured activity: **{len(data['feed'])}**\nCodes tracked: **{len(data['codes'])}**\nMembers with points: **{len(data['users'])}**", color=accent_color())
    e.add_field(name="Quick actions", value="/feed • /points • /leaderboard • /game • /code-drop", inline=False)
    await interaction.response.send_message(embed=e)


# ---------------------------------------------------------------- affiliate / manager area
def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def aff_key(name):
    return name.strip().lower().replace(" ", "-")

def get_aff(name):
    return data["affiliates"].get(aff_key(name))

def aff_totals(a):
    r = a.get("reports", [])
    return {"sales": sum(x.get("sales", 0) for x in r), "signups": sum(x.get("signups", 0) for x in r),
            "revenue": round(sum(x.get("revenue", 0.0) for x in r), 2), "reports": len(r)}

def is_manager(interaction, a=None):
    perms = interaction.user.guild_permissions if interaction.guild else None
    if perms and (perms.manage_guild or perms.administrator):
        return True
    return bool(a and a.get("manager_id") == interaction.user.id)

def can_edit_aff(interaction, a):
    return a.get("owner_id") == interaction.user.id or is_manager(interaction, a)

aff = app_commands.Group(name="aff", description="Affiliate tools")
mgr = app_commands.Group(name="mgr", description="Affiliate manager tools")

@aff.command(name="register", description="Register your affiliate group")
@app_commands.describe(name="Group / brand name", link="Your affiliate link", terms="Payout terms of the campaign (text)")
async def aff_register(interaction: discord.Interaction, name: str, link: str = "", terms: str = ""):
    k = aff_key(name)
    if k in data["affiliates"]:
        return await interaction.response.send_message("That affiliate name already exists.", ephemeral=True)
    data["affiliates"][k] = {"name": name, "owner_id": interaction.user.id, "owner_name": interaction.user.display_name,
                             "link": link, "terms": terms, "manager_id": None, "manager_name": "", "members": [],
                             "reports": [], "advice": [], "payouts": [], "created": now_iso()}
    save_data()
    await interaction.response.send_message(f"✅ Affiliate **{name}** registered. Add sales with `/aff report`.", ephemeral=True)

@aff.command(name="link", description="Set or show an affiliate link")
async def aff_link(interaction: discord.Interaction, name: str, link: str = ""):
    a = get_aff(name)
    if not a:
        return await interaction.response.send_message("Affiliate not found.", ephemeral=True)
    if link:
        if not can_edit_aff(interaction, a):
            return await interaction.response.send_message("Only the owner or a manager can change the link.", ephemeral=True)
        a["link"] = link
        save_data()
    await interaction.response.send_message(f"🔗 **{a['name']}**: {a.get('link') or 'no link set'}", ephemeral=True)

@aff.command(name="report", description="Log a sales/engagement report for your affiliate group")
@app_commands.describe(name="Affiliate name", sales="Sales count", signups="Signups", revenue="Revenue attributed ($)", notes="Notes")
async def aff_report(interaction: discord.Interaction, name: str, sales: app_commands.Range[int, 0, 1000000] = 0,
                     signups: app_commands.Range[int, 0, 1000000] = 0, revenue: app_commands.Range[float, 0, 100000000] = 0.0, notes: str = ""):
    a = get_aff(name)
    if not a:
        return await interaction.response.send_message("Affiliate not found.", ephemeral=True)
    if not can_edit_aff(interaction, a):
        return await interaction.response.send_message("Only the owner or a manager can log reports.", ephemeral=True)
    a["reports"].insert(0, {"time": now_iso(), "by": interaction.user.display_name, "sales": sales, "signups": signups, "revenue": revenue, "notes": notes[:300]})
    a["reports"] = a["reports"][:200]
    save_data()
    await interaction.response.send_message(f"📈 Report saved for **{a['name']}**.", ephemeral=True)

@aff.command(name="stats", description="View affiliate group stats")
async def aff_stats(interaction: discord.Interaction, name: str):
    a = get_aff(name)
    if not a:
        return await interaction.response.send_message("Affiliate not found.", ephemeral=True)
    t = aff_totals(a)
    e = discord.Embed(title=f"♧ {a['name']}", color=accent_color())
    e.add_field(name="Sales", value=f"{t['sales']:,}")
    e.add_field(name="Signups", value=f"{t['signups']:,}")
    e.add_field(name="Revenue", value=f"${t['revenue']:,.2f}")
    e.add_field(name="Members", value=str(len(a["members"])))
    e.add_field(name="Manager", value=a.get("manager_name") or "unassigned")
    e.add_field(name="Link", value=a.get("link") or "—", inline=False)
    if a.get("terms"):
        e.add_field(name="Payout terms", value=a["terms"][:300], inline=False)
    if a["advice"]:
        e.add_field(name="Latest manager advice", value=a["advice"][0]["text"][:300], inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True)

@aff.command(name="join", description="Join an affiliate group as a follower")
async def aff_join(interaction: discord.Interaction, name: str):
    a = get_aff(name)
    if not a:
        return await interaction.response.send_message("Affiliate not found.", ephemeral=True)
    if interaction.user.id not in a["members"]:
        a["members"].append(interaction.user.id)
    user_record(interaction.user.id)["affiliate"] = aff_key(name)
    save_data()
    await interaction.response.send_message(f"Joined **{a['name']}**. Points you earn can be attributed to this group.", ephemeral=True)

@aff.command(name="collab", description="Post a collab request to other affiliates")
@app_commands.describe(name="Your affiliate", idea="What you want to collaborate on")
async def aff_collab(interaction: discord.Interaction, name: str, idea: str):
    a = get_aff(name)
    if not a or not can_edit_aff(interaction, a):
        return await interaction.response.send_message("Affiliate not found or not yours.", ephemeral=True)
    e = discord.Embed(title=f"🤝 COLLAB REQUEST — {a['name']}", description=idea[:1000], color=accent_color())
    if a.get("link"):
        e.add_field(name="Link", value=a["link"])
    await interaction.response.send_message(embed=e)
    add_feed(gname(interaction), cname(interaction), a["name"], f"Collab: {idea}", "collab")

@aff.command(name="leaderboard", description="Affiliate group ranking by revenue")
async def aff_board(interaction: discord.Interaction):
    rows = sorted(data["affiliates"].values(), key=lambda a: aff_totals(a)["revenue"], reverse=True)[:10]
    lines = [f"**{i}.** {a['name']} — ${aff_totals(a)['revenue']:,.2f} • {aff_totals(a)['sales']} sales" for i, a in enumerate(rows, 1)]
    await interaction.response.send_message(embed=discord.Embed(title="🏆 AFFILIATE LEADERBOARD", description="\n".join(lines) or "No affiliates yet.", color=accent_color()))

@mgr.command(name="assign", description="Assign a manager to an affiliate group")
@app_commands.checks.has_permissions(manage_guild=True)
async def mgr_assign(interaction: discord.Interaction, name: str, manager: discord.Member):
    a = get_aff(name)
    if not a:
        return await interaction.response.send_message("Affiliate not found.", ephemeral=True)
    a["manager_id"], a["manager_name"] = manager.id, manager.display_name
    save_data()
    await interaction.response.send_message(f"{manager.mention} now manages **{a['name']}**.", ephemeral=True)

@mgr.command(name="overview", description="See all affiliates you manage (admins see all)")
async def mgr_overview(interaction: discord.Interaction):
    allm = interaction.guild and (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator)
    mine = [a for a in data["affiliates"].values() if allm or a.get("manager_id") == interaction.user.id]
    e = discord.Embed(title="🧭 MANAGER OVERVIEW", color=accent_color())
    for a in mine[:20]:
        t = aff_totals(a)
        e.add_field(name=a["name"], value=f"${t['revenue']:,.2f} • {t['sales']} sales • {t['signups']} signups • {len(a['members'])} members", inline=False)
    if not mine:
        e.description = "No affiliates assigned to you."
    await interaction.response.send_message(embed=e, ephemeral=True)

@mgr.command(name="advise", description="Leave promotion advice for an affiliate")
async def mgr_advise(interaction: discord.Interaction, name: str, advice: str):
    a = get_aff(name)
    if not a or not is_manager(interaction, a):
        return await interaction.response.send_message("Affiliate not found or you are not its manager.", ephemeral=True)
    a["advice"].insert(0, {"time": now_iso(), "by": interaction.user.display_name, "text": advice[:500]})
    a["advice"] = a["advice"][:50]
    save_data()
    await interaction.response.send_message(f"Advice saved for **{a['name']}**.", ephemeral=True)

@mgr.command(name="payout", description="Record a payout made per the campaign terms (ledger only)")
async def mgr_payout(interaction: discord.Interaction, name: str, amount: app_commands.Range[float, 0, 100000000], note: str = ""):
    a = get_aff(name)
    if not a or not is_manager(interaction, a):
        return await interaction.response.send_message("Affiliate not found or you are not its manager.", ephemeral=True)
    a["payouts"].insert(0, {"time": now_iso(), "by": interaction.user.display_name, "amount": amount, "note": note[:200]})
    save_data()
    await interaction.response.send_message(f"Recorded ${amount:,.2f} payout for **{a['name']}**. (Ledger entry only — no money is moved.)", ephemeral=True)

tree.add_command(aff)
tree.add_command(mgr)


# ---------------------------------------------------------------- channel id tools
def export_channel_ids():
    lines = []
    for g in bot.guilds:
        lines.append(f"# {g.name} ({g.id})")
        for c in g.channels:
            cat = (c.category.name + " / ") if getattr(c, "category", None) else ""
            lines.append(f"{c.id}\t{type(c).__name__}\t{cat}{c.name}")
        lines.append("")
    (ROOT / "channel_ids.txt").write_text("\n".join(lines))

@tree.command(name="channelids", description="List this server's channel IDs (privately)")
@app_commands.checks.has_permissions(manage_guild=True)
async def channelids(interaction: discord.Interaction):
    g = interaction.guild
    if not g:
        return await interaction.response.send_message("Use this inside a server.", ephemeral=True)
    text = f"Server {g.name}: {g.id}\n" + "\n".join(f"{c.id}  #{c.name}" for c in g.text_channels)
    await interaction.response.send_message(f"```\n{text[:1850]}\n```", ephemeral=True)


# ---------------------------------------------------------------- calendar / events
event_grp = app_commands.Group(name="event", description="Community calendar")

@event_grp.command(name="add", description="Add a calendar event")
@app_commands.describe(title="Event name", date="Date as YYYY-MM-DD", time="Time, e.g. 6:00 PM", important="Star it as an important day", where="Channel or place")
@app_commands.checks.has_permissions(manage_messages=True)
async def event_add(interaction: discord.Interaction, title: str, date: str, time: str = "", important: bool = False, where: str = ""):
    try:
        d = datetime.date.fromisoformat(date.strip())
    except ValueError:
        return await interaction.response.send_message("Use the date format YYYY-MM-DD, for example 2026-11-05.", ephemeral=True)
    nid = max([e.get("id", 0) for e in data["events"]] + [0]) + 1
    data["events"].append({"id": nid, "title": title[:100], "date": d.isoformat(), "time": time[:20], "where": where[:60], "important": important})
    save_data()
    await interaction.response.send_message(f"📅 Added **{title}** on {d.isoformat()} (id {nid}){' ⭐' if important else ''}.", ephemeral=True)
    await refresh_all_dashboards()

@event_grp.command(name="list", description="Show upcoming events")
async def event_list(interaction: discord.Interaction):
    today = datetime.date.today().isoformat()
    ups = sorted([e for e in data["events"] if e["date"] >= today], key=lambda e: (e["date"], e.get("time", "")))[:10]
    lines = [f"{'⭐' if e.get('important') else '•'} **{e['date']}** {e.get('time', '')} — {e['title']} {('· ' + e['where']) if e.get('where') else ''} (id {e['id']})" for e in ups]
    await interaction.response.send_message(embed=discord.Embed(title="📅 UPCOMING EVENTS", description="\n".join(lines) or "Nothing scheduled.", color=accent_color()))

@event_grp.command(name="remove", description="Remove an event by id")
@app_commands.checks.has_permissions(manage_messages=True)
async def event_remove(interaction: discord.Interaction, event_id: int):
    before = len(data["events"])
    data["events"] = [e for e in data["events"] if e.get("id") != event_id]
    save_data()
    await interaction.response.send_message("Removed." if len(data["events"]) < before else "No event with that id.", ephemeral=True)
    await refresh_all_dashboards()

tree.add_command(event_grp)


# ---------------------------------------------------------------- poker games (points are participation only, never wagered)
from collections import Counter

RANKS = "23456789TJQKA"
SUITS = "♠♥♦♣"
HAND_NAMES = ["High card", "Pair", "Two pair", "Three of a kind", "Straight", "Flush", "Full house", "Four of a kind", "Straight flush"]

def hand_score(cards):
    vals = sorted((RANKS.index(c[0]) for c in cards), reverse=True)
    groups = sorted(Counter(vals).items(), key=lambda x: (x[1], x[0]), reverse=True)
    ordered = tuple(v for v, _ in groups)
    shape = [c for _, c in groups]
    flush = len({c[1] for c in cards}) == 1
    high = None
    if len(set(vals)) == 5:
        if vals[0] - vals[4] == 4:
            high = vals[0]
        elif vals == [12, 3, 2, 1, 0]:
            high = 3
    if high is not None and flush: return (8, (high,))
    if shape == [4, 1]: return (7, ordered)
    if shape == [3, 2]: return (6, ordered)
    if flush: return (5, tuple(vals))
    if high is not None: return (4, (high,))
    if shape == [3, 1, 1]: return (3, ordered)
    if shape == [2, 2, 1]: return (2, ordered)
    if shape == [2, 1, 1, 1]: return (1, ordered)
    return (0, tuple(vals))

def award_points(uid, amount):
    u = user_record(uid)
    u["server_points"] += amount
    g = u.get("affiliate")
    if g:
        u["affiliate_points"][g] = u["affiliate_points"].get(g, 0) + amount

def join_game(gid, user):
    g = data["poker"].get(str(gid))
    if not g:
        return "Game not found."
    if g["status"] != "open":
        return "That game already started."
    if any(p["id"] == user.id for p in g["players"]):
        return "You're already seated."
    if len(g["players"]) >= g["tables"] * g["seats"]:
        return "All seats are taken."
    g["players"].append({"id": user.id, "name": user.display_name})
    save_data()
    return f"🃏 You're in **{g['title']}** ({len(g['players'])}/{g['tables'] * g['seats']} seats)."

class JoinView(discord.ui.View):
    def __init__(self, gid):
        super().__init__(timeout=None)
        self.gid = str(gid)
        self.children[0].custom_id = f"poker_join:{gid}"

    @discord.ui.button(label="Join a table", style=discord.ButtonStyle.primary, emoji="🃏")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(join_game(self.gid, interaction.user), ephemeral=True)

class CodesModal(discord.ui.Modal, title="Codes to give away"):
    codes = discord.ui.TextInput(label="One code per line (kept private)", style=discord.TextStyle.paragraph, required=False, max_length=2000)

    def __init__(self, gtitle, tables, seats, loss_points):
        super().__init__()
        self.gtitle, self.tables, self.seats, self.loss_points = gtitle, tables, seats, loss_points

    async def on_submit(self, interaction: discord.Interaction):
        gid = str(max([int(k) for k in data["poker"]] + [0]) + 1)
        codes = [c.strip() for c in str(self.codes).splitlines() if c.strip()]
        data["poker"][gid] = {"id": gid, "title": self.gtitle, "tables": self.tables, "seats": self.seats, "loss_points": self.loss_points,
                              "host_id": interaction.user.id, "status": "open", "players": [], "codes": codes, "claims": {}, "results": [], "created": now_iso()}
        save_data()
        e = discord.Embed(title=f"🃏 {self.gtitle.upper()}", color=accent_color(),
                          description=f"**{self.tables} tables × {self.seats} seats**\nWinners of each table claim a code. Everyone else earns **{self.loss_points}** loyalty points.\nPoints are participation rewards only and are never wagered.\n\nPress **Join a table** below (game id **{gid}**).")
        e.add_field(name="Codes available", value=str(len(codes)))
        await interaction.channel.send(embed=e, view=JoinView(gid))
        add_feed(gname(interaction), cname(interaction), "Hub Bot", f"Poker game opened: {self.gtitle}", "game")
        await interaction.response.send_message(f"Game **{gid}** created with {len(codes)} private codes. Run `/poker start game_id:{gid}` when seats fill.", ephemeral=True)

poker = app_commands.Group(name="poker", description="Poker engagement games")

@poker.command(name="create", description="Open a poker game (codes entered privately next)")
@app_commands.describe(title="Game name", tables="Number of tables", seats="Seats per table", loss_points="Loyalty points for non-winners")
@app_commands.checks.has_permissions(manage_messages=True)
async def poker_create(interaction: discord.Interaction, title: str = "Poker night", tables: app_commands.Range[int, 1, 10] = 5,
                       seats: app_commands.Range[int, 2, 10] = 5, loss_points: app_commands.Range[int, 0, 10000] = 10):
    await interaction.response.send_modal(CodesModal(title[:60], tables, seats, loss_points))

@poker.command(name="join", description="Join an open poker game by id")
async def poker_join(interaction: discord.Interaction, game_id: str):
    await interaction.response.send_message(join_game(game_id, interaction.user), ephemeral=True)

@poker.command(name="start", description="Deal and settle all tables")
async def poker_start(interaction: discord.Interaction, game_id: str):
    g = data["poker"].get(str(game_id))
    if not g:
        return await interaction.response.send_message("Game not found.", ephemeral=True)
    if g["host_id"] != interaction.user.id and not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("Only the host or a manager can start it.", ephemeral=True)
    if g["status"] != "open":
        return await interaction.response.send_message("Already started.", ephemeral=True)
    if len(g["players"]) < 2:
        return await interaction.response.send_message("Need at least 2 players.", ephemeral=True)
    rng = random.SystemRandom()
    players = g["players"][:]
    rng.shuffle(players)
    nt = max(1, min(g["tables"], len(players) // 2))
    tables = [[] for _ in range(nt)]
    for i, p in enumerate(players):
        tables[i % nt].append(p)
    codes = g["codes"][:]
    e = discord.Embed(title=f"🏁 {g['title'].upper()} — RESULTS", color=accent_color())
    results = []
    for ti, seats in enumerate(tables, 1):
        deck = [r + sname for r in RANKS for sname in SUITS]
        rng.shuffle(deck)
        hands = {p["id"]: [deck.pop() for _ in range(5)] for p in seats}
        scores = {pid: hand_score(h) for pid, h in hands.items()}
        best = max(scores.values())
        winner = rng.choice([p for p in seats if scores[p["id"]] == best])
        code = codes.pop(0) if codes else None
        if code:
            g["claims"][str(winner["id"])] = {"code": code, "claimed": False}
        for p in seats:
            if p["id"] != winner["id"] or not code:
                award_points(p["id"], g["loss_points"])
        rec = {"table": ti, "winner": winner["name"], "winner_id": winner["id"], "hand": HAND_NAMES[best[0]], "cards": " ".join(hands[winner["id"]]), "seats": [p["name"] for p in seats], "code_awarded": bool(code)}
        results.append(rec)
        e.add_field(name=f"Table {ti}: {winner['name']} wins", value=f"{rec['hand']} — {rec['cards']}\nSeated: {', '.join(rec['seats'])[:300]}\n{'🎁 Code awarded — claim with /poker claim' if code else '⭐ No code left; points awarded'}", inline=False)
    g["results"], g["status"] = results, "finished"
    save_data()
    e.set_footer(text="Winners: /poker claim (private). Everyone else: loyalty points added — check /points.")
    await interaction.response.send_message(embed=e)
    add_feed(gname(interaction), cname(interaction), "Hub Bot", f"Poker finished: {g['title']}", "game")

@poker.command(name="claim", description="Claim any code you won (shown only to you)")
async def poker_claim(interaction: discord.Interaction):
    found = []
    for g in data["poker"].values():
        c = g["claims"].get(str(interaction.user.id))
        if c and not c["claimed"]:
            c["claimed"] = True
            found.append(f"**{g['title']}**: `{c['code']}`")
    if found:
        user_record(interaction.user.id)["codes_claimed"] += len(found)
        save_data()
    await interaction.response.send_message("\n".join(found) if found else "No unclaimed codes for you right now.", ephemeral=True)

@poker.command(name="status", description="Show a game's seats and status")
async def poker_status(interaction: discord.Interaction, game_id: str):
    g = data["poker"].get(str(game_id))
    if not g:
        return await interaction.response.send_message("Game not found.", ephemeral=True)
    await interaction.response.send_message(f"**{g['title']}** — {g['status']} — {len(g['players'])}/{g['tables'] * g['seats']} seats: {', '.join(p['name'] for p in g['players']) or 'empty'}", ephemeral=True)

tree.add_command(poker)


# ---------------------------------------------------------------- rewards shop (spend loyalty points)
rewards_grp = app_commands.Group(name="rewards", description="Spend loyalty points on rewards")

def next_id(items):
    return max([i.get("id", 0) for i in items] + [0]) + 1

def find_reward(rid):
    return next((r for r in data["rewards"] if r["id"] == rid), None)

def find_redemption(rid):
    return next((r for r in data["redemptions"] if r["id"] == rid), None)

async def notify_user(uid, text):
    try:
        user = bot.get_user(uid) or await bot.fetch_user(uid)
        await user.send(text[:1900])
    except Exception:
        pass

@rewards_grp.command(name="list", description="Browse the rewards shop")
async def rewards_list(interaction: discord.Interaction):
    u = user_record(interaction.user.id)
    lines = []
    for r in data["rewards"]:
        if not r.get("active", True):
            continue
        stock = "unlimited" if r.get("stock") is None else f"{r['stock']} left"
        lines.append(f"**#{r['id']} {r['name']}** — {r['cost']:,} pts • {stock}\n{r.get('description', '')}")
    e = discord.Embed(title="🎁 REWARDS SHOP", description="\n\n".join(lines) or "No rewards yet.", color=accent_color())
    e.set_footer(text=f"Your points: {u['server_points']:,} • /rewards redeem reward_id")
    await interaction.response.send_message(embed=e, ephemeral=True)

@rewards_grp.command(name="redeem", description="Spend points on a reward")
async def rewards_redeem(interaction: discord.Interaction, reward_id: int):
    r = find_reward(reward_id)
    if not r or not r.get("active", True):
        return await interaction.response.send_message("Reward not found.", ephemeral=True)
    if r.get("stock") is not None and r["stock"] <= 0:
        return await interaction.response.send_message("That reward is out of stock.", ephemeral=True)
    u = user_record(interaction.user.id)
    if u["server_points"] < r["cost"]:
        return await interaction.response.send_message(f"You need {r['cost']:,} points; you have {u['server_points']:,}.", ephemeral=True)
    u["server_points"] -= r["cost"]
    if r.get("stock") is not None:
        r["stock"] -= 1
    rec = {"id": next_id(data["redemptions"]), "user_id": interaction.user.id, "user_name": interaction.user.display_name,
           "reward_id": r["id"], "reward_name": r["name"], "cost": r["cost"], "status": "pending", "time": now_iso(), "note": ""}
    data["redemptions"].insert(0, rec)
    save_data()
    add_feed(gname(interaction), cname(interaction), interaction.user.display_name, f"Requested reward: {r['name']}", "reward")
    await interaction.response.send_message(f"✅ Requested **{r['name']}** for {r['cost']:,} points (request #{rec['id']}). A manager will review it; you'll get a DM when it's decided.", ephemeral=True)

@rewards_grp.command(name="mine", description="See your reward requests")
async def rewards_mine(interaction: discord.Interaction):
    mine = [x for x in data["redemptions"] if x["user_id"] == interaction.user.id][:10]
    lines = [f"#{x['id']} **{x['reward_name']}** — {x['status']}" for x in mine]
    await interaction.response.send_message("\n".join(lines) or "No requests yet.", ephemeral=True)

@rewards_grp.command(name="add", description="Add a reward to the shop")
@app_commands.describe(name="Reward name", cost="Points cost", description="What the member gets", stock="How many available (-1 = unlimited)")
@app_commands.checks.has_permissions(manage_guild=True)
async def rewards_add(interaction: discord.Interaction, name: str, cost: app_commands.Range[int, 1, 10000000], description: str = "",
                      stock: app_commands.Range[int, -1, 1000000] = -1):
    r = {"id": next_id(data["rewards"]), "name": name[:80], "cost": cost, "description": description[:200], "stock": None if stock < 0 else stock, "active": True}
    data["rewards"].append(r)
    save_data()
    await interaction.response.send_message(f"Added reward **#{r['id']} {r['name']}** ({cost:,} pts).", ephemeral=True)

@rewards_grp.command(name="remove", description="Remove a reward from the shop")
@app_commands.checks.has_permissions(manage_guild=True)
async def rewards_remove(interaction: discord.Interaction, reward_id: int):
    r = find_reward(reward_id)
    if not r:
        return await interaction.response.send_message("Reward not found.", ephemeral=True)
    r["active"] = False
    save_data()
    await interaction.response.send_message(f"Removed **{r['name']}** from the shop.", ephemeral=True)

@rewards_grp.command(name="queue", description="See pending reward requests")
@app_commands.checks.has_permissions(manage_guild=True)
async def rewards_queue(interaction: discord.Interaction):
    pend = [x for x in data["redemptions"] if x["status"] == "pending"][:20]
    e = discord.Embed(title="📥 PENDING REWARD REQUESTS", color=accent_color())
    for x in pend:
        e.add_field(name=f"#{x['id']} {x['reward_name']}", value=f"{x['user_name']} • {x['cost']:,} pts", inline=False)
    if not pend:
        e.description = "Nothing pending."
    await interaction.response.send_message(embed=e, ephemeral=True)

@rewards_grp.command(name="approve", description="Approve a request and send the member a note (code, link, etc.)")
@app_commands.checks.has_permissions(manage_guild=True)
async def rewards_approve(interaction: discord.Interaction, request_id: int, note: str = ""):
    x = find_redemption(request_id)
    if not x or x["status"] != "pending":
        return await interaction.response.send_message("No pending request with that id.", ephemeral=True)
    x["status"], x["note"] = "approved", note[:500]
    save_data()
    await notify_user(x["user_id"], f"🎁 Your reward **{x['reward_name']}** was approved!" + (f"\n{note}" if note else ""))
    await interaction.response.send_message(f"Approved #{x['id']} for {x['user_name']}. They were sent a DM (if their DMs are open).", ephemeral=True)

@rewards_grp.command(name="deny", description="Deny a request and refund the points")
@app_commands.checks.has_permissions(manage_guild=True)
async def rewards_deny(interaction: discord.Interaction, request_id: int, reason: str = ""):
    x = find_redemption(request_id)
    if not x or x["status"] != "pending":
        return await interaction.response.send_message("No pending request with that id.", ephemeral=True)
    x["status"], x["note"] = "denied", reason[:500]
    user_record(x["user_id"])["server_points"] += x["cost"]
    r = find_reward(x["reward_id"])
    if r and r.get("stock") is not None:
        r["stock"] += 1
    save_data()
    await notify_user(x["user_id"], f"Your reward request **{x['reward_name']}** was not approved; {x['cost']:,} points were refunded." + (f"\nReason: {reason}" if reason else ""))
    await interaction.response.send_message(f"Denied #{x['id']} and refunded {x['cost']:,} points.", ephemeral=True)

tree.add_command(rewards_grp)


# ---------------------------------------------------------------- live dashboard INSIDE Discord (images that refresh themselves)
import math
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from discord.ext import tasks

BG = (10, 10, 20); CARD = (24, 22, 42); CELL = (36, 32, 64); TXT = (240, 238, 255)
MUTED = (150, 146, 185); GOLD = (255, 196, 92); PURPLE = (167, 139, 250); BLUE = (110, 168, 255); LINE = (60, 52, 100)
_fonts = {}

def font(size, bold=False):
    key = (size, bold)
    if key in _fonts:
        return _fonts[key]
    cands = (["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"]
             if bold else ["/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf"])
    f = None
    for c in cands:
        try:
            f = ImageFont.truetype(c, size)
            break
        except Exception:
            pass
    if f is None:
        try:
            f = ImageFont.load_default(size)
        except TypeError:
            f = ImageFont.load_default()
    _fonts[key] = f
    return f

def _canvas(w=1200, h=700):
    img = Image.new("RGB", (w, h), BG)
    return img, ImageDraw.Draw(img)

def _card(d, box):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=26, fill=CARD)
    n = x1 - x0 - 40
    for i in range(n):
        t = i / max(1, n - 1)
        c = tuple(int(PURPLE[k] * (1 - t) + BLUE[k] * t) for k in range(3))
        d.line([(x0 + 20 + i, y0 + 2), (x0 + 20 + i, y0 + 5)], fill=c)

def _star(d, cx, cy, r, color):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    d.polygon(pts, fill=color)

def fit(d, text, f, maxw):
    text = str(text)
    if d.textlength(text, font=f) <= maxw:
        return text
    while text and d.textlength(text + "…", font=f) > maxw:
        text = text[:-1]
    return text + "…"

def _png(img):
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

def name_of(uid):
    try:
        u = bot.get_user(int(uid))
        if u:
            return getattr(u, "display_name", None) or u.name
    except Exception:
        pass
    return f"Member {str(uid)[-4:]}"

def render_calendar():
    W, H = 1500, 960
    img, d = _canvas(W, H)
    _card(d, (24, 24, 930, H - 24)); _card(d, (958, 24, W - 24, H - 24))
    today = datetime.date.today()
    start = today - datetime.timedelta(days=(today.weekday() + 1) % 7)
    by = {}
    for e in data["events"]:
        by.setdefault(e["date"], []).append(e)
    d.text((60, 50), today.strftime("%B %Y"), font=font(64, True), fill=TXT)
    t = "Next 5 weeks"
    d.text((894 - d.textlength(t, font=font(26)), 78), t, font=font(26), fill=MUTED)
    gx, gy, cw, ch, gap = 50, 200, 115, 126, 10
    for i, nm in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]):
        w = d.textlength(nm, font=font(22, True))
        d.text((gx + i * (cw + gap) + (cw - w) / 2, 158), nm, font=font(22, True), fill=MUTED)
    for i in range(35):
        day = start + datetime.timedelta(days=i)
        r, c = divmod(i, 7)
        x, y = gx + c * (cw + gap), gy + r * (ch + gap)
        es = by.get(day.isoformat(), [])
        imp = any(e.get("important") for e in es)
        d.rounded_rectangle((x, y, x + cw, y + ch), radius=18, fill=CELL, outline=GOLD if imp else None, width=3)
        label = (day.strftime("%b ") + str(day.day)) if day.day == 1 else str(day.day)
        col = BLUE if day == today else (MUTED if day < today else TXT)
        d.text((x + 14, y + 10), label, font=font(32, True), fill=col)
        if imp:
            _star(d, x + cw - 24, y + 28, 13, GOLD)
        for k, e in enumerate(es[:4]):
            cx, cy = x + 22 + k * 22, y + ch - 24
            d.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=GOLD if e.get("important") else PURPLE)
    rx = 992
    d.text((rx, 50), "This week", font=font(46, True), fill=TXT)
    srt = lambda e: (e["date"], e.get("time", ""))
    end = today + datetime.timedelta(days=7)
    wk = sorted([e for e in data["events"] if today.isoformat() <= e["date"] <= end.isoformat()], key=srt)[:5]
    y = 130
    for e in wk:
        imp = e.get("important")
        dt = datetime.date.fromisoformat(e["date"])
        d.text((rx, y), dt.strftime("%a %b %d").upper(), font=font(20, True), fill=GOLD if imp else PURPLE)
        d.text((rx, y + 26), fit(d, e["title"], font(30, True), 400), font=font(30, True), fill=TXT)
        sub = " · ".join(x for x in [e.get("time", ""), e.get("where", "")] if x)
        d.text((rx, y + 66), fit(d, sub, font(22), 430), font=font(22), fill=MUTED)
        if imp:
            _star(d, W - 56, y + 46, 14, GOLD)
        d.line([(rx, y + 102), (W - 56, y + 102)], fill=LINE, width=1)
        y += 112
    if not wk:
        d.text((rx, 140), "Nothing scheduled this week.", font=font(24), fill=MUTED)
        d.text((rx, 176), "Add one with /event add", font=font(20), fill=MUTED)
    d.text((rx, 716), "Important days", font=font(34, True), fill=GOLD)
    imps = sorted([e for e in data["events"] if e.get("important") and e["date"] >= today.isoformat()], key=srt)[:3]
    yy = 772
    for e in imps:
        dt = datetime.date.fromisoformat(e["date"])
        _star(d, rx + 10, yy + 14, 11, GOLD)
        d.text((rx + 34, yy), fit(d, dt.strftime("%b %d").upper() + "  " + e["title"], font(24, True), 410), font=font(24, True), fill=TXT)
        yy += 46
    if not imps:
        d.text((rx, 776), "None starred yet", font=font(22), fill=MUTED)
    return _png(img)

def render_board():
    img, d = _canvas()
    _card(d, (24, 24, 745, 676)); _card(d, (768, 24, 1176, 676))
    d.text((52, 44), "Top members", font=font(36, True), fill=TXT)
    d.text((52, 92), "Loyalty points", font=font(17), fill=MUTED)
    rows = sorted(data["users"].items(), key=lambda x: x[1].get("server_points", 0), reverse=True)[:8]
    top = max([u.get("server_points", 0) for _, u in rows] + [1])
    y = 130
    for i, (uid, u) in enumerate(rows, 1):
        pts = u.get("server_points", 0)
        d.ellipse((52, y + 4, 88, y + 40), fill=GOLD if i == 1 else CELL)
        d.text((70 - d.textlength(str(i), font=font(18, True)) / 2, y + 12), str(i), font=font(18, True), fill=(10, 10, 20) if i == 1 else TXT)
        d.text((104, y + 2), fit(d, name_of(uid), font(22, True), 360), font=font(22, True), fill=TXT)
        ps = f"{pts:,} pts"
        d.text((720 - d.textlength(ps, font=font(20, True)), y + 4), ps, font=font(20, True), fill=GOLD)
        d.rounded_rectangle((104, y + 38, 720, y + 46), radius=4, fill=CELL)
        d.rounded_rectangle((104, y + 38, 104 + max(8, int(616 * pts / top)), y + 46), radius=4, fill=PURPLE)
        y += 66
    if not rows:
        d.text((52, 140), "No points yet. Play games and join events!", font=font(20), fill=MUTED)
    d.text((796, 44), "Affiliates", font=font(32, True), fill=TXT)
    affs = sorted(data["affiliates"].values(), key=lambda a: aff_totals(a)["revenue"], reverse=True)[:5]
    y = 100
    for a in affs:
        t = aff_totals(a)
        d.text((796, y), fit(d, a["name"], font(21, True), 250), font=font(21, True), fill=TXT)
        rv = f"${t['revenue']:,.0f}"
        d.text((1148 - d.textlength(rv, font=font(21, True)), y), rv, font=font(21, True), fill=GOLD)
        d.text((796, y + 28), f"{t['sales']} sales · {len(a['members'])} members", font=font(15), fill=MUTED)
        d.line([(796, y + 54), (1148, y + 54)], fill=LINE, width=1)
        y += 64
    if not affs:
        d.text((796, 104), "No affiliates yet. /aff register", font=font(17), fill=MUTED)
    pend = sum(1 for x in data["redemptions"] if x["status"] == "pending")
    tiles = [("Members", str(len(data["users"]))), ("Points issued", f"{sum(u.get('server_points', 0) for u in data['users'].values()):,}"), ("Pending rewards", str(pend))]
    for i, (lab, val) in enumerate(tiles):
        x = 796 + i * 120
        d.rounded_rectangle((x, 560, x + 110, 650), radius=14, fill=CELL)
        d.text((x + 10, 572), val, font=font(24, True), fill=GOLD)
        d.text((x + 10, 614), lab, font=font(12), fill=MUTED)
    return _png(img)

def render_rewards():
    img, d = _canvas()
    _card(d, (24, 24, 1176, 676))
    d.text((52, 44), "Rewards shop", font=font(40, True), fill=TXT)
    d.text((52, 98), "Spend loyalty points with /rewards redeem reward_id", font=font(18), fill=MUTED)
    items = [r for r in data["rewards"] if r.get("active", True)][:8]
    for i, r in enumerate(items):
        col, row = i % 2, i // 2
        x, y = 52 + col * 560, 150 + row * 124
        d.rounded_rectangle((x, y, x + 540, y + 108), radius=16, fill=CELL)
        d.text((x + 20, y + 14), f"#{r['id']}", font=font(16, True), fill=GOLD)
        d.text((x + 20, y + 38), fit(d, r["name"], font(24, True), 360), font=font(24, True), fill=TXT)
        stock = "unlimited" if r.get("stock") is None else f"{r['stock']} left"
        d.text((x + 20, y + 78), stock, font=font(15), fill=MUTED)
        cost = f"{r['cost']:,} pts"
        d.text((x + 520 - d.textlength(cost, font=font(26, True)), y + 38), cost, font=font(26, True), fill=PURPLE)
    if not items:
        d.text((52, 160), "No rewards yet. Managers: /rewards add", font=font(22), fill=MUTED)
    pend = sum(1 for x in data["redemptions"] if x["status"] == "pending")
    d.text((52, 630), f"{pend} request(s) waiting for approval", font=font(16), fill=GOLD if pend else MUTED)
    return _png(img)

def render_me(user):
    img, d = _canvas(900, 400)
    _card(d, (24, 24, 876, 376))
    u = user_record(user.id)
    ranked = sorted(data["users"].items(), key=lambda x: x[1].get("server_points", 0), reverse=True)
    rank = next((i for i, (k, _) in enumerate(ranked, 1) if k == str(user.id)), len(ranked))
    d.text((52, 44), fit(d, user.display_name, font(36, True), 560), font=font(36, True), fill=TXT)
    d.text((52, 94), f"Rank #{rank} of {len(ranked)}", font=font(20), fill=MUTED)
    g = u.get("affiliate") or "none"
    pend = sum(1 for x in data["redemptions"] if x["user_id"] == user.id and x["status"] == "pending")
    tiles = [("Server points", f"{u['server_points']:,}"), ("Affiliate group", fit(d, g, font(26, True), 190)),
             ("Group points", f"{u['affiliate_points'].get(g, 0):,}"), ("Codes claimed", str(u["codes_claimed"]))]
    for i, (lab, val) in enumerate(tiles):
        x = 52 + i * 204
        d.rounded_rectangle((x, 160, x + 192, 280), radius=16, fill=CELL)
        d.text((x + 16, 184), val, font=font(26, True), fill=GOLD)
        d.text((x + 16, 238), lab, font=font(15), fill=MUTED)
    d.text((52, 310), f"{pend} reward request(s) pending", font=font(17), fill=MUTED)
    return _png(img)

PANELS = {"calendar": render_calendar, "board": render_board, "rewards": render_rewards}

def panel_file(panel):
    return discord.File(PANELS[panel](), filename=f"{panel}.png")

def upcoming_events(limit=25):
    today = datetime.date.today().isoformat()
    return sorted([e for e in data["events"] if e["date"] >= today], key=lambda e: (e["date"], e.get("time", "")))[:limit]

def event_embed(e):
    emb = discord.Embed(title=("⭐ " if e.get("important") else "") + e["title"], color=accent_color())
    emb.add_field(name="When", value=f"{e['date']} {e.get('time', '')}".strip())
    if e.get("where"):
        emb.add_field(name="Where", value=e["where"])
    emb.add_field(name="Going", value=str(len(e.get("going", []))))
    return emb

class EventView(discord.ui.View):
    def __init__(self, eid, uid):
        super().__init__(timeout=300)
        self.eid = eid
        e = next((x for x in data["events"] if x["id"] == eid), None)
        if e and uid in e.get("going", []):
            self.going.label = "Cancel RSVP"

    @discord.ui.button(label="I'm going", emoji="✅", style=discord.ButtonStyle.success)
    async def going(self, interaction: discord.Interaction, button: discord.ui.Button):
        e = next((x for x in data["events"] if x["id"] == self.eid), None)
        if not e:
            return await interaction.response.edit_message(content="That event was removed.", embed=None, view=None)
        g = e.setdefault("going", [])
        if interaction.user.id in g:
            g.remove(interaction.user.id)
            button.label = "I'm going"
        else:
            g.append(interaction.user.id)
            button.label = "Cancel RSVP"
        save_data()
        await interaction.response.edit_message(embed=event_embed(e), view=self)

class AddEventModal(discord.ui.Modal, title="Add calendar event"):
    etitle = discord.ui.TextInput(label="Title", max_length=100)
    edate = discord.ui.TextInput(label="Date (YYYY-MM-DD)", max_length=10, placeholder="2026-11-05")
    etime = discord.ui.TextInput(label="Time (optional)", required=False, max_length=20, placeholder="6:00 PM")
    ewhere = discord.ui.TextInput(label="Where (optional)", required=False, max_length=60)
    eimp = discord.ui.TextInput(label="Important? type yes to star it", required=False, max_length=3)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            d = datetime.date.fromisoformat(str(self.edate).strip())
        except ValueError:
            return await interaction.response.send_message("Use the date format YYYY-MM-DD, for example 2026-11-05.", ephemeral=True)
        nid = max([e.get("id", 0) for e in data["events"]] + [0]) + 1
        data["events"].append({"id": nid, "title": str(self.etitle)[:100], "date": d.isoformat(), "time": str(self.etime)[:20],
                               "where": str(self.ewhere)[:60], "important": str(self.eimp).strip().lower() in ("y", "yes"), "going": []})
        save_data()
        await interaction.response.send_message(f"📅 Added **{self.etitle}** on {d.isoformat()}. The calendar updates in a few seconds.", ephemeral=True)
        await refresh_all_dashboards()

class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        opts = [discord.SelectOption(label=e["title"][:100], value=str(e["id"]),
                                     description=f"{e['date']} {e.get('time', '')} {e.get('where', '')}".strip()[:100],
                                     emoji="⭐" if e.get("important") else "📅") for e in upcoming_events()]
        if not opts:
            opts = [discord.SelectOption(label="No events yet. Managers: press Add event", value="0")]
        sel = discord.ui.Select(placeholder="Select an event for details / RSVP…", options=opts, custom_id="dash:event", row=1)
        sel.callback = self.on_pick
        self.add_item(sel)

    async def on_pick(self, interaction: discord.Interaction):
        v = int(interaction.data["values"][0])
        e = next((x for x in data["events"] if x["id"] == v), None)
        if not e:
            return await interaction.response.send_message("No event selected or it was removed.", ephemeral=True)
        await interaction.response.send_message(embed=event_embed(e), view=EventView(v, interaction.user.id), ephemeral=True)

    async def _show(self, interaction, panel):
        await interaction.response.defer()
        await interaction.edit_original_response(attachments=[panel_file(panel)], view=DashboardView())
        rec = data["dashboards"].get(str(interaction.message.id))
        if rec:
            rec["panel"] = panel
            save_data()

    @discord.ui.button(label="Calendar", emoji="📅", style=discord.ButtonStyle.primary, custom_id="dash:calendar", row=0)
    async def b_cal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._show(interaction, "calendar")

    @discord.ui.button(label="Leaderboard", emoji="🏆", style=discord.ButtonStyle.primary, custom_id="dash:board", row=0)
    async def b_board(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._show(interaction, "board")

    @discord.ui.button(label="Rewards", emoji="🎁", style=discord.ButtonStyle.primary, custom_id="dash:rewards", row=0)
    async def b_rewards(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._show(interaction, "rewards")

    @discord.ui.button(label="My standing", emoji="⭐", style=discord.ButtonStyle.secondary, custom_id="dash:me", row=0)
    async def b_me(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(file=discord.File(render_me(interaction.user), filename="me.png"), ephemeral=True)

    @discord.ui.button(label="Add event", emoji="➕", style=discord.ButtonStyle.secondary, custom_id="dash:add", row=0)
    async def b_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (interaction.guild and interaction.user.guild_permissions.manage_messages):
            return await interaction.response.send_message("Only managers can add events.", ephemeral=True)
        await interaction.response.send_modal(AddEventModal())

async def post_dashboard(channel, panel="calendar"):
    msg = await channel.send(file=panel_file(panel), view=DashboardView())
    data["dashboards"][str(msg.id)] = {"channel_id": channel.id, "panel": panel}
    save_data()
    return msg

@tree.command(name="dashboard", description="Post the live dashboard in this channel (refreshes itself)")
@app_commands.checks.has_permissions(manage_guild=True)
async def dashboard_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        await post_dashboard(interaction.channel)
    except discord.Forbidden:
        return await interaction.followup.send("I need Send Messages and Attach Files permission in this channel.", ephemeral=True)
    await interaction.followup.send("Dashboard posted. It refreshes itself every minute, and the buttons switch panels.", ephemeral=True)

async def refresh_all_dashboards():
    for mid, rec in list(data["dashboards"].items()):
        try:
            ch = bot.get_channel(rec["channel_id"]) or await bot.fetch_channel(rec["channel_id"])
            msg = await ch.fetch_message(int(mid))
            await msg.edit(attachments=[panel_file(rec.get("panel", "calendar"))], view=DashboardView())
        except discord.NotFound:
            data["dashboards"].pop(mid, None)
            save_data()
        except Exception as ex:
            print("Dashboard refresh error:", ex)

@tasks.loop(minutes=1)
async def refresh_dashboards():
    await refresh_all_dashboards()

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    msg = "You don't have permission for that." if isinstance(error, app_commands.MissingPermissions) else f"Error: {error}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


# ---------------------------------------------------------------- web dashboard API
def jerr(msg, status=400):
    return web.json_response({"error": msg}, status=status)

async def index(request):
    return web.Response(text=HTML, content_type="text/html")

async def api_feed(request):
    return web.json_response(data["feed"][:100])

async def api_stats(request):
    return web.json_response({"users": len(data["users"]), "codes": len(data["codes"]), "feed": len(data["feed"])})

async def api_affiliates(request):
    out = []
    for a in data["affiliates"].values():
        t = aff_totals(a)
        out.append({"name": a["name"], "owner": a.get("owner_name", ""), "manager": a.get("manager_name", ""), "link": a.get("link", ""),
                    "members": len(a["members"]), "paid": round(sum(p["amount"] for p in a["payouts"]), 2),
                    "advice": a["advice"][0]["text"] if a["advice"] else "", **t})
    out.sort(key=lambda x: x["revenue"], reverse=True)
    return web.json_response(out)

async def api_servers(request):
    return web.json_response([{"id": str(g.id), "name": g.name} for g in bot.guilds])

def chan_list(guild):
    return [{"id": str(c.id), "name": c.name, "category": c.category.name if c.category else "",
             "guild_id": str(guild.id), "guild_name": guild.name}
            for c in guild.text_channels if c.permissions_for(guild.me).view_channel]

async def api_events(request):
    return web.json_response(sorted(data["events"], key=lambda e: (e["date"], e.get("time", ""))))

async def api_rewards(request):
    shop = [{"id": r["id"], "name": r["name"], "cost": r["cost"], "stock": r.get("stock")} for r in data["rewards"] if r.get("active", True)]
    recent = [{"user": x["user_name"], "reward": x["reward_name"], "status": x["status"]} for x in data["redemptions"][:6]]
    return web.json_response({"shop": shop, "pending": sum(1 for x in data["redemptions"] if x["status"] == "pending"), "recent": recent})

async def api_games(request):
    out = []
    for g in data["poker"].values():
        out.append({"id": g["id"], "title": g["title"], "status": g["status"], "players": len(g["players"]), "seats": g["tables"] * g["seats"],
                    "winners": [{"name": r["winner"], "hand": r["hand"]} for r in g["results"]]})
    return web.json_response(out[::-1])

async def api_channels(request):
    if request.query.get("guild") == "all":
        out = []
        for g in bot.guilds:
            out += chan_list(g)
        return web.json_response(out)
    raw = request.query.get("guild") or config.get("hub_guild_id") or (bot.guilds[0].id if bot.guilds else 0)
    try:
        guild = bot.get_guild(int(raw))
    except (TypeError, ValueError):
        guild = None
    if not guild and bot.guilds:
        guild = bot.guilds[0]
    if not guild:
        return jerr("Bot is not in any server yet.", 404)
    out = []
    for c in guild.text_channels:
        if c.permissions_for(guild.me).view_channel:
            out.append({"id": str(c.id), "name": c.name, "category": c.category.name if c.category else "",
                        "guild_id": str(guild.id), "guild_name": guild.name})
    return web.json_response(out)

async def api_chat(request):
    try:
        channel = bot.get_channel(int(request.query.get("channel") or request.query.get("channel_id") or 0))
    except ValueError:
        return jerr("Invalid channel id.")
    if not channel:
        return jerr("Channel not found (is the bot in that server?).", 404)
    try:
        msgs = []
        async for m in channel.history(limit=25):
            content = m.content or ""
            if m.attachments:
                content += "\n" + "\n".join(a.url for a in m.attachments)
            if not content and m.embeds:
                content = "[embed] " + (m.embeds[0].title or m.embeds[0].description or "")[:200]
            msgs.append({"id": str(m.id), "author": m.author.display_name, "content": content, "time": m.created_at.isoformat()})
        msgs.reverse()
        return web.json_response(msgs)
    except discord.Forbidden:
        return jerr("Bot lacks Read Message History permission here.", 403)
    except Exception as e:
        return jerr(str(e), 500)

async def api_send(request):
    try:
        body = await request.json()
        channel = bot.get_channel(int(body.get("channel") or body.get("channel_id") or 0))
    except Exception:
        return jerr("Bad request.")
    if not channel:
        return jerr("Channel not found.", 404)
    content = (body.get("content") or "").strip()
    if not content:
        return jerr("Message is empty.")
    try:
        await channel.send(content[:2000])
        return web.json_response({"ok": True})
    except discord.Forbidden:
        return jerr("Bot lacks Send Messages permission here.", 403)
    except Exception as e:
        return jerr(str(e), 500)

async def start_web():
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/api/feed", api_feed)
    app.router.add_get("/api/stats", api_stats)
    app.router.add_get("/api/servers", api_servers)
    app.router.add_get("/api/events", api_events)
    app.router.add_get("/api/games", api_games)
    app.router.add_get("/api/rewards", api_rewards)
    app.router.add_get("/api/affiliates", api_affiliates)
    app.router.add_get("/api/channels", api_channels)
    app.router.add_get("/api/chat", api_chat)
    app.router.add_post("/api/send", api_send)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", PORT).start()
    print(f"Local dashboard: http://127.0.0.1:{PORT}")


# ---------------------------------------------------------------- dashboard page
HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Discord Hub TV</title>
<style>
:root{--bg:#080811;--purple:#a78bfa;--gold:#f6c453;--text:#f5f3ff;--muted:#9693b5;--line:#292744;--green:#59e6a5}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at top,#1b1234,#080811 62%);color:var(--text);font:14px/1.45 system-ui,Arial}
button,input,select{font:inherit}button{cursor:pointer}
.app{display:grid;grid-template-columns:200px minmax(0,1fr);min-height:100vh}
aside{background:#0c0c19;border-right:1px solid var(--line);padding:20px 12px;position:sticky;top:0;height:100vh}
.brand{font-size:19px;font-weight:900;letter-spacing:1px;padding:0 10px 25px}.brand span{color:var(--purple)}
.nav button{width:100%;text-align:left;background:transparent;color:#c9c6e4;border:0;padding:11px;border-radius:9px;margin:2px 0}
.nav button:hover,.nav button.active{background:#211b3b;color:white}
main{min-width:0;padding:24px clamp(12px,3vw,40px);max-width:1900px;width:100%;margin:auto}
.top,.sectionhead{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.top{margin-bottom:22px}
h1{font-size:24px;margin:0}h1 small{font-size:12px;color:var(--green);margin-left:9px}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.btn,select,input{background:#19192d;color:white;border:1px solid var(--line);padding:9px 12px;border-radius:8px}
.btn.primary{background:var(--purple);color:#090914;font-weight:800}.btn.active{background:var(--purple);color:#090914}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.stat,.card{background:linear-gradient(145deg,#151528,#10101d);border:1px solid var(--line);border-radius:13px}
.stat{padding:15px}.stat label{color:var(--muted);font-size:12px}.stat strong{display:block;font-size:24px;margin-top:7px;color:var(--gold)}
.sectionhead{margin:25px 0 12px}.sectionhead h2{font-size:15px;margin:0}
.wall{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px;margin-top:13px}
.wall.one{grid-template-columns:1fr}.wall.eight{grid-template-columns:repeat(4,minmax(0,1fr))}
.tile{min-width:0;overflow:hidden;display:flex;flex-direction:column;min-height:350px}
.tilehead{display:flex;justify-content:space-between;gap:8px;padding:13px;border-bottom:1px solid var(--line)}
.channelname{font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.channelname span{color:var(--purple)}
.tiletools{display:flex;gap:6px}.tiletools button{background:#211c3b;border:1px solid var(--line);color:#ddd;border-radius:7px}
.messages{height:270px;overflow:auto;padding:12px;background:#090911}
.msg{padding:8px 0;border-bottom:1px solid #1e1d30;overflow-wrap:anywhere;white-space:pre-wrap}.msg b{color:var(--gold)}.msg small{color:var(--muted);font-size:10px;margin-left:7px}
.empty,.notice{color:var(--muted);padding:18px;text-align:center}
.send{display:flex;gap:7px;padding:10px;border-top:1px solid var(--line)}.send input{flex:1;width:0;background:#090911}
.send button{background:var(--purple);color:#080811;border:0;border-radius:8px;padding:0 13px;font-weight:800}
.lower{display:grid;grid-template-columns:1.5fr 1fr;gap:13px;margin-top:15px}.card.pad{padding:15px}.card h3{font-size:13px;margin:0 0 12px}
.ticker{overflow:auto;white-space:nowrap;color:var(--gold);padding:10px 0}.ticker span{display:inline-block;margin-right:30px}
.feeditem{padding:9px 0;border-bottom:1px solid var(--line);overflow-wrap:anywhere}.feeditem small{display:block;color:var(--muted);margin-top:4px}
@media(max-width:1000px){.app{grid-template-columns:1fr}aside{position:static;height:auto}.stats{grid-template-columns:repeat(2,1fr)}.wall.eight{grid-template-columns:repeat(2,1fr)}.lower{grid-template-columns:1fr}}
@media(max-width:650px){.wall,.wall.eight{grid-template-columns:1fr}}
.calwrap{display:grid;grid-template-columns:1.5fr 1fr;gap:13px;margin-top:15px}
.dow{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;color:#9693b5;font-size:11px;margin:10px 0 6px;text-align:center}
#calGrid{display:grid;grid-template-columns:repeat(7,1fr);gap:6px}
.day{background:#1c1b33;border-radius:9px;min-height:54px;padding:6px;position:relative;font-weight:700;font-size:12px;color:#d8d5f0}
.day.imp{outline:1px solid #f6c453}.day.today span{color:#6ea8ff}.day i{position:absolute;right:6px;top:4px;color:#f6c453;font-style:normal}
.dots{display:flex;gap:3px;margin-top:6px}.dots b{width:7px;height:7px;border-radius:50%;background:#a78bfa}.dots b.g{background:#f6c453}
.ev{padding:8px 0;border-bottom:1px solid #292744}.ev small{color:#9693b5;display:block}.ev.imp b{color:#f6c453}
@media(max-width:1000px){.calwrap{grid-template-columns:1fr}}
</style></head><body>
<div class="app"><aside><div class="brand">DISCORD <span>HUB</span></div><nav class="nav">
<button class="active" data-view="dashboard">◈ Dashboard</button><button data-view="trading">↗ Trading</button><button data-view="giveaways">🎁 Giveaways</button><button data-view="promo">✦ Promo Hunting</button><button data-view="affiliates">♧ Affiliates</button><button data-view="education">▤ Education</button><button data-view="all">▦ All Channels</button></nav></aside>
<main><div class="top"><h1 id="pageTitle">Dashboard <small>● LIVE</small></h1><div class="toolbar"><button class="btn" onclick="refreshAll()">↻ Refresh</button></div></div>
<div class="stats"><div class="stat"><label>Channels available</label><strong id="statChannels">—</strong></div><div class="stat"><label>Visible feeds</label><strong id="statFeeds">—</strong></div><div class="stat"><label>Messages loaded</label><strong id="statMessages">—</strong></div><div class="stat"><label>Refresh</label><strong>3 sec</strong></div></div>
<div class="sectionhead"><h2>LIVE CHAT WALL</h2><div class="toolbar"><button class="btn" data-layout="one">1</button><button class="btn active" data-layout="two">2</button><button class="btn" data-layout="four">4</button><button class="btn" data-layout="eight">8</button></div></div>
<div class="toolbar"><select id="serverPicker"></select><select id="channelPicker"><option value="">Choose a channel…</option></select><button class="btn primary" id="addChannel">＋ Add feed</button><button class="btn" id="clearFeeds">Clear</button></div>
<div id="wall" class="wall two"><div class="card notice">Loading…</div></div>
<div class="lower"><section class="card pad"><h3>📡 ACTIVITY TICKER</h3><div class="ticker" id="ticker">Waiting for activity…</div></section><section class="card pad"><h3>RECENT ACTIVITY</h3><div id="activity" class="notice">Waiting…</div></section></div>
<div class="calwrap"><section class="card pad"><div class="sectionhead" style="margin:0 0 4px"><h3 id="calTitle">Calendar</h3><small style="color:#9693b5">Next 5 weeks</small></div><div class="dow"><span>SUN</span><span>MON</span><span>TUE</span><span>WED</span><span>THU</span><span>FRI</span><span>SAT</span></div><div id="calGrid"></div></section><section class="card pad"><h3>This week</h3><div id="calWeek" class="notice">No events — use /event add in Discord.</div><h3 style="margin-top:16px;color:#f6c453">Important days</h3><div id="calImp" class="notice">None yet</div></section></div>
<section class="card pad" style="margin-top:15px"><h3>🃏 GAMES</h3><div id="games" class="notice">No games yet — use /poker create in Discord.</div></section>
<section class="card pad" style="margin-top:15px"><h3>🎁 REWARDS SHOP <span id="rwPending" style="color:#f6c453;font-weight:400;margin-left:8px"></span></h3><div id="rewards" class="notice">No rewards yet — use /rewards add in Discord.</div></section>
<section class="card pad" style="margin-top:15px"><h3>♧ AFFILIATES &amp; MANAGERS</h3><div id="affiliates" class="notice">No affiliates yet — use /aff register in Discord.</div></section>
</main></div>
<script>
const $=s=>document.querySelector(s);
let layout='two',channels=[],selected=[],view='dashboard';
const wall=$('#wall'),sp=$('#serverPicker'),cp=$('#channelPicker');
const N={one:1,two:2,four:4,eight:8};
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
document.querySelectorAll('[data-layout]').forEach(b=>b.onclick=()=>{layout=b.dataset.layout;document.querySelectorAll('[data-layout]').forEach(x=>x.classList.toggle('active',x===b));renderWall()});
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{view=b.dataset.view;document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('active',x===b));$('#pageTitle').innerHTML=esc(b.textContent.slice(2))+' <small>● LIVE</small>';preset(view)});
sp.onchange=()=>loadChannels(true);
$('#addChannel').onclick=()=>{const c=channels.find(x=>x.id===cp.value);if(c&&!selected.some(x=>x.id===c.id)){selected.unshift(c);selected=selected.slice(0,8);renderWall()}};
$('#clearFeeds').onclick=()=>{selected=[];renderWall()};
async function j(url,opt){const r=await fetch(url,opt);return r.json()}
async function loadServers(){
  try{const s=await j('/api/servers');sp.innerHTML=(s.length>1?'<option value="all">All servers</option>':'')+s.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join('')||'<option>No servers</option>';await loadChannels(true)}
  catch(e){sp.innerHTML='<option>Server API unavailable</option>'}}
async function loadChannels(usePreset){
  try{const a=await j('/api/channels'+(sp.value?'?guild='+sp.value:''));
    if(!Array.isArray(a)){wall.innerHTML='<div class="card notice">'+esc(a.error||'No channels')+'</div>';return}
    channels=a;cp.innerHTML='<option value="">Choose a channel…</option>'+a.map(c=>`<option value="${c.id}">#${esc(c.name)}${c.category?' · '+esc(c.category):''}${sp.value==='all'?' · '+esc(c.guild_name):''}</option>`).join('');
    $('#statChannels').textContent=a.length;if(usePreset||!selected.length)preset(view)}catch(e){console.error(e)}}
function preset(v){
  const t={trading:['trad','market','stock','gold','crypto','forex','prop'],giveaways:['giveaway','game','event','contest'],promo:['promo','code','deal','reward','coupon'],affiliates:['affiliate','manager','report'],education:['education','learn','guide','algo','payout']};
  selected=(v==='all'||v==='dashboard')?channels.slice():channels.filter(c=>(t[v]||[]).some(x=>(c.name+' '+c.category).toLowerCase().includes(x)));
  if(!selected.length)selected=channels.slice(0,8);selected=selected.slice(0,8);renderWall()}
function renderWall(){
  wall.className='wall '+layout;const list=selected.slice(0,N[layout]);$('#statFeeds').textContent=list.length;wall.innerHTML='';
  if(!list.length){wall.innerHTML='<div class="card notice">Pick a server and channel, then Add feed — or choose a preset.</div>';return}
  list.forEach(c=>{const t=document.createElement('section');t.className='card tile';
    t.innerHTML=`<div class="tilehead"><div class="channelname"><span>●</span> #${esc(c.name)} <small style="color:#9693b5">${esc(c.guild_name||'')}</small></div><div class="tiletools"><button data-r="${c.id}">↻</button><button data-x="${c.id}">×</button></div></div><div class="messages" id="m${c.id}"><div class="empty">Loading…</div></div><form class="send" data-id="${c.id}"><input placeholder="Message #${esc(c.name)}…" autocomplete="off"><button>SEND</button></form>`;
    t.querySelector('[data-r]').onclick=()=>loadChat(c.id);
    t.querySelector('[data-x]').onclick=()=>{selected=selected.filter(x=>x.id!==c.id);renderWall()};
    t.querySelector('form').onsubmit=e=>sendMessage(e,c.id);
    wall.appendChild(t);loadChat(c.id)})}
async function loadChat(id){
  try{const a=await j('/api/chat?channel='+id),el=document.getElementById('m'+id);if(!el)return;
    if(!Array.isArray(a)){el.innerHTML='<div class="empty">'+esc(a.error||'Chat unavailable')+'</div>';return}
    const atBottom=el.scrollHeight-el.scrollTop-el.clientHeight<40;
    el.innerHTML=a.map(m=>'<div class="msg"><b>'+esc(m.author)+'</b> '+esc(m.content)+'<small>'+new Date(m.time).toLocaleTimeString()+'</small></div>').join('')||'<div class="empty">No messages yet</div>';
    if(atBottom)el.scrollTop=el.scrollHeight;$('#statMessages').textContent=a.length}catch(e){console.error(e)}}
async function sendMessage(e,id){
  e.preventDefault();const i=e.target.querySelector('input'),content=i.value.trim();if(!content)return;i.disabled=true;
  try{const a=await j('/api/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({channel:id,content})});
    if(a.error)alert(a.error);else{i.value='';setTimeout(()=>{loadChat(id);const el=document.getElementById('m'+id);if(el)el.scrollTop=el.scrollHeight},400)}}
  catch(err){alert('Send failed')}i.disabled=false;i.focus()}
async function activity(){
  try{const a=await j('/api/feed');if(!Array.isArray(a))return;
    $('#activity').className='';$('#activity').innerHTML=a.slice(0,8).map(x=>`<div class="feeditem">${esc(x.content||'(no text)')}<small>${esc(x.guild)} / #${esc(x.channel)} · ${esc(x.author)}</small></div>`).join('')||'<div class="notice">No recent activity.</div>';
    $('#ticker').innerHTML=a.slice(0,5).map(x=>'<span>◆ '+esc((x.content||'activity').slice(0,80))+'</span>').join('')||'Waiting…'}
  catch(e){$('#activity').textContent='Activity endpoint unavailable'}}
function refreshAll(){loadChannels(false);selected.slice(0,N[layout]).forEach(c=>loadChat(c.id));activity()}
async function loadAff(){
  try{const a=await j('/api/affiliates');if(!Array.isArray(a)||!a.length)return;
    $('#affiliates').className='';$('#affiliates').innerHTML='<table style="width:100%;border-collapse:collapse"><tr style="color:#9693b5;text-align:left"><th style="padding-bottom:6px">Affiliate</th><th>Manager</th><th>Sales</th><th>Signups</th><th>Revenue</th><th>Paid</th><th>Members</th></tr>'+a.map(x=>`<tr style="border-top:1px solid #292744"><td style="padding:8px 0"><b>${esc(x.name)}</b>${x.advice?'<br><small style="color:#9693b5">💡 '+esc(x.advice)+'</small>':''}</td><td>${esc(x.manager||'—')}</td><td>${x.sales}</td><td>${x.signups}</td><td style="color:#f6c453">$${x.revenue.toLocaleString()}</td><td>$${x.paid.toLocaleString()}</td><td>${x.members}</td></tr>`).join('')+'</table>'}
  catch(e){console.error(e)}}
function pad(n){return String(n).padStart(2,'0')}
function ymd(d){return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())}
async function loadCal(){
  try{const ev=await j('/api/events');if(!Array.isArray(ev))return;
    const today=new Date();today.setHours(0,0,0,0);const start=new Date(today);start.setDate(today.getDate()-today.getDay());
    const by={};ev.forEach(e=>{(by[e.date]=by[e.date]||[]).push(e)});let cells='';
    for(let i=0;i<35;i++){const d=new Date(start);d.setDate(start.getDate()+i);const k=ymd(d),es=by[k]||[],imp=es.some(e=>e.important);
      cells+='<div class="day'+(imp?' imp':'')+(k===ymd(today)?' today':'')+'"><span>'+(d.getDate()===1?d.toLocaleString('default',{month:'short'})+' 1':d.getDate())+'</span>'+(imp?'<i>★</i>':'')+'<div class="dots">'+es.slice(0,4).map(e=>'<b class="'+(e.important?'g':'')+'"></b>').join('')+'</div></div>'}
    $('#calGrid').innerHTML=cells;$('#calTitle').textContent=today.toLocaleString('default',{month:'long',year:'numeric'});
    const t0=ymd(today),t1=ymd(new Date(today.getTime()+7*864e5));
    const wk=ev.filter(e=>e.date>=t0&&e.date<=t1),im=ev.filter(e=>e.important&&e.date>=t0).slice(0,6);
    $('#calWeek').className='';$('#calWeek').innerHTML=wk.map(e=>'<div class="ev'+(e.important?' imp':'')+'"><b>'+(e.important?'★ ':'')+esc(e.title)+'</b><small>'+esc(e.date)+' '+esc(e.time||'')+(e.where?' · '+esc(e.where):'')+'</small></div>').join('')||'<div class="notice">Nothing this week</div>';
    $('#calImp').className='';$('#calImp').innerHTML=im.map(e=>'<div class="ev imp"><b>★ '+esc(e.title)+'</b><small>'+esc(e.date)+'</small></div>').join('')||'<div class="notice">None yet</div>'}
  catch(e){console.error(e)}}
async function loadGames(){
  try{const a=await j('/api/games');if(!Array.isArray(a)||!a.length)return;
    $('#games').className='';$('#games').innerHTML=a.slice(0,6).map(g=>'<div class="ev"><b>'+esc(g.title)+'</b> · '+esc(g.status)+'<small>'+g.players+'/'+g.seats+' seats'+(g.winners.length?' · winners: '+g.winners.map(w=>esc(w.name)+' ('+esc(w.hand)+')').join(', '):'')+'</small></div>').join('')}
  catch(e){console.error(e)}}
async function loadRewards(){
  try{const r=await j('/api/rewards');if(!r||!Array.isArray(r.shop))return;
    $('#rwPending').textContent=r.pending?r.pending+' pending request'+(r.pending>1?'s':''):'';
    if(!r.shop.length)return;
    $('#rewards').className='';
    $('#rewards').innerHTML=r.shop.map(x=>'<div class="ev"><b>#'+x.id+' '+esc(x.name)+'</b> · '+x.cost.toLocaleString()+' pts<small>'+(x.stock==null?'unlimited':x.stock+' left')+'</small></div>').join('')+(r.recent.length?'<div class="ev"><small>Recent requests: '+r.recent.map(x=>esc(x.user)+' → '+esc(x.reward)+' ('+esc(x.status)+')').join(' · ')+'</small></div>':'')}
  catch(e){console.error(e)}}
loadServers();activity();loadAff();loadCal();loadGames();loadRewards();
setInterval(()=>{selected.slice(0,N[layout]).forEach(c=>loadChat(c.id));activity();loadAff();loadCal();loadGames();loadRewards()},3000);
</script></body></html>"""


from challenge_commands import register as register_challenges
register_challenges(tree, ROOT)

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("Set DISCORD_TOKEN in Terminal first (never paste it into chat).")
    else:
        bot.run(token)
