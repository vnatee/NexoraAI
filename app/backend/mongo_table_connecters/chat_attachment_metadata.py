import logging
import re
from datetime import datetime, timezone
from typing import Any

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
        return True
    except PyMongoError:
        logging.warning(
            "Attachment metadata TTL indexes are unavailable; explicit cleanup is still required",
            exc_info=True,
        )
        return False


def create_attachment_metadata(
    record: AttachmentRecord,
    *,
    storage_backend: str,
    storage_key: str,
) -> dict[str, Any]:
    backend = str(storage_backend or "").strip().lower()
    key = str(storage_key or "").strip()
    if not backend or not key:
        raise ValueError("storage_backend and storage_key are required")
    created_at = _timestamp(record.created_at)
    expires_at = _timestamp(record.expires_at)
    if expires_at <= created_at:
        raise ValueError("Attachment expiry must be after creation")
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
        "error_code": None,
        "created_at": created_at,
        "updated_at": created_at,
        "expires_at": expires_at,
        "delete_at": None,
    }
    collection.insert_one(item)
    return item


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


def update_attachment_status(
    attachment_id: str,
    *,
    owner_id: str,
    conversation_id: str,
    status: str,
    error_code: str = "",
) -> dict[str, Any] | None:
    if status not in ATTACHMENT_STATUSES:
        raise ValueError("Unsupported attachment status")
    safe_error_code = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(error_code or ""))[:100] or None
    query = _active_scope_query(
        attachment_id,
        owner_id=owner_id,
        conversation_id=conversation_id,
    )
    result = collection.update_one(
        query,
        {
            "$set": {
                "status": status,
                "error_code": safe_error_code if status == "failed" else None,
                "updated_at": _now(),
            }
        },
    )
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
        "error_code": item.get("error_code"),
        "created_at": item.get("created_at").isoformat() if item.get("created_at") else None,
        "expires_at": item.get("expires_at").isoformat() if item.get("expires_at") else None,
    }
