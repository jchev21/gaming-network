"""Authenticated Railway lobby commands; real rewards are deliberately disabled."""
import json
import os
from pathlib import Path
import aiohttp
import discord
from discord import app_commands

API = os.getenv('GAMING_API_URL', 'https://gaming-network-api-production.up.railway.app').rstrip('/')

def affiliate_allowed(settings, guild_id, role_ids):
    return str(settings.get('guild_id')) == str(guild_id) and str(settings.get('affiliate_role_id')) in {str(x) for x in role_ids}

def register(tree, root):
    settings_path = Path(os.getenv('DATA_DIR', str(root))) / 'challenge-settings.json'
    def settings():
        return json.loads(settings_path.read_text()) if settings_path.exists() else {}
    async def request(method, route, payload=None):
        token = os.getenv('API_SERVICE_TOKEN', '')
        if not token:
            raise ValueError('API_SERVICE_TOKEN is missing from the bot environment.')
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.request(method, API + route, json=payload, headers={'Authorization': 'Bearer ' + token}) as response:
                value = await response.json()
                if response.status >= 400:
                    raise ValueError(value.get('error', 'Lobby service unavailable'))
                return value
    async def fail(interaction, error):
        message = str(error) if isinstance(error, ValueError) else 'Could not reach the lobby service. Retry shortly.'
        await interaction.followup.send(message, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
    def valid_context(interaction):
        return interaction.guild_id and str(settings().get('guild_id')) == str(interaction.guild_id)
    def summary(c):
        return f"Poker lobby `{c['id']}` — {len(c['players'])}/5 players — {c['status']}.\nPractice lobby: prize redemption is not enabled."

    @tree.command(name='challenge_setup', description='Admin: select the role that may create poker challenges')
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def setup(interaction: discord.Interaction, affiliate_role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message('Administrator permission required.', ephemeral=True)
        if affiliate_role.is_default():
            return await interaction.response.send_message('Choose an Affiliate role, not @everyone.', ephemeral=True)
        tmp = settings_path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'guild_id': str(interaction.guild_id), 'affiliate_role_id': str(affiliate_role.id)}, indent=2))
        tmp.replace(settings_path)
        await interaction.response.send_message('Affiliate authorization configured for this server.', ephemeral=True)

    @tree.command(name='challenge_create', description='Affiliate: open a five-player lobby with a Poker Now table link')
    @app_commands.guild_only()
    async def create(interaction: discord.Interaction, table_url: str):
        cfg = settings()
        if not affiliate_allowed(cfg, interaction.guild_id, [r.id for r in interaction.user.roles]):
            return await interaction.response.send_message('The configured Affiliate role is required. An admin must run /challenge_setup first.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            c = await request('POST', '/challenges', {'affiliateId': str(interaction.user.id), 'tableUrl': table_url, 'rewardPoints': 0})
            await interaction.followup.send(summary(c) + '\nPlayers can reserve a seat with `/challenge_join challenge_id:` followed by this lobby ID.', ephemeral=True)
        except Exception as e:
            await fail(interaction, e)

    @tree.command(name='challenge_join', description='Reserve one of the first five seats in a poker challenge')
    @app_commands.guild_only()
    async def join(interaction: discord.Interaction, challenge_id: str):
        if not valid_context(interaction):
            return await interaction.response.send_message('Challenges are not configured for this server.', ephemeral=True)
        import uuid
        try: challenge_id = str(uuid.UUID(challenge_id))
        except ValueError: return await interaction.response.send_message('Invalid lobby ID.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            c = await request('GET', '/challenges/' + challenge_id)
            if str(interaction.user.id) not in c['players']:
                c = await request('POST', '/challenges/' + challenge_id + '/join', {'userId': str(interaction.user.id)})
            await interaction.followup.send(summary(c) + '\nYour reserved table: ' + (c.get('tableUrl') or 'Awaiting host link') + '\nThe host must admit the reserved players in Poker Now.', ephemeral=True)
        except Exception as e:
            await fail(interaction, e)

    @tree.command(name='challenge_status', description='Check the number of reserved seats in a poker lobby')
    @app_commands.guild_only()
    async def status(interaction: discord.Interaction, challenge_id: str):
        if not valid_context(interaction):
            return await interaction.response.send_message('Challenges are not configured for this server.', ephemeral=True)
        import uuid
        try: challenge_id = str(uuid.UUID(challenge_id))
        except ValueError: return await interaction.response.send_message('Invalid lobby ID.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            c = await request('GET', '/challenges/' + challenge_id)
            await interaction.followup.send(summary(c), ephemeral=True)
        except Exception as e:
            await fail(interaction, e)
