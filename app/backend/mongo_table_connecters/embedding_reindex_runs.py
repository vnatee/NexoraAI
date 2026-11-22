from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument

from mongo_table_connecters.mongo_connector import get_database


runs = get_database()["embedding_reindex_runs"]
items = get_database()["embedding_reindex_items"]

ACTIVE_RUN_STATUSES = {"queued", "running"}
TERMINAL_ITEM_STATUSES = {"succeeded", "failed"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_embedding_reindex_indexes() -> None:
    runs.create_index([("profile_id", 1), ("status", 1)])
    runs.create_index("created_at")
    items.create_index([("run_id", 1), ("status", 1)])
    items.create_index([("run_id", 1), ("kind", 1), ("source_key", 1)], unique=True)


def create_embedding_reindex_run(
    *,
    profile_id: str,
    actor_id: str,
    profile_snapshot: dict[str, Any],
    source_items: list[dict[str, Any]],
) -> dict[str, Any]:
    if runs.find_one({"status": {"$in": list(ACTIVE_RUN_STATUSES)}}):
        raise ValueError("Another full re-index is already running")
    now = _now()
    run_id = str(uuid.uuid4())
    document = {
        "_id": run_id,
        "profile_id": profile_id,
        "profile_snapshot": dict(profile_snapshot),
        "actor_id": actor_id,
        "status": "queued",
        "total": len(source_items),
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "worker_id": None,
        "lease_expires_at": None,
    }
    runs.insert_one(document)
    if source_items:
        items.insert_many(
            [
                {
                    "_id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "kind": str(item["kind"]),
                    "source_key": str(item["source_key"]),
                    "scope": str(item.get("scope") or ""),
                    "source_job_id": str(item.get("source_job_id") or ""),
                    "status": "queued",
                    "ingestion_job_id": "",
                    "error_code": "",
                    "created_at": now,
                    "updated_at": now,
                }
                for item in source_items
            ]
        )
    return document


def get_embedding_reindex_run(run_id: str) -> dict[str, Any] | None:
    return runs.find_one({"_id": run_id})


def latest_embedding_reindex_run(profile_id: str = "") -> dict[str, Any] | None:
    query: dict[str, Any] = {}
    if profile_id:
        query["profile_id"] = profile_id
    return runs.find_one(query, sort=[("created_at", -1)])


def list_recoverable_embedding_reindex_runs() -> list[dict[str, Any]]:
    now = _now()
    return list(
        runs.find(
            {
                "$or": [
                    {"status": "queued"},
                    {
                        "status": "running",
                        "lease_expires_at": {"$lte": now},
                    },
                ]
            }
        ).sort("created_at", 1)
    )


def claim_embedding_reindex_run(
    run_id: str, worker_id: str, *, lease_minutes: int = 10
) -> dict[str, Any] | None:
    now = _now()
    return runs.find_one_and_update(
        {
            "_id": run_id,
            "$or": [
                {"status": "queued"},
                {"status": "running", "lease_expires_at": {"$lte": now}},
            ],
        },
        {
            "$set": {
                "status": "running",
                "worker_id": worker_id,
                "lease_expires_at": now + timedelta(minutes=max(2, lease_minutes)),
                "started_at": now,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )


def heartbeat_embedding_reindex_run(run_id: str, worker_id: str) -> bool:
    result = runs.update_one(
        {"_id": run_id, "status": "running", "worker_id": worker_id},
        {
            "$set": {
                "lease_expires_at": _now() + timedelta(minutes=10),
                "updated_at": _now(),
            }
        },
    )
    return result.modified_count > 0


def release_embedding_reindex_run(run_id: str, worker_id: str) -> None:
    runs.update_one(
        {"_id": run_id, "status": "running", "worker_id": worker_id},
        {
            "$set": {
                "status": "queued",
                "worker_id": None,
                "lease_expires_at": None,
                "updated_at": _now(),
            }
        },
    )


def pending_embedding_reindex_items(run_id: str) -> list[dict[str, Any]]:
    return list(
        items.find(
            {"run_id": run_id, "status": {"$nin": list(TERMINAL_ITEM_STATUSES)}}
        ).sort("created_at", 1)
    )


def update_embedding_reindex_item(
    item_id: str,
    *,
    status: str,
    ingestion_job_id: str = "",
    error_code: str = "",
) -> None:
    updates: dict[str, Any] = {"status": status, "updated_at": _now()}
    if ingestion_job_id:
        updates["ingestion_job_id"] = ingestion_job_id
    if error_code:
        updates["error_code"] = str(error_code)[:100]
    items.update_one({"_id": item_id}, {"$set": updates})


def embedding_reindex_progress(run_id: str) -> dict[str, int]:
    pipeline = [
        {"$match": {"run_id": run_id}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    counts = {str(row["_id"]): int(row["count"]) for row in items.aggregate(pipeline)}
    total = sum(counts.values())
    return {
        "total": total,
        "queued": counts.get("queued", 0),
        "running": counts.get("running", 0),
        "succeeded": counts.get("succeeded", 0),
        "failed": counts.get("failed", 0),
    }


def complete_embedding_reindex_run(run_id: str, worker_id: str) -> dict[str, Any] | None:
    progress = embedding_reindex_progress(run_id)
    status = "completed" if progress["failed"] == 0 else "completed_with_failures"
    now = _now()
    return runs.find_one_and_update(
        {"_id": run_id, "status": "running", "worker_id": worker_id},
        {
            "$set": {
                "status": status,
                "completed_at": now,
                "updated_at": now,
                "worker_id": None,
                "lease_expires_at": None,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
