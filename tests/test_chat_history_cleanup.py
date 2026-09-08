import pytest
from quart import Quart

from chat_history import cosmosdb
from config import CONFIG_CHAT_ATTACHMENT_STORE


class _Store:
    def __init__(self, events: list[str], *, fail: bool = False):
        self.events = events
        self.fail = fail

    async def delete(self, attachment_id: str, *, owner_id: str, conversation_id: str) -> None:
        self.events.append(f"object:{attachment_id}")
        if self.fail:
            raise RuntimeError("storage unavailable")


async def _direct_call(function, *args, **kwargs):
    return function(*args, **kwargs)


@pytest.mark.asyncio
async def test_conversation_cleanup_deletes_dependencies_before_history_and_audits(monkeypatch):
    events: list[str] = []
    application = Quart(__name__)
    application.config[CONFIG_CHAT_ATTACHMENT_STORE] = _Store(events)
    monkeypatch.setattr(cosmosdb.asyncio, "to_thread", _direct_call)
    monkeypatch.setattr(
        cosmosdb,
        "list_conversation_attachment_metadata",
        lambda **_kwargs: [{"_id": "attachment-1"}],
    )
    monkeypatch.setattr(
        cosmosdb,
        "delete_conversation_attachment_chunks",
        lambda **_kwargs: events.append("chunks") or 2,
    )
    monkeypatch.setattr(
        cosmosdb,
        "delete_conversation_attachment_metadata",
        lambda **_kwargs: events.append("metadata") or 1,
    )
    monkeypatch.setattr(
        cosmosdb,
        "delete_session",
        lambda *_args: events.append("history") or True,
    )
    monkeypatch.setattr(
        cosmosdb,
        "insert_deletion_audit",
        lambda **kwargs: events.append(
            f"audit:{kwargs['reason']}:{kwargs['conversation_count']}:{kwargs['attachment_count']}"
        ),
    )

    async with application.app_context():
        deleted = await cosmosdb._delete_database_history_session(
            {
                "_id": "11111111-1111-4111-8111-111111111111",
                "owner_id": "user-1",
                "conversation_id": "22222222-2222-4222-8222-222222222222",
            },
            actor_id="user-1",
            reason="user",
        )

    assert deleted is True
    assert events == [
        "object:attachment-1",
        "chunks",
        "metadata",
        "history",
        "audit:user:1:1",
    ]


@pytest.mark.asyncio
async def test_conversation_cleanup_keeps_history_when_object_deletion_fails(monkeypatch):
    events: list[str] = []
    application = Quart(__name__)
    application.config[CONFIG_CHAT_ATTACHMENT_STORE] = _Store(events, fail=True)
    monkeypatch.setattr(cosmosdb.asyncio, "to_thread", _direct_call)
    monkeypatch.setattr(
        cosmosdb,
        "list_conversation_attachment_metadata",
        lambda **_kwargs: [{"_id": "attachment-1"}],
    )
    monkeypatch.setattr(cosmosdb, "delete_session", lambda *_args: events.append("history") or True)
    monkeypatch.setattr(cosmosdb, "insert_deletion_audit", lambda **_kwargs: events.append("audit"))

    async with application.app_context():
        with pytest.raises(RuntimeError, match="storage unavailable"):
            await cosmosdb._delete_database_history_session(
                {
                    "_id": "11111111-1111-4111-8111-111111111111",
                    "owner_id": "user-1",
                    "conversation_id": "22222222-2222-4222-8222-222222222222",
                },
                actor_id="system",
                reason="retention",
            )

    assert events == ["object:attachment-1"]
