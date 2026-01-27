from discord.ext import commands
from firebase_admin import firestore

from bot import RIOT_API_KEY
from database import TRACKED_USERS_COLLECTION
from utils.helpers import parse_riot_id
from utils.logger_config import logger
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
        # API handling
        puuid = await get_puuid(self.bot.session, username, tagline, RIOT_API_KEY)
        # DB handling
        guild_id_str = str(ctx.guild.id)
        doc_id = puuid
        doc_ref = self.bot.db.collection(TRACKED_USERS_COLLECTION).document(doc_id)
        ranked_data = await get_ranked_info(self.bot.session, puuid, RIOT_API_KEY)
        try:
            doc_ref.set(
                {
                    "riot_id": riot_id,
                    "puuid": puuid,
                    "tier": f"{ranked_data.get('tier')}",
                    "rank": f"{ranked_data.get('rank')}",
                    "LP": ranked_data.get("LP"),
                    "guild_ids": firestore.ArrayUnion([guild_id_str]),
                    f"server_info.{guild_id_str}": {"added_by": ctx.author.id},
                },
                merge=True,
            )
            await ctx.send(f"{riot_id} is now being tracked!")
        except Exception as e:
            logger.exception(f"❌ ERROR: tracking: {e}")
            await ctx.send("Database write failed.")
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
        # API handling
        puuid = await get_puuid(self.bot.session, username, tagline, RIOT_API_KEY)
        # DB handling
        guild_id_str = str(ctx.guild.id)
        doc_id = puuid
        doc_ref = self.bot.db.collection(TRACKED_USERS_COLLECTION).document(doc_id)
        try:
            doc = doc_ref.get()
            if not doc.exists:
                return await ctx.send(f"{riot_id} is not in the database.")
            data = doc.to_dict()
            guild_list = data.get("guild_ids", [])
            if guild_id_str not in guild_list:
                return await ctx.send(f"{riot_id} is not being tracked in this server.")
            guild_list.remove(guild_id_str)
            if not guild_list:
                # We are the only server left, delete the whole file
                doc_ref.delete()
                await ctx.send(f"{riot_id} is no longer tracked")
            else:
                data["guild_ids"] = guild_list
                del data[f"server_info.{guild_id_str}"]
                doc_ref.set(data)
                await ctx.send(f"{riot_id} is no longer tracked")
        except Exception as e:
            logger.exception(f"❌ ERROR: untracking: {e}")
            await ctx.send("Database update failed")

async def setup(bot):
    await bot.add_cog(Track(bot))
