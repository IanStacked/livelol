import asyncio

from discord.ext import commands, tasks

from bot import RIOT_API_KEY
from database import GUILD_CONFIG_COLLECTION, TRACKED_USERS_COLLECTION
from utils.helpers import check_new_riot_id, extract_match_info
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
                old_tier = doc.get("tier")
                old_rank = doc.get("rank")
                old_lp = doc.get("LP")
                puuid = doc.get("puuid")
                data = await get_ranked_info(self.bot.session, puuid, RIOT_API_KEY)
                new_tier = data.get("tier")
                new_rank = data.get("rank")
                new_lp = data.get("LP")
                if old_tier == new_tier and old_rank == new_rank and old_lp == new_lp:
                    continue
                doc.reference.update(data)
                guild_ids = doc.get("guild_ids")
                for guild in guild_ids:
                    channel = None
                    try:
                        config_ref = (
                            self.bot.db.collection(GUILD_CONFIG_COLLECTION).document(guild)
                        )
                        config = config_ref.get()
                        if config.exists:
                            channel_id = config.get("channel_id")
                            channel = self.bot.get_channel(channel_id)
                    except Exception as e:
                        logger.exception(
                            f"❌ ERROR: fetching config for guild {guild}: {e}",
                        )
                    if channel:
                        riot_id = doc.get("riot_id")
                        match_info = await get_recent_match_info(
                            self.bot.session,
                            puuid,
                            RIOT_API_KEY,
                        )
                        processed_match_info = extract_match_info(match_info, puuid)
                        ranked_data = {
                            "old_tier": old_tier,
                            "old_rank": old_rank,
                            "old_lp": old_lp,
                            "new_tier": new_tier,
                            "new_rank": new_rank,
                            "new_lp": new_lp,
                        }
                        new_riot_id = check_new_riot_id(
                            processed_match_info,
                            puuid,
                            riot_id,
                        )
                        if(new_riot_id != ""):
                            #update database with new riot_id
                            doc_id = puuid
                            doc_ref = (
                                self.bot.db.collection(TRACKED_USERS_COLLECTION).document(doc_id)
                            )
                            formatted_riot_id = {
                                "riot_id": new_riot_id,
                            }
                            doc_ref.update(formatted_riot_id)
                            riot_id = new_riot_id
                        view = MatchDetailsView(
                            processed_match_info,
                            ranked_data,
                            riot_id,
                            puuid,
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
