import contextlib

import discord
from discord.ext import commands

from utils.exceptions import LiveLOLError
from utils.logger_config import logger


class Management(commands.Cog):
    """Handles bot command errors, cooldowns, and permissions."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ) -> discord.Message | None:
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
                title="Slow Down!",
                description=(
                    f"You're using '{ctx.command}' too fast. "
                    f"Try again in {round(error.retry_after, 2)}s."
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
            # Best-effort DM; if we can't DM either, the error is still handled.
            with contextlib.suppress(discord.Forbidden):
                await ctx.author.send(
                    f"I'm missing permissions (**{perms}**) in **{ctx.guild.name}**!",
                )
            return None
        if isinstance(unwrapped_error, commands.MissingPermissions):
            return await ctx.send(
                "You don't have permission to use this command.",
                delete_after=10,
            )
        if isinstance(unwrapped_error, LiveLOLError):
            return await ctx.send(f"{unwrapped_error}")
        logger.error(
            f"❌ ERROR: {unwrapped_error}",
            exc_info=unwrapped_error,
        )
        return await ctx.send("An unexpected error occurred.")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Triggered when the bot is kicked from a server."""
        await self.bot.db_service.remove_guild_config(guild.id)
        await self.bot.db_service.untrack_all_users(guild.id)
        logger.info(f"Bot removed from guild: {guild.name} ({guild.id})")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Management(bot))
