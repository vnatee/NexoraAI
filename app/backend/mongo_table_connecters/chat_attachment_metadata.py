import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from core.attachment_store import AttachmentRecord
from mongo_table_connecters.mongo_connector import get_database


collection = get_database()["chat_attachment_metadata"]

ATTACHMENT_STATUSES = {"stored", "extracting", "ready", "failed"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Attachment metadata timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def ensure_attachment_metadata_indexes() -> bool:
    """Create useful indexes when supported; explicit cleanup remains authoritative."""
    try:
        collection.create_index(
            [("owner_id", 1), ("conversation_id", 1), ("created_at", -1)],
            name="attachment_owner_conversation",
        )
        collection.create_index(
            "expires_at",
            expireAfterSeconds=0,
            name="attachment_expiry",
        )
        collection.create_index(
            [("owner_id", 1), ("conversation_id", 1), ("upload_id", 1)],
            unique=True,
            partialFilterExpression={"upload_id": {"$exists": True}},
            name="attachment_upload_idempotency",
        )
        return True
    except PyMongoError:
        logging.warning(
            "One or more attachment metadata indexes are unavailable; explicit cleanup and application idempotency remain active",
            exc_info=True,
        )
        return False


def create_attachment_metadata(
    record: AttachmentRecord,
    *,
    storage_backend: str,
    storage_key: str,
    upload_id: str = "",
    page_count: int | None = None,
    scan_status: str = "not_configured",
) -> dict[str, Any]:
    backend = str(storage_backend or "").strip().lower()
    key = str(storage_key or "").strip()
    if not backend or not key:
        raise ValueError("storage_backend and storage_key are required")
    created_at = _timestamp(record.created_at)
    expires_at = _timestamp(record.expires_at)
    if expires_at <= created_at:
        raise ValueError("Attachment expiry must be after creation")
    normalized_upload_id = str(upload_id or "").strip()
    if len(normalized_upload_id) > 128:
        raise ValueError("upload_id is too long")
    if page_count is not None and (
        isinstance(page_count, bool) or not isinstance(page_count, int) or page_count < 1
    ):
        raise ValueError("page_count must be a positive integer")
    if scan_status not in {"not_configured", "clean"}:
        raise ValueError("Unsupported attachment scan status")
    item = {
        "_id": record.attachment_id,
        "owner_id": record.owner_id,
        "conversation_id": record.conversation_id,
        "filename": record.filename,
        "content_type": record.content_type,
        "size": record.size,
        "sha256": record.sha256,
        "storage_backend": backend[:50],
        "storage_key": key[:1024],
        "status": "stored",
        "page_count": page_count,
        "scan_status": scan_status,
        "error_code": None,
        "created_at": created_at,
        "updated_at": created_at,
        "expires_at": expires_at,
        "delete_at": None,
    }
    if normalized_upload_id:
        item["upload_id"] = normalized_upload_id
    collection.insert_one(item)
    return item


def get_attachment_metadata_by_upload_id(
    upload_id: str,
    *,
    owner_id: str,
    conversation_id: str,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    return collection.find_one(
        {
            "upload_id": str(upload_id or "").strip(),
            "owner_id": owner_id,
            "conversation_id": conversation_id,
            "delete_at": None,
            "expires_at": {"$gt": now or _now()},
        }
    )


def _active_scope_query(
    attachment_id: str,
    *,
    owner_id: str,
    conversation_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    return {
        "_id": attachment_id,
        "owner_id": owner_id,
        "conversation_id": conversation_id,
        "delete_at": None,
        "expires_at": {"$gt": now or _now()},
    }


def get_attachment_metadata(
    attachment_id: str,
    *,
    owner_id: str,
    conversation_id: str,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    return collection.find_one(
        _active_scope_query(
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
            now=now,
        )
    )


def list_attachment_metadata(
    *,
    owner_id: str,
    conversation_id: str,
    now: datetime | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    query = {
        "owner_id": owner_id,
        "conversation_id": conversation_id,
        "delete_at": None,
        "expires_at": {"$gt": now or _now()},
    }
    return list(collection.find(query).sort("created_at", -1).limit(max(1, min(limit, 100))))


def list_recoverable_attachment_metadata(
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    recovery_time = now or _now()
    query = {
        "delete_at": None,
        "expires_at": {"$gt": recovery_time},
        "$or": [
            {"status": "stored"},
            {"status": "extracting", "lease_expires_at": {"$lte": recovery_time}},
            {"status": "extracting", "lease_expires_at": {"$exists": False}},
            {"status": "extracting", "lease_expires_at": None},
        ],
    }
    return list(collection.find(query).sort("updated_at", 1).limit(max(1, min(limit, 500))))


def claim_attachment_extraction(
    attachment_id: str,
    *,
    owner_id: str,
    conversation_id: str,
    worker_id: str,
    lease_minutes: int = 10,
) -> dict[str, Any] | None:
    normalized_worker_id = str(worker_id or "").strip()
    if not normalized_worker_id:
        raise ValueError("worker_id is required")
    now = _now()
    query = {
        **_active_scope_query(
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
            now=now,
        ),
        "$or": [
            {"status": "stored"},
            {"status": "extracting", "lease_expires_at": {"$lte": now}},
            {"status": "extracting", "lease_expires_at": {"$exists": False}},
            {"status": "extracting", "lease_expires_at": None},
        ],
    }
    return collection.find_one_and_update(
        query,
        {
            "$set": {
                "status": "extracting",
                "error_code": None,
                "worker_id": normalized_worker_id[:128],
                "lease_expires_at": now + timedelta(minutes=max(1, lease_minutes)),
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )


def release_attachment_extraction(
    attachment_id: str,
    *,
    owner_id: str,
    conversation_id: str,
    worker_id: str,
) -> bool:
    result = collection.update_one(
        {
            **_active_scope_query(
                attachment_id,
                owner_id=owner_id,
                conversation_id=conversation_id,
            ),
            "status": "extracting",
            "worker_id": str(worker_id or "").strip(),
        },
        {
            "$set": {"status": "stored", "updated_at": _now()},
            "$unset": {"worker_id": "", "lease_expires_at": ""},
        },
    )
    return bool(result.modified_count)


def update_attachment_status(
    attachment_id: str,
    *,
    owner_id: str,
    conversation_id: str,
    status: str,
    error_code: str = "",
    chunk_count: int | None = None,
    extracted_characters: int | None = None,
    worker_id: str = "",
) -> dict[str, Any] | None:
    if status not in ATTACHMENT_STATUSES:
        raise ValueError("Unsupported attachment status")
    safe_error_code = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(error_code or ""))[:100] or None
    if chunk_count is not None and (
        isinstance(chunk_count, bool) or not isinstance(chunk_count, int) or chunk_count < 0
    ):
        raise ValueError("chunk_count must be non-negative")
    if extracted_characters is not None and (
        isinstance(extracted_characters, bool)
        or not isinstance(extracted_characters, int)
        or extracted_characters < 0
    ):
        raise ValueError("extracted_characters must be non-negative")
    query = _active_scope_query(
        attachment_id,
        owner_id=owner_id,
        conversation_id=conversation_id,
    )
    if worker_id:
        query["worker_id"] = str(worker_id).strip()
    values = {
        "status": status,
        "error_code": safe_error_code if status == "failed" else None,
        "updated_at": _now(),
    }
    if chunk_count is not None:
        values["chunk_count"] = chunk_count
    if extracted_characters is not None:
        values["extracted_characters"] = extracted_characters
    update: dict[str, Any] = {"$set": values}
    if status in {"ready", "failed", "stored"}:
        update["$unset"] = {"worker_id": "", "lease_expires_at": ""}
    result = collection.update_one(query, update)
    if not result.modified_count:
        return None
    return get_attachment_metadata(
        attachment_id,
        owner_id=owner_id,
        conversation_id=conversation_id,
    )


def soft_delete_attachment_metadata(
    attachment_id: str,
    *,
    owner_id: str,
    conversation_id: str,
) -> bool:
    now = _now()
    result = collection.update_one(
        _active_scope_query(
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
            now=now,
        ),
        {"$set": {"delete_at": now, "updated_at": now}},
    )
    return bool(result.modified_count)


def delete_expired_attachment_metadata(*, now: datetime | None = None) -> int:
    result = collection.delete_many({"expires_at": {"$lte": now or _now()}})
    return int(result.deleted_count)


def serialize_attachment_metadata(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("_id") or ""),
        "filename": str(item.get("filename") or ""),
        "content_type": str(item.get("content_type") or ""),
        "size": max(0, int(item.get("size") or 0)),
        "status": str(item.get("status") or ""),
        "page_count": item.get("page_count"),
        "scan_status": str(item.get("scan_status") or ""),
        "chunk_count": max(0, int(item.get("chunk_count") or 0)),
        "extracted_characters": max(0, int(item.get("extracted_characters") or 0)),
        "error_code": item.get("error_code"),
        "created_at": item.get("created_at").isoformat() if item.get("created_at") else None,
        "expires_at": item.get("expires_at").isoformat() if item.get("expires_at") else None,
    }
