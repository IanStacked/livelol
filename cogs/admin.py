from discord.ext import commands

from database import GUILD_CONFIG_COLLECTION
from utils.logger_config import logger


class Admin(commands.Cog):
    """Handles bot administration."""

    def __init__(self, bot):
        self.bot = bot

    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(name="updateshere")
    async def set_update_channel(self, ctx):
        """Defaults automatic rank updates to post in this channel.

        Usage: !updateshere
        Automatic rank updates will post in the channel where this bot is used.
        If this command is not used, by default the bot will simply not post
        live ranked updates.
        """
        if self.bot.db is None:
            return await ctx.send("Database Error")
        doc_ref = (
            self.bot.db.collection(GUILD_CONFIG_COLLECTION).document(str(ctx.guild.id))
        )
        try:
            doc_ref.set({"channel_id": ctx.channel.id}, merge=True)
            await ctx.send("Rank updates will now be posted in this channel")
        except Exception as e:
            logger.exception(f"❌ ERROR: setting guild config: {e}")
            await ctx.send("Database write failed.")
            raise e

async def setup(bot):
    await bot.add_cog(Admin(bot))
