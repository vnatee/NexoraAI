from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument

from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["web_source_scans"]

_LEASE_DURATION = timedelta(minutes=5)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_web_source_scan_indexes() -> None:
    collection.create_index([("expires_at", 1), ("status", 1)])
    collection.create_index([("team_id", 1), ("created_by", 1), ("created_at", -1)])
    collection.create_index([("status", 1), ("lease_expires_at", 1), ("updated_at", 1)])


def create_web_source_scan(document: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    scan = {
        **document,
        "_id": str(document.get("_id") or uuid.uuid4()),
        "status": "ready",
        "created_at": now,
        "updated_at": now,
        "last_error": "",
    }
    collection.insert_one(scan)
    return scan


def get_web_source_scan(scan_id: str) -> dict[str, Any] | None:
    return collection.find_one({"_id": str(scan_id)})


def queue_web_source_scan(
    scan_id: str,
    selected_urls: list[str],
    *,
    requested_by: str,
    at: datetime | None = None,
) -> dict[str, Any] | None:
    now = at or _now()
    scan = collection.find_one({
        "_id": str(scan_id),
        "status": "ready",
        "expires_at": {"$gt": now},
    })
    if not scan:
        return None
    selected = set(selected_urls)
    progress = [
        {
            "url": str(page.get("source_url") or ""),
            "status": "queued" if str(page.get("source_url") or "") in selected else "skipped",
            "attempt": 0,
            "error": None,
            "updated_at": now,
        }
        for page in scan.get("pages") or []
    ]
    return collection.find_one_and_update(
        {"_id": str(scan_id), "status": "ready", "expires_at": {"$gt": now}},
        {"$set": {
            "status": "queued",
            "selected_urls": list(selected_urls),
            "page_progress": progress,
            "requested_by": str(requested_by),
            "attempt": 1,
            "started_at": None,
            "completed_at": None,
            "worker_id": None,
            "lease_expires_at": None,
            "updated_at": now,
            "last_error": "",
        }},
        return_document=ReturnDocument.AFTER,
    )


def claim_web_source_scan(
    scan_id: str,
    worker_id: str,
    *,
    at: datetime | None = None,
) -> dict[str, Any] | None:
    now = at or _now()
    return collection.find_one_and_update(
        {
            "_id": str(scan_id),
            "$or": [
                {"status": "queued", "worker_id": {"$in": [None, ""]}},
                {"status": "indexing", "lease_expires_at": {"$lte": now}},
            ],
        },
        {"$set": {
            "status": "indexing",
            "worker_id": str(worker_id),
            "lease_expires_at": now + _LEASE_DURATION,
            "started_at": now,
            "updated_at": now,
            "last_error": "",
        }},
        return_document=ReturnDocument.AFTER,
    )


def heartbeat_web_source_scan(scan_id: str, worker_id: str) -> bool:
    now = _now()
    result = collection.update_one(
        {"_id": str(scan_id), "status": "indexing", "worker_id": str(worker_id)},
        {"$set": {"lease_expires_at": now + _LEASE_DURATION, "updated_at": now}},
    )
    return bool(result.modified_count)


def release_web_source_scan(scan_id: str, worker_id: str) -> None:
    now = _now()
    collection.update_one(
        {"_id": str(scan_id), "status": "indexing", "worker_id": str(worker_id)},
        {"$set": {
            "status": "queued",
            "worker_id": None,
            "lease_expires_at": None,
            "updated_at": now,
        }},
    )


def _safe_error(error: Exception | str) -> dict[str, str]:
    code = error.__class__.__name__ if isinstance(error, Exception) else "IndexingError"
    message = re.sub(r"[\r\n\t]+", " ", str(error)).strip()
    message = re.sub(r"(?i)(bearer)\s+\S+", r"\1 <redacted>", message)
    message = re.sub(
        r"(?i)(api[_ -]?key|token|secret)\s*[:=]\s*\S+",
        r"\1=<redacted>",
        message,
    )
    return {
        "code": str(code)[:100],
        "message": (message or "Web page indexing failed")[:500],
    }


def update_web_source_page(
    scan_id: str,
    worker_id: str,
    page_index: int,
    status: str,
    *,
    error: Exception | str | None = None,
    storage_key: str = "",
) -> bool:
    if status not in {"indexing", "indexed", "failed"}:
        raise ValueError("Unsupported web source page status")
    now = _now()
    updates: dict[str, Any] = {
        f"page_progress.{page_index}.status": status,
        f"page_progress.{page_index}.updated_at": now,
        "updated_at": now,
        "lease_expires_at": now + _LEASE_DURATION,
    }
    if status == "indexing":
        updates[f"page_progress.{page_index}.error"] = None
        updates[f"page_progress.{page_index}.storage_key"] = ""
    elif error is not None:
        updates[f"page_progress.{page_index}.error"] = _safe_error(error)
    else:
        updates[f"page_progress.{page_index}.error"] = None
    if storage_key:
        updates[f"page_progress.{page_index}.storage_key"] = str(storage_key)
    update: dict[str, Any] = {"$set": updates}
    if status == "indexing":
        update["$inc"] = {f"page_progress.{page_index}.attempt": 1}
    result = collection.update_one(
        {"_id": str(scan_id), "status": "indexing", "worker_id": str(worker_id)},
        update,
    )
    return bool(result.modified_count)


def complete_web_source_scan(
    scan_id: str,
    worker_id: str,
    status: str,
    *,
    error: Exception | str | None = None,
) -> dict[str, Any] | None:
    if status not in {"indexed", "failed"}:
        raise ValueError("Unsupported terminal web source status")
    now = _now()
    return collection.find_one_and_update(
        {"_id": str(scan_id), "status": "indexing", "worker_id": str(worker_id)},
        {"$set": {
            "status": status,
            "worker_id": None,
            "lease_expires_at": None,
            "updated_at": now,
            "completed_at": now,
            "last_error": _safe_error(error)["message"] if error is not None else "",
        }},
        return_document=ReturnDocument.AFTER,
    )


def retry_web_source_scan(scan_id: str, *, at: datetime | None = None) -> dict[str, Any] | None:
    now = at or _now()
    scan = collection.find_one({
        "_id": str(scan_id),
        "status": "failed",
        "expires_at": {"$gt": now},
    })
    if not scan:
        return None
    progress = []
    for item in scan.get("page_progress") or []:
        next_item = dict(item)
        if next_item.get("status") in {"failed", "indexing", "queued"}:
            next_item["status"] = "queued"
            next_item["error"] = None
            next_item["updated_at"] = now
        progress.append(next_item)
    return collection.find_one_and_update(
        {"_id": str(scan_id), "status": "failed", "expires_at": {"$gt": now}},
        {
            "$set": {
                "status": "queued",
                "page_progress": progress,
                "worker_id": None,
                "lease_expires_at": None,
                "completed_at": None,
                "updated_at": now,
                "last_error": "",
            },
            "$inc": {"attempt": 1},
        },
        return_document=ReturnDocument.AFTER,
    )


def list_recoverable_web_source_scans(
    *, at: datetime | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    now = at or _now()
    return list(
        collection.find({
            "$or": [
                {"status": "queued", "worker_id": {"$in": [None, ""]}},
                {"status": "indexing", "lease_expires_at": {"$lte": now}},
            ],
        }).sort("updated_at", 1).limit(max(1, min(int(limit), 100)))
    )


def list_web_source_scans(
    *, team_id: str | None, limit: int = 20
) -> list[dict[str, Any]]:
    if team_id:
        query: dict[str, Any] = {"team_id": str(team_id)}
    else:
        query = {"$or": [
            {"team_id": None},
            {"team_id": ""},
            {"team_id": {"$exists": False}},
        ]}
    return list(
        collection.find(query).sort("created_at", -1).limit(max(1, min(int(limit), 100)))
    )


def mark_web_source_scan_failed(scan_id: str, error_type: str = "") -> None:
    now = _now()
    collection.update_one(
        {"_id": str(scan_id)},
        {"$set": {
            "status": "failed",
            "worker_id": None,
            "lease_expires_at": None,
            "completed_at": now,
            "updated_at": now,
            "last_error": _safe_error(error_type)["message"],
        }},
    )

def claim_web_source_scan_for_cleanup(
    scan_id: str,
    *,
    at: datetime | None = None,
) -> dict[str, Any] | None:
    now = at or _now()
    return collection.find_one_and_update(
        {
            "_id": str(scan_id),
            "$or": [
                {"status": {"$in": ["ready", "failed"]}},
                {
                    "status": {"$in": ["queued", "indexed", "indexing", "deleting"]},
                    "expires_at": {"$lte": now},
                    "$or": [
                        {"lease_expires_at": {"$lte": now}},
                        {"lease_expires_at": None},
                        {"lease_expires_at": {"$exists": False}},
                    ],
                },
            ],
        },
        {"$set": {"status": "deleting", "updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )


def list_expired_web_source_scans(
    *,
    at: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    now = at or _now()
    return list(
        collection.find({
            "expires_at": {"$lte": now},
            "$or": [
                {"status": {"$in": ["ready", "failed"]}},
                {
                    "status": {"$in": ["queued", "indexed", "indexing", "deleting"]},
                    "$or": [
                        {"lease_expires_at": {"$lte": now}},
                        {"lease_expires_at": None},
                        {"lease_expires_at": {"$exists": False}},
                    ],
                },
            ],
        }).sort("expires_at", 1).limit(max(1, min(int(limit), 500)))
    )


def delete_web_source_scan(scan_id: str) -> None:
    collection.delete_one({"_id": str(scan_id)})
