"""Regression test for the cogs/management.py cooldown message.

A stray backslash-continuation inside the f-string used to splice the next
source line's leading indentation into the message text sent to Discord
(e.g. "too fast.                     Try again in..."). This pins the fix:
the two sentences join with a single space and no embedded whitespace run.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from discord.ext import commands

from cogs.management import Management


def _make_ctx():
    ctx = MagicMock()
    ctx.command = "track"
    ctx.guild.id = 123
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_cooldown_message_has_no_embedded_whitespace_run():
    cog = Management(bot=MagicMock())
    ctx = _make_ctx()
    error = commands.CommandOnCooldown(
        cooldown=MagicMock(),
        retry_after=4.2,
        type=commands.BucketType.user,
    )

    await cog.on_command_error(ctx, error)

    embed = ctx.send.call_args.kwargs["embed"]
    assert embed.description == "You're using 'track' too fast. Try again in 4.2s."
    assert "  " not in embed.description
    assert "\n" not in embed.description
