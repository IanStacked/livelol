"""Tests for the Deadlock cog: API parsing, db service, poll loop and commands."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from cogs import deadlock as deadlock_cog
from cogs.deadlock import Deadlock, parse_account_id
from utils import deadlock_api
from utils.db_service import (
    DEADLOCK_TRACKED_USERS_COLLECTION,
    DeadlockDatabaseService,
)
from utils.deadlock_api import (
    DeadlockAPIError,
    badge_name,
    entry_won,
    get_match_history,
    new_matches,
    newest_match_id,
)
from utils.deadlock_ui import DeadlockMatchView
from utils.exceptions import DatabaseError, UserNotFoundError


def _entry(match_id, mode=1, team=0, result=0, **kw):
    base = {
        "match_id": match_id,
        "match_mode": mode,
        "player_team": team,
        "match_result": result,
        "hero_id": 7,
        "player_kills": 5,
        "player_deaths": 2,
        "player_assists": 9,
        "match_duration_s": 1500,
    }
    base.update(kw)
    return base


# API helpers


def test_new_matches_only_newer_oldest_first():
    history = [_entry(30), _entry(20), _entry(10)]
    assert [e["match_id"] for e in new_matches(history, 10)] == [20, 30]


def test_new_matches_without_pointer_is_empty():
    assert new_matches([_entry(30)], None) == []


def test_new_matches_caps_to_newest():
    history = [_entry(i) for i in range(100, 120)]
    got = new_matches(history, 99)
    assert len(got) == deadlock_api.MAX_ANNOUNCE_PER_CYCLE
    assert got[-1]["match_id"] == 119


def test_newest_match_id_ignores_order():
    assert newest_match_id([_entry(5), _entry(9), _entry(7)]) == 9
    assert newest_match_id([]) is None


def test_entry_won_compares_winning_team_to_player_team():
    assert entry_won(_entry(1, team=1, result=1))
    assert not entry_won(_entry(1, team=1, result=0))


def test_badge_name():
    assert badge_name(116) == "Eternus 6"
    assert badge_name(None) is None
    assert badge_name(900) is None


def _session(status, payload):
    response = AsyncMock()
    response.status = status
    response.json.return_value = payload
    cm = MagicMock()
    cm.__aenter__.return_value = response
    cm.__aexit__.return_value = None
    session = MagicMock()
    session.get.return_value = cm
    return session


@pytest.mark.asyncio
async def test_get_match_history_never_force_refetches():
    session = _session(200, [_entry(1)])
    assert await get_match_history(session, 42) == [_entry(1)]
    url = session.get.call_args.args[0]
    assert url.endswith("/v1/players/42/match-history")
    assert "force_refetch" not in url
    assert "params" not in session.get.call_args.kwargs


@pytest.mark.asyncio
async def test_get_match_history_429_uses_fallback_body():
    session = _session(429, [_entry(1)])
    assert await get_match_history(session, 42) == [_entry(1)]


@pytest.mark.asyncio
async def test_get_match_history_error_status_raises():
    with pytest.raises(DeadlockAPIError):
        await get_match_history(_session(500, None), 42)


# Views


def test_ranked_embed_shows_badge_and_estimated_delta():
    entry = _entry(
        1, mode=4, team=0, result=1, ranked_delta=-300, ranked_display_badge=116
    )
    text = DeadlockMatchView(
        entry, "Infernus", "Deadlock 1"
    ).minimized_embed.description
    assert "lost a ranked match" in text
    assert "Eternus 6" in text
    assert "Estimated rank progress: -300" in text
    assert "Infernus (5/2/9)" in text


def test_normal_embed_has_win_hero_kda_and_no_rank():
    entry = _entry(1, mode=1, team=1, result=1)
    text = DeadlockMatchView(
        entry, "Infernus", "Deadlock 1"
    ).minimized_embed.description
    assert "won a normal match" in text
    assert "Infernus (5/2/9)" in text
    assert "rank" not in text.lower().replace("ranked", "")


# DB service


def _service(doc_data=None):
    doc_ref = MagicMock()
    doc = MagicMock()
    doc.exists = doc_data is not None
    doc.to_dict.return_value = doc_data
    doc_ref.get.return_value = doc
    db = MagicMock()
    db.collection.return_value.document.return_value = doc_ref
    return DeadlockDatabaseService(db), doc_ref, db


@pytest.mark.asyncio
async def test_track_user_seeds_pointer_on_first_sight():
    service, doc_ref, db = _service(None)
    await service.track_user(111, 9, 42, 500)
    db.collection.assert_called_with(DEADLOCK_TRACKED_USERS_COLLECTION)
    payload = doc_ref.set.call_args.args[0]
    assert payload["last_match_id"] == 500
    assert payload["server_info.111"] == {"added_by": 9}


@pytest.mark.asyncio
async def test_track_user_second_server_does_not_rewind_pointer():
    service, doc_ref, _ = _service({"last_match_id": 400, "guild_ids": ["222"]})
    await service.track_user(111, 9, 42, 500)
    assert "last_match_id" not in doc_ref.set.call_args.args[0]


@pytest.mark.asyncio
async def test_untrack_user_removes_only_that_guild():
    data = {
        "guild_ids": ["111", "222"],
        "server_info": {"111": {"added_by": 1}, "222": {"added_by": 2}},
    }
    service, doc_ref, _ = _service(data)
    await service.untrack_user(111, 42)
    written = doc_ref.set.call_args.args[0]
    assert written["guild_ids"] == ["222"]
    assert written["server_info"] == {"222": {"added_by": 2}}


@pytest.mark.asyncio
async def test_untrack_user_deletes_doc_when_last_guild():
    service, doc_ref, _ = _service({"guild_ids": ["111"], "server_info": {}})
    await service.untrack_user(111, 42)
    doc_ref.delete.assert_called_once()


@pytest.mark.asyncio
async def test_untrack_user_not_tracked_raises():
    service, _, _ = _service(None)
    with pytest.raises(UserNotFoundError):
        await service.untrack_user(111, 42)
    service, doc_ref, _ = _service({"guild_ids": ["222"]})
    with pytest.raises(UserNotFoundError):
        await service.untrack_user(111, 42)
    doc_ref.set.assert_not_called()


@pytest.mark.asyncio
async def test_untrack_user_wraps_unexpected_error():
    service, doc_ref, _ = _service({})
    doc_ref.get.side_effect = RuntimeError("down")
    with pytest.raises(DatabaseError):
        await service.untrack_user(111, 42)


@pytest.mark.asyncio
async def test_untrack_all_users_removes_only_that_guild():
    doc = MagicMock()
    doc.to_dict.return_value = {
        "guild_ids": ["111", "222"],
        "server_info": {"111": {"added_by": 1}, "222": {"added_by": 2}},
    }
    db = MagicMock()
    db.collection.return_value.where.return_value.stream.return_value = [doc]
    await DeadlockDatabaseService(db).untrack_all_users(111)
    written = doc.reference.set.call_args.args[0]
    assert written["guild_ids"] == ["222"]
    assert written["server_info"] == {"222": {"added_by": 2}}


# Cog


def test_parse_account_id():
    assert parse_account_id(" 12345 ") == 12345
    assert parse_account_id("abc") is None
    assert parse_account_id("0") is None
    assert parse_account_id("-5") is None


def _cog(users, last_channel=True):
    cog = object.__new__(Deadlock)
    cog.bot = MagicMock()
    cog.bot.db_service.get_guild_config = AsyncMock(return_value=10)
    channel = MagicMock()
    channel.send = AsyncMock()
    cog.bot.get_channel.return_value = channel if last_channel else None
    cog.dl_db = MagicMock()
    cog.dl_db.get_all_tracked_users = AsyncMock(return_value=users)
    cog.dl_db.update_player_data = AsyncMock()
    return cog, channel


@pytest.fixture(autouse=True)
def _no_sleep_no_net(monkeypatch):
    monkeypatch.setattr(deadlock_cog.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(
        deadlock_cog, "get_hero_name", AsyncMock(return_value="Infernus")
    )


async def _run_loop(cog, history, monkeypatch):
    monkeypatch.setattr(
        deadlock_cog, "get_match_history", AsyncMock(return_value=history)
    )
    await Deadlock.deadlock_update_task.coro(cog)


@pytest.mark.asyncio
async def test_loop_announces_ranked_and_normal_and_advances_pointer(monkeypatch):
    user = {"account_id": 42, "guild_ids": ["111"], "last_match_id": 10}
    cog, channel = _cog([user])
    history = [_entry(30, mode=4, ranked_delta=20), _entry(20, mode=1), _entry(10)]
    await _run_loop(cog, history, monkeypatch)
    assert channel.send.await_count == 2
    cog.dl_db.update_player_data.assert_awaited_once_with(42, {"last_match_id": 30})


@pytest.mark.asyncio
async def test_loop_no_new_match_posts_nothing(monkeypatch):
    user = {"account_id": 42, "guild_ids": ["111"], "last_match_id": 30}
    cog, channel = _cog([user])
    await _run_loop(cog, [_entry(30), _entry(20)], monkeypatch)
    channel.send.assert_not_awaited()
    cog.dl_db.update_player_data.assert_not_awaited()


@pytest.mark.asyncio
async def test_loop_missing_pointer_seeds_without_announcing(monkeypatch):
    user = {"account_id": 42, "guild_ids": ["111"]}
    cog, channel = _cog([user])
    await _run_loop(cog, [_entry(30), _entry(20)], monkeypatch)
    channel.send.assert_not_awaited()
    cog.dl_db.update_player_data.assert_awaited_once_with(42, {"last_match_id": 30})


@pytest.mark.asyncio
async def test_loop_pointer_written_before_send_and_send_failure_not_retried(
    monkeypatch,
):
    user = {"account_id": 42, "guild_ids": ["111"], "last_match_id": 10}
    cog, channel = _cog([user])
    channel.send.side_effect = RuntimeError("discord down")
    await _run_loop(cog, [_entry(20)], monkeypatch)
    cog.dl_db.update_player_data.assert_awaited_once_with(42, {"last_match_id": 20})


@pytest.mark.asyncio
async def test_loop_api_error_for_one_player_does_not_abort_cycle(monkeypatch):
    users = [
        {"account_id": 1, "guild_ids": ["111"], "last_match_id": 1},
        {"account_id": 2, "guild_ids": ["111"], "last_match_id": 1},
    ]
    cog, channel = _cog(users)
    fetch = AsyncMock(side_effect=[DeadlockAPIError("boom"), [_entry(5)]])
    monkeypatch.setattr(deadlock_cog, "get_match_history", fetch)
    await Deadlock.deadlock_update_task.coro(cog)
    assert channel.send.await_count == 1


@pytest.mark.asyncio
async def test_loop_guild_without_channel_config_is_skipped(monkeypatch):
    user = {"account_id": 42, "guild_ids": ["111"], "last_match_id": 10}
    cog, channel = _cog([user])
    cog.bot.db_service.get_guild_config = AsyncMock(return_value=None)
    await _run_loop(cog, [_entry(20)], monkeypatch)
    channel.send.assert_not_awaited()


def _ctx():
    ctx = MagicMock()
    ctx.guild.id = 111
    ctx.author.id = 9
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_trackdl_seeds_pointer_from_newest_match(monkeypatch):
    cog, _ = _cog([])
    cog.dl_db.track_user = AsyncMock()
    monkeypatch.setattr(
        deadlock_cog,
        "get_match_history",
        AsyncMock(return_value=[_entry(7), _entry(9)]),
    )
    ctx = _ctx()
    await Deadlock.trackdl.callback(cog, ctx, "42")
    cog.dl_db.track_user.assert_awaited_once_with(111, 9, 42, 9)


@pytest.mark.asyncio
async def test_trackdl_empty_history_is_not_found(monkeypatch):
    cog, _ = _cog([])
    cog.dl_db.track_user = AsyncMock()
    monkeypatch.setattr(deadlock_cog, "get_match_history", AsyncMock(return_value=[]))
    with pytest.raises(DeadlockAPIError):
        await Deadlock.trackdl.callback(cog, _ctx(), "42")
    cog.dl_db.track_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_trackdl_bad_id_is_rejected_without_api_call(monkeypatch):
    cog, _ = _cog([])
    fetch = AsyncMock()
    monkeypatch.setattr(deadlock_cog, "get_match_history", fetch)
    ctx = _ctx()
    await Deadlock.trackdl.callback(cog, ctx, "notanumber")
    fetch.assert_not_awaited()
    assert "Invalid input" in ctx.send.await_args.args[0]


@pytest.mark.asyncio
async def test_untrackdl_calls_service():
    cog, _ = _cog([])
    cog.dl_db.untrack_user = AsyncMock()
    await Deadlock.untrackdl.callback(cog, _ctx(), "42")
    cog.dl_db.untrack_user.assert_awaited_once_with(111, 42)
