from discord.ext import commands


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
        self.bot.db_service.set_guild_config(ctx)
        await ctx.send("Rank updates will now be posted in this channel")

async def setup(bot):
    await bot.add_cog(Admin(bot))
