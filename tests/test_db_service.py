"""Tests for utils/db_service.py untrack paths.

Firestore expands a dotted field path like ``server_info.<gid>`` written via
``.set(payload, merge=True)`` into a real NESTED map - ``to_dict()`` returns
``{"server_info": {"<gid>": {...}}}``, never a flat ``"server_info.<gid>"``
key. These tests pin the untrack methods to removing the right nested entry
rather than a flat key that never exists.
"""

from unittest.mock import MagicMock

import pytest

from utils.db_service import DatabaseService
from utils.exceptions import DatabaseError


def _make_doc(data):
    doc = MagicMock()
    doc.exists = True
    doc.to_dict.return_value = data
    return doc


def _make_service(data):
    doc_ref = MagicMock()
    doc_ref.get.return_value = _make_doc(data)
    db = MagicMock()
    db.collection.return_value.document.return_value = doc_ref
    return DatabaseService(db), doc_ref


@pytest.mark.asyncio
async def test_untrack_user_removes_only_that_guilds_server_info():
    data = {
        "guild_ids": ["111", "222"],
        "server_info": {
            "111": {"added_by": 1},
            "222": {"added_by": 2},
        },
    }
    service, doc_ref = _make_service(data)

    await service.untrack_user(guild_id=111, riot_id="Foo#NA1", puuid="p1")

    doc_ref.set.assert_called_once()
    written = doc_ref.set.call_args.args[0]
    assert written["guild_ids"] == ["222"]
    assert written["server_info"] == {"222": {"added_by": 2}}
    doc_ref.delete.assert_not_called()


@pytest.mark.asyncio
async def test_untrack_user_deletes_doc_when_last_guild_removed():
    data = {
        "guild_ids": ["111"],
        "server_info": {"111": {"added_by": 1}},
    }
    service, doc_ref = _make_service(data)

    await service.untrack_user(guild_id=111, riot_id="Foo#NA1", puuid="p1")

    doc_ref.delete.assert_called_once()
    doc_ref.set.assert_not_called()


@pytest.mark.asyncio
async def test_untrack_user_missing_guild_raises_user_not_found():
    data = {"guild_ids": ["222"], "server_info": {"222": {"added_by": 2}}}
    service, doc_ref = _make_service(data)

    with pytest.raises(DatabaseError):
        await service.untrack_user(guild_id=111, riot_id="Foo#NA1", puuid="p1")


@pytest.mark.asyncio
async def test_untrack_all_users_removes_only_that_guilds_server_info():
    data = {
        "guild_ids": ["111", "222"],
        "server_info": {
            "111": {"added_by": 1},
            "222": {"added_by": 2},
        },
    }
    doc = _make_doc(data)
    doc_ref = MagicMock()
    doc.reference = doc_ref
    collection = MagicMock()
    collection.where.return_value.stream.return_value = [doc]
    db = MagicMock()
    db.collection.return_value = collection
    service = DatabaseService(db)

    await service.untrack_all_users(guild_id=111)

    doc_ref.set.assert_called_once()
    written = doc_ref.set.call_args.args[0]
    assert written["guild_ids"] == ["222"]
    assert written["server_info"] == {"222": {"added_by": 2}}
    doc_ref.delete.assert_not_called()
