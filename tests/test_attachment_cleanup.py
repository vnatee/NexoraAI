from datetime import datetime, timezone

import pytest

from core.attachment_cleanup import cleanup_expired_attachments


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


class FakeStore:
    def __init__(self):
        self.now = None

    async def delete_expired(self, *, now=None):
        self.now = now
        return 3


class FakeIndex:
    def __init__(self):
        self.now = None

    async def delete_expired(self, *, now=None):
        self.now = now
        return 4


@pytest.mark.asyncio
async def test_cleanup_deletes_objects_before_metadata_and_reports_counts():
    store = FakeStore()
    index = FakeIndex()
    calls = []

    def delete_metadata(*, now=None):
        calls.append(("metadata", now))
        return 2

    result = await cleanup_expired_attachments(store, delete_metadata, index=index, now=NOW)

    assert store.now == NOW
    assert index.now == NOW
    assert calls == [("metadata", NOW)]
    assert result.deleted_objects == 3
    assert result.deleted_chunks == 4
    assert result.deleted_metadata == 2


@pytest.mark.asyncio
async def test_cleanup_preserves_metadata_when_object_cleanup_fails():
    class FailingStore:
        async def delete_expired(self, *, now=None):
            raise RuntimeError("storage unavailable")

    metadata_called = False

    def delete_metadata(*, now=None):
        nonlocal metadata_called
        metadata_called = True
        return 1

    with pytest.raises(RuntimeError, match="storage unavailable"):
        await cleanup_expired_attachments(FailingStore(), delete_metadata, now=NOW)
    assert metadata_called is False
