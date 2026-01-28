from discord.ext import commands

from bot import RIOT_API_KEY
from utils.helpers import parse_riot_id
from utils.riot_api import get_puuid, get_ranked_info


class Track(commands.Cog):
    """Handles bot user tracking functionality."""

    def __init__(self, bot):
        self.bot = bot

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.command()
    async def track(self, ctx, *, riot_id):
        """Adds a user to the list of users tracked by the bot.

        Usage: !track <riotid>
        Given a riotid, the bot will attempt to add the user to the bot's database,
        "tracking" the user.
        """
        if self.bot.db is None:
            return await ctx.send("Database Error")
        parsed = parse_riot_id(riot_id)
        if not parsed:
            return await ctx.send(
                "Invalid input, please ensure syntax is: !track username#tagline",
            )
        username = parsed[0]
        tagline = parsed[1]
        riot_id = f"{username}#{tagline}"
        puuid = await get_puuid(self.bot.session, username, tagline, RIOT_API_KEY)
        ranked_data = await get_ranked_info(self.bot.session, puuid, RIOT_API_KEY)
        await self.bot.db_service.track_user(
            ctx,
            riot_id,
            puuid,
            ranked_data,
        )
        await ctx.send(f"{riot_id} is now being tracked!")

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
        puuid = await get_puuid(self.bot.session, username, tagline, RIOT_API_KEY)
        await self.bot.db_service.untrack_user(
            ctx,
            riot_id,
            puuid,
        )
        await ctx.send(f"{riot_id} is no longer tracked")

async def setup(bot):
    await bot.add_cog(Track(bot))
