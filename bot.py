import asyncio
import os
import sys

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import database_startup
from utils.constants import REGION_CLUSTERS
from utils.db_service import DatabaseService
from utils.helpers import (
    extract_match_info,
    next_streak,
    parse_rank_info,
    rank_difference,
)
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
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                try:
                    cog_name = filename[:-3]
                    await self.load_extension(f"cogs.{cog_name}")
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


# Command Definitions


@commands.cooldown(1, 10, commands.BucketType.user)
@commands.bot_has_permissions(send_messages=True, embed_links=True)
@bot.command()
async def update(ctx):
    """Manually updates ranked information of tracked users in this server.

    Usage: !update
    Triggers ranked updates for all users in the server where this command is called
    """
    tracked_users = await bot.db_service.get_guild_tracked_users(ctx.guild.id)
    if not tracked_users:
        return await ctx.send("No users tracked in this server. Use !track.")
    await ctx.send(
        "Manual ranked update process has begun. "
        "This can take some time. "
        "A confirmation message will be sent when the process is completed.",
    )
    for user in tracked_users:
        puuid = user.get("puuid")
        region = user.get("region")
        riot_id = user.get("riot_id")
        cluster = REGION_CLUSTERS.get(region)
        data = await get_ranked_info(bot.session, puuid, region, RIOT_API_KEY)
        ranked_data = parse_rank_info(user, data)
        if not rank_difference(ranked_data):
            continue
        match_info = await get_recent_match_info(
            bot.session,
            puuid,
            cluster,
            RIOT_API_KEY,
        )
        processed_match_info = extract_match_info(match_info, puuid)
        if processed_match_info is None:
            logger.warning(f"⚠️ Skipping {riot_id}: no match info")
            continue
        # Only a genuinely new game advances the win/loss streak. A repeat match
        # id (e.g. an LP change with no new game, like a dodge) leaves the streak
        # untouched so it isn't double-counted.
        match_id = processed_match_info.get("match_id")
        if match_id and match_id != user.get("last_match_id"):
            streak = next_streak(user.get("streak"), processed_match_info.get("win"))
        else:
            streak = user.get("streak") or 0
        data["streak"] = streak
        # Never overwrite a good last_match_id with None (see background.py): a
        # match DTO missing metadata.matchId yields match_id=None, and clobbering
        # it would make the next real game look "new" and double-count the streak.
        if match_id:
            data["last_match_id"] = match_id
        await bot.db_service.update_ranked_data(puuid, data)
        view = MatchDetailsView(
            processed_match_info,
            ranked_data,
            riot_id,
            puuid,
            region,
            streak,
        )
        initial_embed = view.create_minimized_embed()
        message = await ctx.send(embed=initial_embed, view=view)
        view.message = message
        # This sleep ensures we stay behind API Rate limit curve.
        await asyncio.sleep(1.5)
    return await ctx.send("Ranked information has been updated.")


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
