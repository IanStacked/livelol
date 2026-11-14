import asyncio

import discord
from discord.ext import commands, tasks

from utils.db_service import DeadlockDatabaseService
from utils.deadlock_api import (
    DeadlockPlayerNotFoundError,
    get_hero_name,
    get_match_history,
    new_matches,
    newest_match_id,
)
from utils.deadlock_ui import DeadlockMatchView
from utils.exceptions import DatabaseError, LiveLOLError
from utils.logger_config import logger

# Cached for a guild whose config read failed this cycle: distinct from None,
# which means the guild has no channel set.
_READ_FAILED = object()


def parse_account_id(raw):
    """Steam account id (SteamID3) as a positive int, or None.

    ASCII digits only (isdigit alone passes superscripts, which int() rejects), and
    bounded at 2**31 - 1 because the API types account_id as int32.
    """
    raw = raw.strip()
    if not (raw.isascii() and raw.isdigit()):
        return None
    value = int(raw)
    if value <= 0 or value > 2**31 - 1:
        return None
    return value


class Deadlock(commands.Cog):
    """Deadlock watchlist commands and the match-announcement background loop."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Own service: League's DatabaseService is left untouched.
        self.dl_db = DeadlockDatabaseService(bot.db)
        if not self.deadlock_update_task.is_running():
            self.deadlock_update_task.start()
            logger.info("✅ Deadlock update task started.")

    def cog_unload(self) -> None:
        self.deadlock_update_task.cancel()

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.command()
    async def trackdl(self, ctx: commands.Context, account_id: str) -> None:
        """Adds a Deadlock player to the list tracked by the bot.

        Usage: !trackdl <steam account id>
        The account id is the player's SteamID3 number (the number in their
        Steam3 ID, e.g. [U:1:12345678] is 12345678). Every match they finish,
        ranked or normal, is posted once the API picks it up.
        """
        if self.bot.db is None:
            raise DatabaseError("The database is currently unavailable.")
        parsed = parse_account_id(account_id)
        if parsed is None:
            return await ctx.send(
                "Invalid input, please ensure syntax is: !trackdl <steam account id>",
            )
        history = await get_match_history(self.bot.session, parsed)
        last_match_id = newest_match_id(history)
        if last_match_id is None:
            raise DeadlockPlayerNotFoundError(
                f"No Deadlock match history found for {parsed}. "
                "Check the account id (SteamID3).",
            )
        await self.dl_db.track_user(ctx.guild.id, ctx.author.id, parsed, last_match_id)
        await ctx.send(f"Deadlock player {parsed} is now being tracked!")

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.command()
    async def untrackdl(self, ctx: commands.Context, account_id: str) -> None:
        """Removes a Deadlock player from the list tracked by the bot.

        Usage: !untrackdl <steam account id>
        """
        if self.bot.db is None:
            raise DatabaseError("The database is currently unavailable.")
        parsed = parse_account_id(account_id)
        if parsed is None:
            return await ctx.send(
                "Invalid input, please ensure syntax is: !untrackdl <steam account id>",
            )
        await self.dl_db.untrack_user(ctx.guild.id, parsed)
        await ctx.send(f"Deadlock player {parsed} is no longer tracked")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        await self.dl_db.untrack_all_users(guild.id)

    @tasks.loop(minutes=10)
    async def deadlock_update_task(self) -> None:
        """Announce every new Deadlock match (ranked and normal) per tracked player."""
        try:
            logger.info("♻️ Starting Deadlock update loop")
            tracked_users = await self.dl_db.get_all_tracked_users()
            # Cycle-local: each distinct guild's config is read at most once per
            # cycle, filled lazily so guilds with no new match cost no read.
            channel_cache = {}
            for user in tracked_users:
                account_id = user.get("account_id")
                guild_ids = user.get("guild_ids") or []
                # Guard each player so one API/DB error never aborts the cycle.
                try:
                    history = await get_match_history(self.bot.session, account_id)
                    fresh = new_matches(history, user.get("last_match_id"))
                    if not fresh:
                        # Also seeds a missing pointer without announcing.
                        if user.get("last_match_id") is None:
                            seed = newest_match_id(history)
                            if seed is not None:
                                await self.dl_db.update_player_data(
                                    account_id, {"last_match_id": seed}
                                )
                        await asyncio.sleep(1.5)
                        continue
                    # Hero names are resolved before the pointer moves. get_hero_name
                    # never raises: a failed lookup falls back to a "Hero #id" label.
                    named = [
                        (
                            entry,
                            await get_hero_name(self.bot.session, entry.get("hero_id")),
                        )
                        for entry in fresh
                    ]
                    channel_ids = {}
                    for guild in guild_ids:
                        if guild not in channel_cache:
                            channel_cache[guild] = await self._channel_id(guild)
                        channel_ids[guild] = channel_cache[guild]
                    # The pointer is per player, so one failed guild read holds the
                    # whole player (no pointer, no posts); the matches go out next
                    # cycle, when the cache is fresh and the read is retried.
                    # Trade-off: a guild read that fails every cycle holds that player,
                    # healthy guilds included, every cycle with a warning. The matches
                    # are retried, and the 5-match cap logs whatever it drops.
                    if any(c is _READ_FAILED for c in channel_ids.values()):
                        logger.warning(
                            f"⚠️ Holding Deadlock {account_id} this cycle: "
                            "guild config read failed"
                        )
                        await asyncio.sleep(1.5)
                        continue
                    # Deliberately written before the guild-send loop: a failed send
                    # is a silent, non-retried miss rather than a duplicate later.
                    await self.dl_db.update_player_data(
                        account_id, {"last_match_id": newest_match_id(history)}
                    )
                    for entry, hero_name in named:
                        for guild, channel_id in channel_ids.items():
                            await self._announce(
                                guild, channel_id, entry, hero_name, account_id
                            )
                    # Stay well under the API rate limit.
                    await asyncio.sleep(1.5)
                except LiveLOLError as e:
                    logger.warning(f"⚠️ Skipping Deadlock {account_id} this cycle: {e}")
                except Exception as e:
                    logger.exception(f"❌ ERROR processing Deadlock {account_id}: {e}")
        except Exception as e:
            logger.exception(f"❌ ERROR: {e}")

    async def _channel_id(self, guild):
        """The guild's channel id, None when none is set, _READ_FAILED on error."""
        try:
            return await self.dl_db.get_channel_id(guild)
        except Exception as e:
            logger.exception(f"❌ ERROR reading channel config for {guild}: {e}")
            return _READ_FAILED

    async def _announce(self, guild, channel_id, entry, hero_name, account_id):
        """Post one match to one guild; a failure there never blocks other guilds."""
        if channel_id is None:
            return
        try:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                return
            view = DeadlockMatchView(entry, hero_name, f"Deadlock {account_id}")
            message = await channel.send(embed=view.create_minimized_embed(), view=view)
            view.message = message
        except Exception as e:
            logger.exception(f"❌ ERROR announcing Deadlock match in {guild}: {e}")

    @deadlock_update_task.before_loop
    async def before_deadlock_task(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Deadlock(bot))
