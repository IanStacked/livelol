import contextlib

import discord
from discord.ext import commands

from utils.exceptions import RateLimitError, RiotAPIError, UserNotFoundError
from utils.logger_config import logger


class Management(commands.Cog):
    """Handles bot command errors, cooldowns, and permissions."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(
          self,
          ctx: commands.Context,
          error: commands.CommandError,
    ):
        # Unwrap discord command error wrapper so we can access the original error.
        unwrapped_error = getattr(error, "original", error)
        if isinstance(unwrapped_error, commands.CommandNotFound):
            return await ctx.send(
                "Sorry, I don't know that command",
                delete_after=10,
            )
        if isinstance(unwrapped_error, commands.MissingRequiredArgument):
            return await ctx.send(
                f"Missing arguments. Usage: !{ctx.command} '{ctx.command.signature}'",
                delete_after=10,
            )
        if isinstance(unwrapped_error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title = "Slow Down!",
                description = (
                    f"You're using '{ctx.command}' too fast. \
                    Try again in {round(error.retry_after, 2)}s."
                ),
                color=discord.Color.orange(),
            )
            return await ctx.send(
                embed=embed,
                delete_after=10,
            )
        if isinstance(unwrapped_error, commands.BotMissingPermissions):
            perms = unwrapped_error.missing_permissions
            logger.warning(f"Bot missing perms in {ctx.guild.id}: {perms}")
            with contextlib.suppress(discord.Forbidden):
                return await ctx.author.send(
                    f"I'm missing permissions (**{perms}**) in **{ctx.guild.name}**!",
                )
        if isinstance(unwrapped_error, UserNotFoundError):
            return await ctx.send(f"User Not Found: {unwrapped_error}")
        if isinstance(unwrapped_error, RateLimitError):
            return await ctx.send(
                f"Bot is busy, try again in a minute: {unwrapped_error}",
                delete_after=10,
            )
        if isinstance(unwrapped_error, RiotAPIError):
            return await ctx.send(f"Riot API issue: {unwrapped_error}")
        if isinstance(unwrapped_error, commands.MissingPermissions):
            return await ctx.send(
                "You don't have permission to use this command.",
                delete_after=10,
            )
        logger.error(
            f"❌ ERROR: {unwrapped_error}",
            exc_info=unwrapped_error,
        )
        return await ctx.send("An unexpected error occurred.")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Triggered when the bot is kicked from a server."""
        await self.bot.db_service.remove_guild_config(guild)
        await self.bot.db_service.untrack_all_users(guild)
        logger.info(f"Bot removed from guild: {guild.name} ({guild.id})")

async def setup(bot):
    await bot.add_cog(Management(bot))
