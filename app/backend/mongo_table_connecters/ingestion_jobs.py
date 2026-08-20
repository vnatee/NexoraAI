import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument

from mongo_table_connecters.mongo_connector import get_database


db = get_database()
collection = db["ingestion_jobs"]

ACTIVE_STATUSES = {"uploaded", "extracting", "chunking", "embedding"}
TERMINAL_STATUSES = {"indexed", "failed"}
ALL_STATUSES = ACTIVE_STATUSES | TERMINAL_STATUSES


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_error(error: Exception) -> dict[str, str]:
    message = re.sub(r"[\r\n\t]+", " ", str(error)).strip()
    message = re.sub(r"(?i)(returned HTTP\s+\d+)\s*:.*$", r"\1", message)
    message = re.sub(r"(?i)(authentication failed)\s*:.*$", r"\1", message)
    message = re.sub(r"(?i)(bearer)\s+\S+", r"\1 <redacted>", message)
    message = re.sub(r"(?i)(bearer|api[_ -]?key|token|secret)\s*[:=]\s*\S+", r"\1=<redacted>", message)
    message = re.sub(r"(?i)([?&](?:sig|token|key)=)[^&\s]+", r"\1<redacted>", message)
    return {
        "code": error.__class__.__name__[:100],
        "message": (message or "Document processing failed")[:500],
    }


