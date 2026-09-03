from unittest.mock import MagicMock

from prepdocslib import docinteldb


def test_document_processing_usage_is_idempotent_by_job_id(monkeypatch):
    collection = MagicMock()
    collection.update_one.return_value.upserted_id = "ingestion:job-1"
    monkeypatch.setattr(docinteldb, "processing_usage_collection", collection)

    result = docinteldb.insert_document_processing_usage(
        owner_id="user-1",
        owner_name="User One",
        team_id="team-1",
        scope="team",
        provider_id="provider-1",
        provider_name="Docling",
        profile_id="profile-1",
        profile_name="PDF",
        page_count=12,
        file_type="pdf",
        duration_ms=500,
        event_id="ingestion:job-1",
    )

    assert collection.update_one.call_args.args[0] == {"_id": "ingestion:job-1"}
    stored = collection.update_one.call_args.args[1]["$setOnInsert"]
    assert stored["schema_version"] == 2
    assert stored["page_count"] == 12
    assert collection.update_one.call_args.kwargs["upsert"] is True
    assert result["inserted"] is True
