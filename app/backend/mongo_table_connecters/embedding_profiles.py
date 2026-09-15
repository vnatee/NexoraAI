from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from mongo_table_connecters.mongo_connector import get_database

profiles = get_database()["embedding_profiles"]
settings = get_database()["application_settings"]
SETTINGS_ID = "embedding:system"
ENVIRONMENT_PROFILE_ID = "environment"


def list_embedding_profiles(*, include_deleted: bool = False) -> list[dict[str, Any]]:
    query = {} if include_deleted else {"delete_at": None}
    return list(profiles.find(query).sort("name", 1))


def get_embedding_profile(profile_id: str, *, include_deleted: bool = False) -> dict[str, Any] | None:
    query: dict[str, Any] = {"_id": profile_id}
    if not include_deleted:
        query["delete_at"] = None
    return profiles.find_one(query)


def insert_embedding_profile(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document = {
        "_id": str(uuid.uuid4()),
        **data,
        "created_at": now,
        "updated_at": now,
        "delete_at": None,
    }
    profiles.insert_one(document)
    return document


def update_embedding_profile(profile_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    profiles.update_one(
        {"_id": profile_id, "delete_at": None},
        {"$set": {**data, "updated_at": datetime.now(timezone.utc)}},
    )
    return get_embedding_profile(profile_id)


def soft_delete_embedding_profile(profile_id: str) -> bool:
    result = profiles.update_one(
        {"_id": profile_id, "delete_at": None},
        {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


def get_embedding_settings() -> dict[str, Any]:
    document = settings.find_one({"_id": SETTINGS_ID}) or {}
    return {
        "active_profile_id": str(document.get("active_profile_id") or ENVIRONMENT_PROFILE_ID),
        "runtime_profile_id": str(document.get("runtime_profile_id") or ENVIRONMENT_PROFILE_ID),
        "restart_required": bool(document.get("restart_required", False)),
        "reindex_required": bool(document.get("reindex_required", False)),
        "activated_at": document.get("activated_at"),
        "runtime_started_at": document.get("runtime_started_at"),
    }


def activate_embedding_profile(profile_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    current = get_embedding_settings()
    changed = current["active_profile_id"] != profile_id
    settings.update_one(
        {"_id": SETTINGS_ID},
        {
            "$set": {
                "active_profile_id": profile_id,
                "restart_required": current["runtime_profile_id"] != profile_id,
                "reindex_required": current["reindex_required"] or changed,
                "activated_at": now,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return get_embedding_settings()


def mark_embedding_runtime_started(profile_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    current = get_embedding_settings()
    settings.update_one(
        {"_id": SETTINGS_ID},
        {
            "$set": {
                "runtime_profile_id": profile_id,
                "restart_required": current["active_profile_id"] != profile_id,
                "runtime_started_at": now,
                "updated_at": now,
            },
            "$setOnInsert": {
                "active_profile_id": profile_id,
                "reindex_required": False,
                "created_at": now,
            },
        },
        upsert=True,
    )
    return get_embedding_settings()


def mark_embedding_reindex_complete(profile_id: str) -> dict[str, Any]:
    current = get_embedding_settings()
    if current["active_profile_id"] != profile_id or current["runtime_profile_id"] != profile_id:
        raise ValueError("The selected embedding profile must be running before re-index can be completed")
    settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": {"reindex_required": False, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return get_embedding_settings()
