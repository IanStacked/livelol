import discord
from discord.ext import commands

from utils.constants import RANK_ORDER, TIER_ORDER


class Leaderboard(commands.Cog):
    """Handles bot leaderboard."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.command()
    async def leaderboard(self, ctx: commands.Context) -> None:
        """Prints the servers leaderboard.

        Usage: !leaderboard
        Prints out the tracked users in order of rank from highest to lowest
        """
        tracked_users = await self.bot.db_service.get_guild_tracked_users(ctx.guild.id)
        if not tracked_users:
            return await ctx.send("No users tracked in this server. Use !track.")
        leaderboard_data = []
        for data in tracked_users:
            leaderboard_data.append(
                {
                    "name": data.get("riot_id"),
                    "tier": data.get("tier", "UNRANKED"),
                    "rank": data.get("rank", ""),
                    "lp": data.get("LP", 0),
                    "region": data.get("region"),
                },
            )
        leaderboard_data.sort(
            key=lambda x: (
                TIER_ORDER.get(x["tier"].upper(), -1),
                RANK_ORDER.get(x["rank"], 0),
                x["lp"],
            ),
            reverse=True,
        )
        embed = discord.Embed(
            title=f"🏆 Leaderboard for {ctx.guild.name}",
            color=discord.Color.gold(),
        )
        description = ""
        for i, player in enumerate(leaderboard_data, 1):
            if i == 1:
                rank_prefix = "🥇"
            elif i == 2:
                rank_prefix = "🥈"
            elif i == 3:
                rank_prefix = "🥉"
            else:
                rank_prefix = f"**{i}.**"
            description += (
                f"{rank_prefix} ({player['region']}) **{player['name']}** - "
                f"{player['tier']} {player['rank']} ({player['lp']} LP)\n"
            )
        embed.description = description
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
