import uuid
from datetime import datetime, timezone
from typing import Any

from mongo_table_connecters.mongo_connector import get_database


collection = get_database()["business_document_bindings"]


def normalize_business_document_binding(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Business document binding payload must be an object")
    permissions = data.get("permissions")
    if permissions is None:
        permissions = ["read"]
    if not isinstance(permissions, list):
        raise ValueError("permissions must be an array")
    permissions = list(dict.fromkeys(str(value).strip().lower() for value in permissions if str(value).strip().lower() in {"read", "create"}))
    if not permissions:
        raise ValueError("At least one document permission is required")
    return {
        "agent_id": str(data.get("agent_id") or "").strip(),
        "connection_id": str(data.get("connection_id") or "").strip(),
        "enabled": data.get("enabled", True) is not False,
        "permissions": permissions,
    }


def insert_business_document_binding(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document = {"_id": str(uuid.uuid4()), **data, "created_at": now, "updated_at": now, "delete_at": None}
    collection.insert_one(document)
    return document


def list_business_document_bindings(agent_id: str, *, enabled_only: bool = False) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"agent_id": agent_id, "delete_at": None}
    if enabled_only:
        query["enabled"] = True
    return list(collection.find(query))


def get_business_document_binding(binding_id: str) -> dict[str, Any] | None:
    return collection.find_one({"_id": binding_id, "delete_at": None})


def update_business_document_binding(binding_id: str, data: dict[str, Any]) -> bool:
    return collection.update_one(
        {"_id": binding_id, "delete_at": None},
        {"$set": {**data, "updated_at": datetime.now(timezone.utc)}},
    ).matched_count > 0


def delete_business_document_binding(binding_id: str) -> bool:
    return collection.update_one(
        {"_id": binding_id, "delete_at": None},
        {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc)}},
    ).modified_count > 0
