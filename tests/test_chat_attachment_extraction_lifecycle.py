from datetime import datetime, timedelta, timezone

import pytest

import app as app_module
from core.attachment_extraction import AttachmentExtractionError, ExtractedChunk
from core.attachment_store import AttachmentRecord, StoredAttachment


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _record():
    return AttachmentRecord(
        attachment_id="9aee2161-d67f-45a1-b4a5-7d2042dd1c26",
        owner_id="owner-1",
        conversation_id="conversation-1",
        filename="requirements.txt",
        content_type="text/plain",
        size=12,
        sha256="a" * 64,
        created_at=NOW.isoformat(),
        expires_at=(NOW + timedelta(hours=24)).isoformat(),
    )


class Store:
    async def get(self, attachment_id, *, owner_id, conversation_id):
        assert attachment_id == _record().attachment_id
        assert owner_id == "owner-1"
        assert conversation_id == "conversation-1"
        return StoredAttachment(_record(), b"requirements")


class Index:
    def __init__(self):
        self.replaced = []
        self.deleted = []

    async def replace_attachment(self, record, chunks):
        self.replaced.append((record, chunks))
        return len(chunks)

    async def delete_attachment(self, attachment_id, *, owner_id, conversation_id):
        self.deleted.append((attachment_id, owner_id, conversation_id))
        return 1


@pytest.mark.asyncio
async def test_extraction_lifecycle_marks_ready_with_bounded_counts(monkeypatch):
    statuses = []

    def update_status(attachment_id, **values):
        statuses.append((attachment_id, values))
        return {"_id": attachment_id}

    chunks = [
        ExtractedChunk(0, 1, "1", "Requirement one"),
        ExtractedChunk(1, 2, "2", "Requirement two"),
    ]
    monkeypatch.setattr(app_module, "update_attachment_status", update_status)
    monkeypatch.setattr(app_module, "extract_attachment_chunks", lambda **kwargs: chunks)
    index = Index()

    await app_module._run_chat_attachment_extraction(
        Store(),
        index,
        _record().attachment_id,
        owner_id="owner-1",
        conversation_id="conversation-1",
    )

    assert [values["status"] for _, values in statuses] == ["extracting", "ready"]
    assert statuses[-1][1]["chunk_count"] == 2
    assert statuses[-1][1]["extracted_characters"] == 30
    assert len(index.replaced) == 1
    assert index.deleted == []


@pytest.mark.asyncio
async def test_extraction_lifecycle_marks_ocr_required_without_index_content(monkeypatch):
    statuses = []

    def update_status(attachment_id, **values):
        statuses.append(values)
        return {"_id": attachment_id}

    def require_ocr(**kwargs):
        raise AttachmentExtractionError("Document has no machine-readable text; OCR is required")

    monkeypatch.setattr(app_module, "update_attachment_status", update_status)
    monkeypatch.setattr(app_module, "extract_attachment_chunks", require_ocr)
    index = Index()

    await app_module._run_chat_attachment_extraction(
        Store(),
        index,
        _record().attachment_id,
        owner_id="owner-1",
        conversation_id="conversation-1",
    )

    assert [item["status"] for item in statuses] == ["extracting", "failed"]
    assert statuses[-1]["error_code"] == "ocr_required"
    assert index.replaced == []
    assert index.deleted == [(_record().attachment_id, "owner-1", "conversation-1")]


@pytest.mark.asyncio
async def test_extraction_stops_when_metadata_was_revoked(monkeypatch):
    monkeypatch.setattr(app_module, "update_attachment_status", lambda *args, **kwargs: None)

    class UnusedStore:
        async def get(self, *args, **kwargs):
            raise AssertionError("revoked attachment must not be read")

    index = Index()
    await app_module._run_chat_attachment_extraction(
        UnusedStore(),
        index,
        _record().attachment_id,
        owner_id="owner-1",
        conversation_id="conversation-1",
    )
    assert index.replaced == []