def create_ingestion_job(
    *,
    owner_id: str,
    owner_name: str,
    scope: str,
    filename: str,
    storage_path: str,
    file_size: int,
    team_id: str = "",
    data_group_ids: list[str] | None = None,
    routing_context: dict[str, str] | None = None,
    route: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _now()
    route = route or {}
    profile = route.get("profile") or {}
    provider = route.get("provider") or {}
    rule = route.get("rule") or {}
    item = {
        "_id": str(uuid.uuid4()),
        "owner_id": owner_id,
        "owner_name": owner_name,
        "scope": scope,
        "team_id": team_id,
        "data_group_ids": list(data_group_ids or []),
        "filename": filename,
        "storage_path": storage_path,
        "file_size": max(0, int(file_size or 0)),
        "status": "uploaded",
        "attempt": 1,
        "routing_context": dict(routing_context or {}),
        "route_source": str(route.get("source") or "system_fallback"),
        "profile_id": str(profile.get("_id") or ""),
        "profile_name": str(profile.get("name") or ""),
        "provider_id": str(provider.get("_id") or ""),
        "provider_name": str(provider.get("name") or provider.get("provider_type") or "System parser"),
        "rule_id": str(rule.get("_id") or ""),
        "rule_name": str(rule.get("name") or ""),
        "error": None,
        "result_message": "",
        "stage_history": [{"status": "uploaded", "at": now}],
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
    }
    collection.insert_one(item)
    return item


def get_ingestion_job(job_id: str) -> dict[str, Any] | None:
    return collection.find_one({"_id": job_id})


def claim_ingestion_job(job_id: str, worker_id: str, *, lease_minutes: int = 60) -> dict[str, Any] | None:
    now = _now()
    return collection.find_one_and_update(
        {
            "_id": job_id,
            "$or": [
                {"status": "uploaded", "worker_id": {"$in": [None, ""]}},
                {"status": {"$in": list(ACTIVE_STATUSES)}, "lease_expires_at": {"$lte": now}},
            ],
        },
        {
            "$set": {
                "worker_id": worker_id,
                "lease_expires_at": now + timedelta(minutes=max(5, lease_minutes)),
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )


def list_recoverable_ingestion_jobs(limit: int = 100) -> list[dict[str, Any]]:
    now = _now()
    query = {
        "$or": [
            {"status": "uploaded", "worker_id": {"$in": [None, ""]}},
            {"status": {"$in": list(ACTIVE_STATUSES)}, "lease_expires_at": {"$lte": now}},
        ]
    }
    return list(collection.find(query).sort("updated_at", 1).limit(max(1, min(limit, 500))))


def list_ingestion_jobs(
    owner_id: str,
    *,
    scope: str = "",
    team_id: str = "",
    limit: int = 20,
    indexed_visibility_seconds: int = 60,
) -> list[dict[str, Any]]:
    cutoff = _now() - timedelta(seconds=max(0, indexed_visibility_seconds))
    query: dict[str, Any] = {
        "owner_id": owner_id,
        "$or": [
            {"status": {"$ne": "indexed"}},
            {"status": "indexed", "completed_at": {"$gte": cutoff}},
        ],
    }
    if scope:
        query["scope"] = scope
    if team_id:
        query["team_id"] = team_id
    return list(collection.find(query).sort("created_at", -1).limit(max(1, min(limit, 100))))


def latest_indexed_times(
    scope: str,
    storage_paths: list[str],
    *,
    owner_id: str = "",
    team_id: str = "",
) -> dict[str, str]:
    if not storage_paths:
        return {}
    query: dict[str, Any] = {
        "scope": scope,
        "storage_path": {"$in": storage_paths},
        "status": "indexed",
        "completed_at": {"$ne": None},
    }
    if owner_id:
        query["owner_id"] = owner_id
    if team_id:
        query["team_id"] = team_id
    result: dict[str, str] = {}
    for job in collection.find(query).sort("completed_at", -1):
        path = str(job.get("storage_path") or "")
        completed_at = job.get("completed_at")
        if path and completed_at and path not in result:
            result[path] = completed_at.isoformat()
    return result


def update_ingestion_job_status(
    job_id: str,
    status: str,
    *,
    error: Exception | None = None,
    result_message: str = "",
    worker_id: str = "",
) -> dict[str, Any] | None:
    if status not in ALL_STATUSES:
        raise ValueError("Unsupported ingestion job status")
    now = _now()
    updates: dict[str, Any] = {"status": status, "updated_at": now}
    if worker_id and status in ACTIVE_STATUSES:
        updates["lease_expires_at"] = now + timedelta(minutes=60)
    if status == "extracting":
        updates["started_at"] = now
    if status in TERMINAL_STATUSES:
        updates["completed_at"] = now
        updates["worker_id"] = None
        updates["lease_expires_at"] = None
    if error is not None:
        updates["error"] = _safe_error(error)
    elif status != "failed":
        updates["error"] = None
    if result_message:
        updates["result_message"] = result_message[:300]
    query = {"_id": job_id}
    if worker_id:
        query["worker_id"] = worker_id
    result = collection.update_one(
        query,
        {
            "$set": updates,
            "$push": {"stage_history": {"status": status, "at": now}},
        },
    )
    return get_ingestion_job(job_id) if result.modified_count else None


def restart_failed_ingestion_job(job_id: str, owner_id: str) -> dict[str, Any] | None:
    now = _now()
    result = collection.update_one(
        {"_id": job_id, "owner_id": owner_id, "status": "failed"},
        {
            "$set": {
                "status": "uploaded",
                "error": None,
                "result_message": "",
                "updated_at": now,
                "started_at": None,
                "completed_at": None,
                "worker_id": None,
                "lease_expires_at": None,
            },
            "$inc": {"attempt": 1},
            "$push": {"stage_history": {"status": "uploaded", "at": now}},
        },
    )
    return get_ingestion_job(job_id) if result.modified_count else None


def serialize_ingestion_job(item: dict[str, Any]) -> dict[str, Any]:
    timestamp_fields = {"created_at", "updated_at", "started_at", "completed_at"}
    serialized = {
        key: (value.isoformat() if key in timestamp_fields and value else value)
        for key, value in item.items()
        if key not in {"owner_name", "storage_path", "routing_context", "data_group_ids", "worker_id", "lease_expires_at"}
    }
    serialized["stage_history"] = [
        {
            "status": str(stage.get("status") or ""),
            "at": stage.get("at").isoformat() if stage.get("at") else None,
        }
        for stage in item.get("stage_history") or []
    ]
    return serialized
