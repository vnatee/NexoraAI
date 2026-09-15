import uuid
from datetime import datetime, timezone
from typing import Any

from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["mail_bindings"]


def normalize_mail_binding(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Mail binding payload must be an object")
    permissions = data.get("permissions")
    if permissions is None:
        permissions = ["read", "send"]
    if not isinstance(permissions, list):
        raise ValueError("permissions must be an array")
    permissions = [item for item in (str(v).lower() for v in permissions) if item in ("read", "send")]
    if not permissions:
        raise ValueError("At least one mail permission (read or send) is required")
    allowed_domains = data.get("allowed_recipient_domains") or []
    if not isinstance(allowed_domains, list):
        raise ValueError("allowed_recipient_domains must be an array")
    return {
        "agent_id": str(data.get("agent_id") or ""),
        "email_id": str(data.get("email_id") or ""),
        "enabled": data.get("enabled", True) is not False,
        "permissions": list(dict.fromkeys(permissions)),
        "allowed_recipient_domains": [str(v).strip().lower() for v in allowed_domains if str(v).strip()][:50],
        "max_recipients": max(1, min(int(data.get("max_recipients") or 10), 100)),
        "is_html": data.get("is_html", False) is True,
        "subject": str(data.get("subject") or "")[:1000],
        "body": str(data.get("body") or "")[:20000],
        "default_to": list(data.get("default_to") or [])[:100],
        "default_cc": list(data.get("default_cc") or [])[:100],
        "default_bcc": list(data.get("default_bcc") or [])[:100],
    }


def insert_mail_binding(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document = {"_id": str(uuid.uuid4()), **data, "created_at": now, "updated_at": now, "delete_at": None}
    collection.insert_one(document)
    return document


def list_mail_bindings(agent_id: str, *, enabled_only: bool = False) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"agent_id": agent_id, "delete_at": None}
    if enabled_only:
        query["enabled"] = True
    return list(collection.find(query))


def get_mail_binding(binding_id: str) -> dict[str, Any] | None:
    return collection.find_one({"_id": binding_id, "delete_at": None})


def update_mail_binding(binding_id: str, **values: Any) -> bool:
    allowed_fields = {
        "agent_id", "email_id", "enabled", "permissions",
        "allowed_recipient_domains", "max_recipients", "is_html",
        "subject", "body", "default_to", "default_cc", "default_bcc",
    }
    allowed = {key: value for key, value in values.items() if key in allowed_fields}
    if not allowed:
        return False
    allowed["updated_at"] = datetime.now(timezone.utc)
    return collection.update_one({"_id": binding_id, "delete_at": None}, {"$set": allowed}).matched_count > 0


def delete_mail_binding(binding_id: str) -> bool:
    return collection.update_one(
        {"_id": binding_id, "delete_at": None},
        {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc)}},
    ).modified_count > 0
