import asyncio
import os
import sys

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv
from google.cloud.firestore import FieldFilter

from database import TRACKED_USERS_COLLECTION, database_startup
from utils.constants import RANK_ORDER, TIER_ORDER
from utils.db_service import DatabaseService
from utils.helpers import extract_match_info
from utils.logger_config import logger
from utils.riot_api import get_ranked_info, get_recent_match_info
from utils.sentry_config import setup_sentry
from utils.ui_components import MatchDetailsView, MyHelp

# API Keys

load_dotenv()
DISCORD_KEY = os.getenv("DISCORD_PUBLIC_KEY")
RIOT_API_KEY = os.getenv("RIOT_API_KEY")

# Sentry Initialization

setup_sentry()

# Database Startup

db = database_startup()
if not db:
    logger.error("❌ ERROR: Database did not properly initialize")
    sys.exit(1)

# Bot Startup

BOT_PREFIX = "!"
class MyBot(commands.Bot):
    """The main bot engine."""
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="Watching The Rift - !help",
        )
        super().__init__(
            command_prefix=BOT_PREFIX,
            intents=intents,
            activity=activity,
        )
        self.session = None  # placeholder
        self.db_service = DatabaseService(db=db)
        self.db = db

    async def setup_hook(self):
        """Bot bootup sequence."""
        self.session = aiohttp.ClientSession()
        logger.info("✅ Persistent HTTP Session created.")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    cog_name = filename[:-3]
                    await self.load_extension(f'cogs.{cog_name}')
                    logger.info(f"✅ Loaded cog: {cog_name}")
                except Exception as e:
                    logger.error(f"❌ Failed to load cog {filename}: {e}")

    async def close(self):
        """Bot bootdown sequence."""
        if self.session:
            await self.session.close()
            logger.info("🛑 HTTP Session closed.")
        await super().close()

bot = MyBot()
bot.help_command = MyHelp()

# Event Handlers

@bot.event
async def on_ready():
    # called when bot initially connects
    logger.info(f"✅ Bot connected as {bot.user.name} (ID: {bot.user.id})")
    if db is None:
        logger.warning("Database is not connected")

# Command Definitions

@commands.cooldown(1, 10, commands.BucketType.user)
@commands.bot_has_permissions(send_messages=True, embed_links=True)
@bot.command()
async def update(ctx):
    """Manually updates ranked information of tracked users in this server.

    Usage: !update
    Triggers ranked updates for all users in the server where this command is called
    """
    if db is None:
        return await ctx.send("Database Error")
    guild_id_str = str(ctx.guild.id)
    docs = (
        db.collection(TRACKED_USERS_COLLECTION)
        .where(filter=FieldFilter("guild_ids", "array_contains", guild_id_str))
        .stream()
    )
    doc_list = list(docs)
    if not doc_list:
        return await ctx.send("No users tracked in this server. Use !track.")
    await ctx.send(
        "Manual ranked update process has begun. " \
        "This can take some time. " \
        "A confirmation message will be sent when the process is completed.",
    )
    for doc in doc_list:
        old_tier = doc.get("tier")
        old_rank = doc.get("rank")
        old_lp = doc.get("LP")
        puuid = doc.get("puuid")
        data = await get_ranked_info(bot.session, puuid, RIOT_API_KEY)
        new_tier = data.get("tier")
        new_rank = data.get("rank")
        new_lp = data.get("LP")
        if old_tier == new_tier and old_rank == new_rank and old_lp == new_lp:
            continue
        doc.reference.update(data)
        riot_id = doc.get("riot_id")
        match_info = await get_recent_match_info(bot.session, puuid, RIOT_API_KEY)
        processed_match_info = extract_match_info(match_info, puuid)
        ranked_data = {
            "old_tier": old_tier,
            "old_rank": old_rank,
            "old_lp": old_lp,
            "new_tier": new_tier,
            "new_rank": new_rank,
            "new_lp": new_lp,
        }
        view = MatchDetailsView(processed_match_info, ranked_data, riot_id, puuid)
        initial_embed = view.create_minimized_embed()
        message = await ctx.send(embed=initial_embed, view=view)
        view.message = message
        # This sleep ensures we stay behind API Rate limit curve.
        await asyncio.sleep(1.5)
    return await ctx.send("Ranked information has been updated.")

@commands.cooldown(1, 5, commands.BucketType.user)
@commands.bot_has_permissions(send_messages=True, embed_links=True)
@bot.command()
async def leaderboard(ctx):
    """Prints the servers leaderboard.

    Usage: !leaderboard
    Prints out the tracked users in order of rank from highest to lowest
    """
    if db is None:
        return await ctx.send("Database Error")
    guild_id_str = str(ctx.guild.id)
    # DB handling
    docs = (
        db.collection(TRACKED_USERS_COLLECTION)
        .where(filter=FieldFilter("guild_ids", "array_contains", guild_id_str))
        .stream()
    )
    doc_list = list(docs)
    if not doc_list:
        return await ctx.send("No users tracked in this server. Use !track.")
    leaderboard_data = []
    for doc in doc_list:
        data = doc.to_dict()
        leaderboard_data.append(
            {
                "name": data.get("riot_id"),
                "tier": data.get("tier", "UNRANKED"),
                "rank": data.get("rank", ""),
                "lp": data.get("LP", 0),
            },
        )
    leaderboard_data.sort(
        key=lambda x: (
            TIER_ORDER.get(x["tier"].upper(), -1),
            RANK_ORDER.get(x["rank"], 0),
            x["lp"],
        ),
        reverse=True,
    )
    embed = discord.Embed(
        title=f"🏆 Leaderboard for {ctx.guild.name}",
        color=discord.Color.gold(),
    )
    description = ""
    for i, player in enumerate(leaderboard_data, 1):
        if i == 1:
            rank_prefix = "🥇"
        elif i == 2:
            rank_prefix = "🥈"
        elif i == 3:
            rank_prefix = "🥉"
        else:
            rank_prefix = f"**{i}.**"
        description += (
            f"{rank_prefix} **{player['name']}** - "
            f"{player['tier']} {player['rank']} ({player['lp']} LP)\n"
        )
    embed.description = description
    await ctx.send(embed=embed)

# Helper Functions

def bot_startup():
    try:
        bot.run(DISCORD_KEY)
    except discord.errors.LoginFailure:
        logger.exception(
            "❌ ERROR: Invalid Token detected. Please check your DISCORD_TOKEN.",
        )
    except Exception as e:
        logger.exception(f"❌ ERROR: occurred while running the bot: {e}")
