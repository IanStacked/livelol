import asyncio

from discord.ext import commands, tasks
from firebase_admin import firestore

from bot import RIOT_API_KEY
from database import (
    BOT_HEALTH_COLLECTION,
    HEARTBEAT_DOC,
)
from utils.constants import REGION_CLUSTERS
from utils.exceptions import LiveLOLError
from utils.helpers import (
    check_new_riot_id,
    extract_match_info,
    next_streak,
    parse_rank_info,
    rank_difference,
)
from utils.logger_config import logger
from utils.riot_api import get_ranked_info, get_recent_match_info
from utils.ui_components import MatchDetailsView


class Background(commands.Cog):
    """Handles bot background processes."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        if not self.background_update_task.is_running():
            self.background_update_task.start()
            logger.info("✅ Background update task started.")
        if not self.heartbeat_task.is_running():
            self.heartbeat_task.start()
            logger.info("✅ Heartbeat task started.")

    def cog_unload(self) -> None:
        """Clean up tasks if cog is unloaded."""
        self.background_update_task.cancel()
        self.heartbeat_task.cancel()

    @tasks.loop(seconds=60)
    async def heartbeat_task(self) -> None:
        """Write a liveness heartbeat to Firestore.

        Proves the bot's event loop is alive. `scripts/health.sh` reads this doc
        and derives liveness from how fresh `last_beat` is. Guarded so a heartbeat
        failure (e.g. a transient Firestore error) never disrupts the bot.
        """
        try:
            self.bot.db.collection(BOT_HEALTH_COLLECTION).document(HEARTBEAT_DOC).set(
                {
                    "last_beat": firestore.SERVER_TIMESTAMP,
                    "connected": self.bot.is_ready() and not self.bot.is_closed(),
                    "latency_ms": round(self.bot.latency * 1000),
                    "bot_user": str(self.bot.user),
                },
            )
        except Exception as e:
            logger.warning(f"⚠️ Heartbeat write failed: {e}")

    @heartbeat_task.before_loop
    async def before_heartbeat_task(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=10)
    async def background_update_task(self) -> None:
        """Bot background update task."""
        try:
            logger.info("♻️ Starting background update loop")
            tracked_users = await self.bot.db_service.get_all_tracked_users()
            for user in tracked_users:
                puuid = user.get("puuid")
                region = user.get("region")
                cluster = REGION_CLUSTERS.get(region)
                riot_id = user.get("riot_id")
                guild_ids = user.get("guild_ids")
                # Guard each user so one player's Riot/DB error (rate-limited shard,
                # missing match, renamed account) never aborts the whole cycle.
                try:
                    data = await get_ranked_info(
                        self.bot.session,
                        puuid,
                        region,
                        RIOT_API_KEY,
                    )
                    ranked_data = parse_rank_info(user, data)
                    if not rank_difference(ranked_data):
                        continue
                    match_info = await get_recent_match_info(
                        self.bot.session,
                        puuid,
                        cluster,
                        RIOT_API_KEY,
                    )
                    processed_match_info = extract_match_info(match_info, puuid)
                    if processed_match_info is None:
                        logger.warning(
                            f"⚠️ Skipping {riot_id} this cycle: no match info"
                        )
                        continue
                    # Only a genuinely new game advances the win/loss streak. A
                    # repeat match id (e.g. an LP change with no new game, like a
                    # dodge) leaves the streak untouched so it isn't double-counted.
                    match_id = processed_match_info.get("match_id")
                    if match_id and match_id != user.get("last_match_id"):
                        streak = next_streak(
                            user.get("streak"), processed_match_info.get("win")
                        )
                    else:
                        streak = user.get("streak") or 0
                    data["streak"] = streak
                    data["last_match_id"] = match_id
                    await self.bot.db_service.update_ranked_data(puuid, data)
                    new_riot_id = check_new_riot_id(
                        processed_match_info,
                        puuid,
                        riot_id,
                    )
                    if new_riot_id:
                        await self.bot.db_service.update_riot_id(puuid, new_riot_id)
                        logger.info(
                            f"📝 Name Change Detected: {riot_id} -> {new_riot_id}"
                        )
                        riot_id = new_riot_id
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
                            streak,
                        )
                        initial_embed = view.create_minimized_embed()
                        message = await channel.send(embed=initial_embed, view=view)
                        view.message = message
                    # This sleep ensures we stay behind API Rate limit curve.
                    await asyncio.sleep(1.5)
                except LiveLOLError as e:
                    logger.warning(f"⚠️ Skipping {riot_id} this cycle: {e}")
                except Exception as e:
                    logger.exception(f"❌ ERROR processing {riot_id}: {e}")
        except Exception as e:
            logger.exception(f"❌ ERROR: {e}")

    @background_update_task.before_loop
    async def before_background_task(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Background(bot))
