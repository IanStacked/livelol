from discord.ext import commands

from bot import RIOT_API_KEY
from utils.constants import REGION_CLUSTERS
from utils.exceptions import DatabaseError, UserNotFoundError
from utils.helpers import parse_region, parse_riot_id
from utils.logger_config import logger
from utils.riot_api import get_puuid, get_ranked_info, get_summoner_info


class Track(commands.Cog):
    """Handles bot user tracking functionality."""

    def __init__(self, bot):
        self.bot = bot

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.command()
    async def track(self, ctx, region, *, riot_id):
        """Adds a user to the list of users tracked by the bot.

        Usage: !track <region> <riotid>
        Given a region and riotid, the bot will attempt to add the user to the bot's
        database, "tracking" the user.
        List of valid region tags and their respective geographic area names:
        na1 - North America
        euw1 - Europe West
        eun1 - Europe Nordic & East
        me1 - Middle East
        kr - Korea
        jp1 - Japan
        br1 - Brazil
        la1 - Latin America North (LAN)
        la2 - Latin America South (LAS)
        oc1 - Oceania (OCE)
        tr1 - Turkey
        ru - Russia
        ph2 - Philippines
        sg2 - Singapore, Malaysia, & Indonesia
        th2 - Thailand
        tw2 - Taiwan, Hong Kong, & Macao
        vn2 - Vietnam
        """
        if self.bot.db is None:
            return await ctx.send("Database Error")
        parsed_region = parse_region(region)
        if not parsed_region:
            return await ctx.send(
                "Invalid input, please ensure syntax " \
                "is: !track region username#tagline.",
            )
        if parsed_region not in REGION_CLUSTERS:
            return await ctx.send(
                "The region inputted is invalid. " \
                "Please ensure syntax " \
                "is: !track region username#tagline. " \
                "List of valid regions: br1, eun1, euw1, jp1, kr, la1, la2, na1, " \
                "oc1, tr1, ru, ph2, sg2, th2, tw2, vn2, me1 " \
                "For more detailed information, use !help track.",
            )
        parsed_riot_id = parse_riot_id(riot_id)
        if not parsed_riot_id:
            return await ctx.send(
                "Invalid input, please ensure syntax " \
                "is: !track region username#tagline.",
            )
        username = parsed_riot_id[0]
        tagline = parsed_riot_id[1]
        riot_id = f"{username}#{tagline}"
        try:
            puuid = await get_puuid(self.bot.session, username, tagline, RIOT_API_KEY)
            summoner_info = await get_summoner_info(
                self.bot.session,
                puuid,
                parsed_region,
                RIOT_API_KEY,
            )
            if not summoner_info:
                raise UserNotFoundError(
                    f"Player {riot_id} was found, " \
                    f"but they do not have a profile on {parsed_region}. " \
                    "Please enter the users correct region. " \
                    "List of valid regions: br1, eun1, euw1, jp1, kr, la1, la2, na1, " \
                    "oc1, tr1, ru, ph2, sg2, th2, tw2, vn2, me1 " \
                    "For more detailed information, use !help track.",
                )
            ranked_data = await get_ranked_info(
                self.bot.session,
                puuid,
                parsed_region,
                RIOT_API_KEY,
            )
            await self.bot.db_service.track_user(
                ctx,
                riot_id,
                puuid,
                ranked_data,
                parsed_region,
            )
            await ctx.send(f"{riot_id} is now being tracked!")
        except DatabaseError as e:
            logger.exception(f"Database write failed for {riot_id}: {e}")
            raise e


    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.command()
    async def untrack(self, ctx, *, riot_id):
        """Removes a user from the list of users tracked by the bot.

        Usage: !untrack <riotid>
        Given a riotid, the bot will attempt to remove the user from the bot's database,
        "untracking" the user.
        """
        if self.bot.db is None:
            return await ctx.send("Database Error")
        parsed = parse_riot_id(riot_id)
        if not parsed:
            return await ctx.send(
                "Invalid input, please ensure syntax is: !untrack username#tagline",
            )
        username = parsed[0]
        tagline = parsed[1]
        riot_id = f"{username}#{tagline}"
        try:
            puuid = await get_puuid(self.bot.session, username, tagline, RIOT_API_KEY)
            await self.bot.db_service.untrack_user(
                ctx,
                riot_id,
                puuid,
            )
            await ctx.send(f"{riot_id} is no longer tracked")
        except DatabaseError as e:
            logger.exception(f"Database write failed for {riot_id}: {e}")
            raise e

async def setup(bot):
    await bot.add_cog(Track(bot))
