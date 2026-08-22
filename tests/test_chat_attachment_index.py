from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from core.attachment_extraction import ExtractedChunk
from core.attachment_store import AttachmentRecord
from mongo_table_connecters import chat_attachment_index as attachment_index


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


class Result:
    def __init__(self, deleted_count=0):
        self.deleted_count = deleted_count


class Cursor:
    def __init__(self, items):
        self.items = items

    def limit(self, count):
        self.items = self.items[:count]
        return self

    def __iter__(self):
        return iter(self.items)


class MemoryCollection:
    def __init__(self):
        self.items = {}
        self.indexes = []
        self.fail_insert = False

    @staticmethod
    def _matches(item, query):
        for key, expected in query.items():
            actual = item.get(key)
            if isinstance(expected, dict) and "$gt" in expected:
                if actual is None or actual <= expected["$gt"]:
                    return False
            elif isinstance(expected, dict) and "$lte" in expected:
                if actual is None or actual > expected["$lte"]:
                    return False
            elif isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
            elif actual != expected:
                return False
        return True

    def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))

    def insert_many(self, documents, ordered):
        assert ordered is True
        for document in documents:
            self.items[document["_id"]] = deepcopy(document)
            if self.fail_insert:
                raise RuntimeError("insert failed")

    def find(self, query):
        return Cursor([deepcopy(item) for item in self.items.values() if self._matches(item, query)])

    def delete_many(self, query):
        identifiers = [key for key, item in self.items.items() if self._matches(item, query)]
        for identifier in identifiers:
            del self.items[identifier]
        return Result(len(identifiers))


@pytest.fixture
def collection(monkeypatch):
    value = MemoryCollection()
    monkeypatch.setattr(attachment_index, "collection", value)
    monkeypatch.setattr(attachment_index, "_now", lambda: NOW)
    return value


def _record(attachment_id="attachment-1", conversation_id="conversation-1"):
    return AttachmentRecord(
        attachment_id=attachment_id,
        owner_id="owner-1",
        conversation_id=conversation_id,
        filename="requirements.pdf",
        content_type="application/pdf",
        size=100,
        sha256="a" * 64,
        created_at=NOW.isoformat(),
        expires_at=(NOW + timedelta(hours=24)).isoformat(),
    )


def _chunks(prefix=""):
    return [
        ExtractedChunk(0, 1, "1", f"{prefix}Encryption at rest is required."),
        ExtractedChunk(1, 2, "2", f"{prefix}Backups are retained for thirty days."),
    ]


def test_replace_and_search_are_owner_conversation_and_attachment_scoped(collection):
    attachment_index.replace_attachment_chunks(_record(), _chunks())
    attachment_index.replace_attachment_chunks(
        _record("attachment-2", "conversation-2"),
        _chunks("Other conversation: "),
    )

    results = attachment_index.search_attachment_chunks(
        owner_id="owner-1",
        conversation_id="conversation-1",
        query="encryption required",
        now=NOW,
    )
    assert [(item.attachment_id, item.page_number) for item in results] == [("attachment-1", 1)]
    assert attachment_index.search_attachment_chunks(
        owner_id="owner-2",
        conversation_id="conversation-1",
        query="encryption",
        now=NOW,
    ) == []
    assert attachment_index.search_attachment_chunks(
        owner_id="owner-1",
        conversation_id="conversation-1",
        query="encryption",
        attachment_ids=["attachment-2"],
        now=NOW,
    ) == []


def test_search_excludes_expired_chunks_and_ranks_exact_phrase_first(collection):
    attachment_index.replace_attachment_chunks(_record(), _chunks())
    collection.items["attachment-1:0001"]["text"] = "Encryption is mentioned without the exact phrase."
    results = attachment_index.search_attachment_chunks(
        owner_id="owner-1",
        conversation_id="conversation-1",
        query="encryption at rest",
        now=NOW,
    )
    assert results[0].page_number == 1

    for item in collection.items.values():
        item["expires_at"] = NOW - timedelta(seconds=1)
    assert attachment_index.search_attachment_chunks(
        owner_id="owner-1",
        conversation_id="conversation-1",
        query="encryption",
        now=NOW,
    ) == []


def test_replace_cleans_partial_insert_on_failure(collection):
    collection.fail_insert = True
    with pytest.raises(RuntimeError, match="insert failed"):
        attachment_index.replace_attachment_chunks(_record(), _chunks())
    assert collection.items == {}


def test_delete_and_expiry_cleanup_are_scoped(collection):
    attachment_index.replace_attachment_chunks(_record(), _chunks())
    attachment_index.replace_attachment_chunks(_record("attachment-2"), _chunks())
    assert attachment_index.delete_attachment_chunks(
        "attachment-1",
        owner_id="owner-2",
        conversation_id="conversation-1",
    ) == 0
    assert attachment_index.delete_attachment_chunks(
        "attachment-1",
        owner_id="owner-1",
        conversation_id="conversation-1",
    ) == 2
    for item in collection.items.values():
        item["expires_at"] = NOW - timedelta(seconds=1)
    assert attachment_index.delete_expired_attachment_chunks(now=NOW) == 2


def test_attachment_index_defines_scope_position_and_ttl_indexes(collection):
    assert attachment_index.ensure_attachment_index_indexes()
    assert [options["name"] for _, options in collection.indexes] == [
        "attachment_chunk_scope",
        "attachment_chunk_position",
        "attachment_chunk_expiry",
    ]


@pytest.mark.asyncio
async def test_mongo_attachment_index_exposes_async_contract(collection):
    index = attachment_index.MongoAttachmentIndex()
    assert await index.replace_attachment(_record(), _chunks()) == 2
    results = await index.search(
        owner_id="owner-1",
        conversation_id="conversation-1",
        query="backups retained",
    )
    assert results[0].page_label == "2"
