import asyncio

from discord.ext import commands, tasks

from bot import RIOT_API_KEY
from database import TRACKED_USERS_COLLECTION
from utils.constants import REGION_CLUSTERS
from utils.exceptions import ServiceUnavailableError
from utils.helpers import (
    check_new_riot_id,
    extract_match_info,
    parse_rank_info,
    rank_difference,
)
from utils.logger_config import logger
from utils.riot_api import get_ranked_info, get_recent_match_info
from utils.ui_components import MatchDetailsView


class Background(commands.Cog):
    """Handles bot background processes."""

    def __init__(self, bot):
        self.bot = bot
        if not self.background_update_task.is_running():
            self.background_update_task.start()
            logger.info("✅ Background update task started.")

    def cog_unload(self):
        """Clean up task if cog is unloaded."""
        self.background_update_task.cancel()

    @tasks.loop(minutes=10)
    async def background_update_task(self):
        """Bot background update task."""
        try:
            logger.info("♻️ Starting background update loop")
            docs = self.bot.db.collection(TRACKED_USERS_COLLECTION).stream()
            doc_list = list(docs)
            for doc in doc_list:
                puuid = doc.get("puuid")
                region = doc.get("region")
                cluster = REGION_CLUSTERS.get(region)
                riot_id = doc.get("riot_id")
                guild_ids = doc.get("guild_ids")
                try:
                    data = await get_ranked_info(
                        self.bot.session,
                        puuid,
                        region,
                        RIOT_API_KEY,
                    )
                except ServiceUnavailableError:
                    continue
                ranked_data = parse_rank_info(doc, data)
                if not rank_difference(ranked_data):
                    continue
                doc.reference.update(data)
                try:
                    match_info = await get_recent_match_info(
                        self.bot.session,
                        puuid,
                        cluster,
                        RIOT_API_KEY,
                    )
                except ServiceUnavailableError:
                    continue
                processed_match_info = extract_match_info(match_info, puuid)
                new_riot_id = check_new_riot_id(
                    processed_match_info,
                    puuid,
                    riot_id,
                )
                if new_riot_id:
                    await self.bot.db_service.update_riot_id(puuid, new_riot_id)
                    riot_id = new_riot_id
                    logger.info(f"📝 Name Change Detected: {riot_id} -> {new_riot_id}")
                for guild in guild_ids:
                    channel_id = await self.bot.db_service.get_guild_config(guild)
                    if channel_id is None:
                        continue
                    channel = self.bot.get_channel(channel_id)
                    view = MatchDetailsView(
                        processed_match_info,
                        ranked_data,
                        riot_id,
                        puuid,
                        region,
                    )
                    initial_embed = view.create_minimized_embed()
                    message = await channel.send(embed=initial_embed, view=view)
                    view.message = message
                # This sleep ensures we stay behind API Rate limit curve.
                await asyncio.sleep(1.5)
        except Exception as e:
            logger.exception(f"❌ ERROR: {e}")

    @background_update_task.before_loop
    async def before_background_task(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Background(bot))
