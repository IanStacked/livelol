"""Tests for the bot.py `!update` command.

bot.py runs side effects at import time (`setup_sentry()` and
`db = database_startup()` via `MyBot()`), which is why nothing else imports it.
The fixture stubs those two before importing, then drives `update.callback`
directly against a fake context and a fake db_service.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def bot_module(monkeypatch):
    # Neutralize the heavy import-time side effects before importing bot.
    monkeypatch.setattr("database.database_startup", lambda: MagicMock())
    monkeypatch.setattr("utils.sentry_config.setup_sentry", lambda: None)

    import sys

    sys.modules.pop("bot", None)
    import bot

    # Keep the per-user rate-limit sleep from actually sleeping.
    monkeypatch.setattr(bot.asyncio, "sleep", AsyncMock())
    # The embed/view path needs no real rendering for these tests.
    monkeypatch.setattr(bot, "MatchDetailsView", MagicMock())
    return bot


def _make_ctx():
    ctx = MagicMock()
    ctx.guild.id = 123
    ctx.send = AsyncMock()
    return ctx


async def _run_update(bot_module, ctx):
    await bot_module.update.callback(ctx)


@pytest.mark.asyncio
async def test_update_with_no_tracked_users_short_circuits(bot_module):
    bot_module.bot.db_service = MagicMock()
    bot_module.bot.db_service.get_guild_tracked_users = AsyncMock(return_value=[])
    bot_module.bot.db_service.update_ranked_data = AsyncMock()
    ctx = _make_ctx()

    await _run_update(bot_module, ctx)

    ctx.send.assert_awaited_once()
    assert "No users tracked" in ctx.send.await_args.args[0]
    bot_module.bot.db_service.update_ranked_data.assert_not_called()


@pytest.mark.asyncio
async def test_update_advances_streak_on_new_match(bot_module, monkeypatch):
    user = {
        "puuid": "p1",
        "region": "na1",
        "riot_id": "Player#NA1",
        "streak": 2,
        "last_match_id": "OLD_MATCH",
    }
    bot_module.bot.db_service = MagicMock()
    bot_module.bot.db_service.get_guild_tracked_users = AsyncMock(return_value=[user])
    bot_module.bot.db_service.update_ranked_data = AsyncMock()

    monkeypatch.setattr(bot_module, "get_ranked_info", AsyncMock(return_value={}))
    monkeypatch.setattr(bot_module, "parse_rank_info", lambda *_: {"tier": "GOLD"})
    monkeypatch.setattr(bot_module, "rank_difference", lambda *_: True)
    monkeypatch.setattr(bot_module, "get_recent_match_info", AsyncMock(return_value={}))
    monkeypatch.setattr(
        bot_module,
        "extract_match_info",
        lambda *_: {"match_id": "NEW_MATCH", "win": True},
    )
    ctx = _make_ctx()

    await _run_update(bot_module, ctx)

    bot_module.bot.db_service.update_ranked_data.assert_awaited_once()
    puuid, data = bot_module.bot.db_service.update_ranked_data.await_args.args
    assert puuid == "p1"
    # A genuinely new match advances the pointer and the streak.
    assert data["last_match_id"] == "NEW_MATCH"
    assert data["streak"] == 3


@pytest.mark.asyncio
async def test_update_does_not_clobber_last_match_id_with_none(bot_module, monkeypatch):
    # A match DTO missing metadata.matchId yields match_id=None; the write must
    # preserve the existing last_match_id rather than overwrite it with None.
    user = {
        "puuid": "p1",
        "region": "na1",
        "riot_id": "Player#NA1",
        "streak": 2,
        "last_match_id": "OLD_MATCH",
    }
    bot_module.bot.db_service = MagicMock()
    bot_module.bot.db_service.get_guild_tracked_users = AsyncMock(return_value=[user])
    bot_module.bot.db_service.update_ranked_data = AsyncMock()

    monkeypatch.setattr(bot_module, "get_ranked_info", AsyncMock(return_value={}))
    monkeypatch.setattr(bot_module, "parse_rank_info", lambda *_: {"tier": "GOLD"})
    monkeypatch.setattr(bot_module, "rank_difference", lambda *_: True)
    monkeypatch.setattr(bot_module, "get_recent_match_info", AsyncMock(return_value={}))
    monkeypatch.setattr(
        bot_module,
        "extract_match_info",
        lambda *_: {"match_id": None, "win": True},
    )
    ctx = _make_ctx()

    await _run_update(bot_module, ctx)

    bot_module.bot.db_service.update_ranked_data.assert_awaited_once()
    _puuid, data = bot_module.bot.db_service.update_ranked_data.await_args.args
    # last_match_id must NOT be present (so Firestore's partial update leaves the
    # stored value untouched), and the streak stays put on a repeat/no-op match.
    assert "last_match_id" not in data
    assert data["streak"] == 2
