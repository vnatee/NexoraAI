from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from core.attachment_store import AttachmentRecord
from mongo_table_connecters import chat_attachment_metadata as metadata


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


class Result:
    def __init__(self, *, modified_count=0, deleted_count=0):
        self.modified_count = modified_count
        self.deleted_count = deleted_count


class Cursor:
    def __init__(self, items):
        self.items = items

    def sort(self, key, direction):
        self.items.sort(key=lambda item: item[key], reverse=direction < 0)
        return self

    def limit(self, count):
        self.items = self.items[:count]
        return self

    def __iter__(self):
        return iter(self.items)


class MemoryCollection:
    def __init__(self):
        self.items = {}
        self.indexes = []

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
            elif actual != expected:
                return False
        return True

    def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))

    def insert_one(self, item):
        self.items[item["_id"]] = deepcopy(item)

    def find_one(self, query):
        return next((deepcopy(item) for item in self.items.values() if self._matches(item, query)), None)

    def find(self, query):
        return Cursor([deepcopy(item) for item in self.items.values() if self._matches(item, query)])

    def update_one(self, query, update):
        item = next((item for item in self.items.values() if self._matches(item, query)), None)
        if not item:
            return Result()
        item.update(update.get("$set") or {})
        return Result(modified_count=1)

    def delete_many(self, query):
        identifiers = [key for key, item in self.items.items() if self._matches(item, query)]
        for identifier in identifiers:
            del self.items[identifier]
        return Result(deleted_count=len(identifiers))


@pytest.fixture
def collection(monkeypatch):
    value = MemoryCollection()
    monkeypatch.setattr(metadata, "collection", value)
    monkeypatch.setattr(metadata, "_now", lambda: NOW)
    return value


def record(*, attachment_id="attachment-1", owner_id="owner-1", conversation_id="conversation-1", expires_in=24):
    return AttachmentRecord(
        attachment_id=attachment_id,
        owner_id=owner_id,
        conversation_id=conversation_id,
        filename="requirements.pdf",
        content_type="application/pdf",
        size=128,
        sha256="a" * 64,
        created_at=NOW.isoformat(),
        expires_at=(NOW + timedelta(hours=expires_in)).isoformat(),
    )


def test_create_and_read_metadata_requires_exact_owner_and_conversation(collection):
    created = metadata.create_attachment_metadata(
        record(), storage_backend="local", storage_key="opaque/storage-key"
    )

    assert created["status"] == "stored"
    assert metadata.get_attachment_metadata(
        "attachment-1", owner_id="owner-1", conversation_id="conversation-1"
    )
    assert metadata.get_attachment_metadata(
        "attachment-1", owner_id="owner-2", conversation_id="conversation-1"
    ) is None
    assert metadata.get_attachment_metadata(
        "attachment-1", owner_id="owner-1", conversation_id="conversation-2"
    ) is None


def test_list_excludes_other_conversations_and_expired_records(collection):
    metadata.create_attachment_metadata(record(), storage_backend="local", storage_key="key-1")
    metadata.create_attachment_metadata(
        record(attachment_id="attachment-2", conversation_id="conversation-2"),
        storage_backend="local",
        storage_key="key-2",
    )
    metadata.create_attachment_metadata(
        record(attachment_id="attachment-3", expires_in=1),
        storage_backend="local",
        storage_key="key-3",
    )
    collection.items["attachment-3"]["expires_at"] = NOW - timedelta(seconds=1)

    items = metadata.list_attachment_metadata(owner_id="owner-1", conversation_id="conversation-1", now=NOW)
    assert [item["_id"] for item in items] == ["attachment-1"]


def test_status_and_soft_delete_are_acl_scoped(collection):
    metadata.create_attachment_metadata(record(), storage_backend="local", storage_key="key-1")

    assert metadata.update_attachment_status(
        "attachment-1",
        owner_id="owner-2",
        conversation_id="conversation-1",
        status="ready",
    ) is None
    failed = metadata.update_attachment_status(
        "attachment-1",
        owner_id="owner-1",
        conversation_id="conversation-1",
        status="failed",
        error_code="Parser failed: private content",
        chunk_count=3,
        extracted_characters=450,
    )
    assert failed["error_code"] == "Parser_failed_private_content"
    assert failed["chunk_count"] == 3
    assert failed["extracted_characters"] == 450
    assert not metadata.soft_delete_attachment_metadata(
        "attachment-1", owner_id="owner-1", conversation_id="wrong"
    )
    assert metadata.soft_delete_attachment_metadata(
        "attachment-1", owner_id="owner-1", conversation_id="conversation-1"
    )
    assert metadata.get_attachment_metadata(
        "attachment-1", owner_id="owner-1", conversation_id="conversation-1"
    ) is None


def test_explicit_cleanup_removes_expired_metadata(collection):
    metadata.create_attachment_metadata(record(), storage_backend="local", storage_key="key-1")
    metadata.create_attachment_metadata(
        record(attachment_id="attachment-2", expires_in=1),
        storage_backend="local",
        storage_key="key-2",
    )
    collection.items["attachment-2"]["expires_at"] = NOW - timedelta(seconds=1)

    assert metadata.delete_expired_attachment_metadata(now=NOW) == 1
    assert set(collection.items) == {"attachment-1"}


def test_serializer_does_not_expose_owner_storage_key_or_hash(collection):
    item = metadata.create_attachment_metadata(record(), storage_backend="local", storage_key="secret-path")
    serialized = metadata.serialize_attachment_metadata(item)

    assert serialized["id"] == "attachment-1"
    assert "owner_id" not in serialized
    assert "conversation_id" not in serialized
    assert "storage_key" not in serialized
    assert "sha256" not in serialized


def test_indexes_include_owner_conversation_and_optional_ttl(collection):
    assert metadata.ensure_attachment_metadata_indexes()
    assert collection.indexes[0][1]["name"] == "attachment_owner_conversation"
    assert collection.indexes[1][1] == {"expireAfterSeconds": 0, "name": "attachment_expiry"}
    assert collection.indexes[2][1]["unique"] is True
    assert collection.indexes[2][1]["name"] == "attachment_upload_idempotency"


def test_create_rejects_invalid_expiry(collection):
    with pytest.raises(ValueError, match="expiry"):
        metadata.create_attachment_metadata(
            record(expires_in=0), storage_backend="local", storage_key="key"
        )


def test_upload_id_lookup_is_acl_scoped_and_serializes_safe_processing_metadata(collection):
    item = metadata.create_attachment_metadata(
        record(),
        storage_backend="local",
        storage_key="key",
        upload_id="9aee2161-d67f-45a1-b4a5-7d2042dd1c26",
        page_count=12,
        scan_status="clean",
    )

    assert metadata.get_attachment_metadata_by_upload_id(
        item["upload_id"],
        owner_id="owner-1",
        conversation_id="conversation-1",
    )
    assert metadata.get_attachment_metadata_by_upload_id(
        item["upload_id"],
        owner_id="owner-2",
        conversation_id="conversation-1",
    ) is None
    serialized = metadata.serialize_attachment_metadata(item)
    assert serialized["page_count"] == 12
    assert serialized["scan_status"] == "clean"
    assert "upload_id" not in serialized
