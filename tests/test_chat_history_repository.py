from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mongo_table_connecters import chat_history

SESSION_ID = "11111111-1111-4111-8111-111111111111"


def test_upsert_history_is_owner_scoped_and_sets_expiry(monkeypatch):
    collection = MagicMock()
    monkeypatch.setattr(chat_history, "collection", collection)
    monkeypatch.setattr(chat_history, "retention_days", lambda _team_id=None: 90)

    chat_history.upsert_session(
        SESSION_ID,
        "user-1",
        [["Question", {"message": {"content": "Answer"}}]],
    )

    query, update = collection.update_one.call_args.args
    assert query == {"_id": SESSION_ID, "owner_id": "user-1"}
    assert update["$set"]["owner_id"] == "user-1"
    assert update["$set"]["expires_at"] > update["$set"]["updated_at"]
    assert collection.update_one.call_args.kwargs["upsert"] is True


def test_upsert_history_rejects_invalid_session_id():
    with pytest.raises(ValueError, match="valid UUID"):
        chat_history.upsert_session("not-an-id", "user-1", [["Question", {}]])


def test_upsert_history_supports_no_expiry(monkeypatch):
    collection = MagicMock()
    monkeypatch.setattr(chat_history, "collection", collection)
    monkeypatch.setattr(chat_history, "retention_days", lambda _team_id=None: 0)

    chat_history.upsert_session(
        SESSION_ID,
        "user-1",
        [["Question", {"message": {"content": "Answer"}}]],
        conversation_id=SESSION_ID,
    )

    assert collection.update_one.call_args.args[1]["$set"]["expires_at"] is None


def test_history_read_and_delete_require_exact_owner(monkeypatch):
    collection = MagicMock()
    collection.find_one.return_value = None
    collection.delete_one.return_value = SimpleNamespace(deleted_count=0)
    monkeypatch.setattr(chat_history, "collection", collection)

    assert chat_history.get_session(SESSION_ID, "user-2") is None
    assert chat_history.delete_session(SESSION_ID, "user-2") is False
    assert collection.find_one.call_args.args[0]["owner_id"] == "user-2"
    assert collection.delete_one.call_args.args[0] == {
        "_id": SESSION_ID,
        "owner_id": "user-2",
    }


def test_cleanup_worker_lists_only_expired_documents(monkeypatch):
    now = datetime(2026, 9, 6, tzinfo=timezone.utc)
    collection = MagicMock()
    collection.find.return_value.limit.return_value = [
        {"_id": SESSION_ID, "owner_id": "user-1", "conversation_id": SESSION_ID}
    ]
    monkeypatch.setattr(chat_history, "collection", collection)

    assert len(chat_history.list_expired_sessions(now)) == 1
    assert collection.find.call_args.args[0] == {
        "expires_at": {"$type": "date", "$lte": now}
    }


def test_team_retention_cannot_exceed_system_policy(monkeypatch):
    collection = MagicMock()
    settings = MagicMock()
    settings.find_one.side_effect = [
        {"retention_days": 30},
    ]
    monkeypatch.setattr(chat_history, "collection", collection)
    monkeypatch.setattr(chat_history, "settings", settings)

    with pytest.raises(ValueError, match="cannot exceed"):
        chat_history.save_retention_days(90, "team-1")
    settings.update_one.assert_not_called()


def test_lowering_system_retention_clamps_team_settings_and_recalculates_expiry(monkeypatch):
    collection = MagicMock()
    collection.distinct.return_value = ["team-1"]
    settings = MagicMock()
    settings.find_one.side_effect = lambda query: (
        {"retention_days": 30}
        if query.get("_id") == chat_history.SYSTEM_SETTINGS_ID
        else {"retention_days": 60}
    )
    monkeypatch.setattr(chat_history, "collection", collection)
    monkeypatch.setattr(chat_history, "settings", settings)

    assert chat_history.save_retention_days(30) == 30
    settings.update_many.assert_called_once()
    assert settings.update_many.call_args.args[0]["$or"] == [
        {"retention_days": 0},
        {"retention_days": {"$gt": 30}},
    ]
    assert collection.update_many.call_count == 2


def test_no_expiry_sets_null_expiry(monkeypatch):
    collection = MagicMock()
    collection.distinct.return_value = []
    settings = MagicMock()
    monkeypatch.setattr(chat_history, "collection", collection)
    monkeypatch.setattr(chat_history, "settings", settings)

    assert chat_history.save_retention_days(0) == 0
    assert collection.update_many.call_args.args[1] == {"$set": {"expires_at": None}}


def test_deletion_audit_contains_metadata_only(monkeypatch):
    audit_collection = MagicMock()
    monkeypatch.setattr(chat_history, "audit_collection", audit_collection)

    chat_history.insert_deletion_audit(
        actor_id="user-1",
        reason="user",
        conversation_count=1,
        attachment_count=2,
    )

    document = audit_collection.insert_one.call_args.args[0]
    assert document["actor_id"] == "user-1"
    assert document["conversation_count"] == 1
    assert document["attachment_count"] == 2
    assert "answers" not in document
    assert "content" not in document


def test_history_indexes_replace_parent_ttl_with_worker_scan_index(monkeypatch):
    collection = MagicMock()
    collection.index_information.return_value = {"_id_": {}, "history_expiry": {}}
    audit_collection = MagicMock()
    monkeypatch.setattr(chat_history, "collection", collection)
    monkeypatch.setattr(chat_history, "audit_collection", audit_collection)

    chat_history.ensure_indexes()

    collection.drop_index.assert_called_once_with("history_expiry")
    assert any(
        call.args == ("expires_at",) and call.kwargs.get("name") == "history_expiry_scan"
        for call in collection.create_index.call_args_list
    )
    audit_collection.create_index.assert_called_once_with(
        "expires_at", expireAfterSeconds=0, name="history_audit_expiry"
    )
