from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument

from core.effective_access import AccessControlError
from mongo_table_connecters.mongo_connector import get_database

KEY_PREFIX = "nxai_"
DEFAULT_EXPIRY_DAYS = 90
MAX_EXPIRY_DAYS = 365
DEFAULT_RATE_LIMIT_PER_MINUTE = 60
MAX_RATE_LIMIT_PER_MINUTE = 1000
ACCESS_TYPE_INTERNAL = "internal_service"
ACCESS_TYPE_EXTERNAL = "external_customer"
SUPPORTED_ACCESS_TYPES = {ACCESS_TYPE_INTERNAL, ACCESS_TYPE_EXTERNAL}

database = get_database()
keys_collection = database["agent_invocation_keys"]
rate_limits_collection = database["agent_invocation_rate_limits"]
audit_collection = database["agent_invocation_audit_events"]


class AgentInvocationKeyError(AccessControlError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _bounded_text(value: object, field: str, maximum: int, *, required: bool = False) -> str:
    normalized = str(value or "").strip()
    if required and not normalized:
        raise AgentInvocationKeyError(f"{field} is required")
    if len(normalized) > maximum:
        raise AgentInvocationKeyError(f"{field} is too long")
    return normalized


def _unique_ids(value: object, field: str, *, required: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise AgentInvocationKeyError(f"{field} must be an array")
    result: list[str] = []
    for item in value:
        normalized = str(item or "").strip()
        if not normalized:
            raise AgentInvocationKeyError(f"{field} contains an invalid value")
        if normalized not in result:
            result.append(normalized)
    if len(result) > 100:
        raise AgentInvocationKeyError(f"{field} supports at most 100 values")
    if required and not result:
        raise AgentInvocationKeyError(f"{field} must contain at least one Agent")
    return result


def normalize_agent_invocation_access_type(value: object) -> str:
    normalized = str(value or ACCESS_TYPE_INTERNAL).strip().lower()
    if normalized not in SUPPORTED_ACCESS_TYPES:
        raise AgentInvocationKeyError(
            "access_type must be internal_service or external_customer"
        )
    return normalized


def ensure_agent_invocation_key_indexes() -> None:
    keys_collection.create_index(
        [("team_id", 1), ("active", 1), ("delete_at", 1)],
        name="agent_invocation_key_team",
    )
    keys_collection.create_index("key_prefix", unique=True, name="agent_invocation_key_prefix")
    keys_collection.create_index("expires_at", name="agent_invocation_key_expiry")
    rate_limits_collection.create_index(
        "expires_at", expireAfterSeconds=0, name="agent_invocation_rate_limit_expiry"
    )
    audit_collection.create_index(
        [("created_at", -1)], name="agent_invocation_audit_created"
    )
    audit_collection.create_index(
        "expires_at", expireAfterSeconds=0, name="agent_invocation_audit_expiry"
    )


def serialize_agent_invocation_key(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "_id": str(document.get("_id") or ""),
        "team_id": str(document.get("team_id") or ""),
        "name": str(document.get("name") or ""),
        "access_type": normalize_agent_invocation_access_type(
            document.get("access_type")
        ),
        "key_prefix": str(document.get("key_prefix") or ""),
        "allowed_agent_ids": list(document.get("allowed_agent_ids") or []),
        "allowed_data_group_ids": list(document.get("allowed_data_group_ids") or []),
        "allow_global_knowledge": document.get("allow_global_knowledge") is True,
        "rate_limit_per_minute": int(
            document.get("rate_limit_per_minute") or DEFAULT_RATE_LIMIT_PER_MINUTE
        ),
        "active": document.get("active") is True,
        "expires_at": document.get("expires_at"),
        "created_at": document.get("created_at"),
        "created_by": str(document.get("created_by") or ""),
        "last_used_at": document.get("last_used_at"),
        "revoked_at": document.get("revoked_at"),
        "replaced_by": str(document.get("replaced_by") or "") or None,
    }


def create_agent_invocation_key(
    *,
    team_id: str,
    name: str,
    allowed_agent_ids: object,
    allowed_data_group_ids: object,
    allow_global_knowledge: bool,
    expiry_days: int = DEFAULT_EXPIRY_DAYS,
    rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE,
    created_by: str,
    access_type: str = ACCESS_TYPE_INTERNAL,
) -> tuple[dict[str, Any], str]:
    normalized_team_id = _bounded_text(team_id, "team_id", 128, required=True)
    normalized_name = _bounded_text(name, "name", 120, required=True)
    normalized_access_type = normalize_agent_invocation_access_type(access_type)
    agent_ids = _unique_ids(allowed_agent_ids, "allowed_agent_ids", required=True)
    data_group_ids = _unique_ids(allowed_data_group_ids, "allowed_data_group_ids")
    try:
        normalized_expiry_days = int(expiry_days)
        normalized_rate_limit = int(rate_limit_per_minute)
    except (TypeError, ValueError) as error:
        raise AgentInvocationKeyError(
            "expiry_days and rate_limit_per_minute must be integers"
        ) from error
    if not 1 <= normalized_expiry_days <= MAX_EXPIRY_DAYS:
        raise AgentInvocationKeyError(
            f"expiry_days must be between 1 and {MAX_EXPIRY_DAYS}"
        )
    if not 1 <= normalized_rate_limit <= MAX_RATE_LIMIT_PER_MINUTE:
        raise AgentInvocationKeyError(
            f"rate_limit_per_minute must be between 1 and {MAX_RATE_LIMIT_PER_MINUTE}"
        )
    if normalized_access_type == ACCESS_TYPE_EXTERNAL and allow_global_knowledge:
        raise AgentInvocationKeyError(
            "External customer API keys cannot access Global Knowledge"
        )

    now = _now()
    key_id = str(uuid.uuid4())
    public_prefix = f"{KEY_PREFIX}{key_id}"
    token = f"{public_prefix}.{secrets.token_urlsafe(32)}"
    document = {
        "_id": key_id,
        "team_id": normalized_team_id,
        "name": normalized_name,
        "access_type": normalized_access_type,
        "key_prefix": public_prefix,
        "token_digest": _token_digest(token),
        "allowed_agent_ids": agent_ids,
        "allowed_data_group_ids": data_group_ids,
        "allow_global_knowledge": allow_global_knowledge is True,
        "rate_limit_per_minute": normalized_rate_limit,
        "active": True,
        "expires_at": now + timedelta(days=normalized_expiry_days),
        "created_at": now,
        "updated_at": now,
        "created_by": str(created_by or ""),
        "last_used_at": None,
        "revoked_at": None,
        "revoked_by": None,
        "replaced_by": None,
        "delete_at": None,
    }
    keys_collection.insert_one(document)
    return serialize_agent_invocation_key(document), token


def list_agent_invocation_keys(team_id: str) -> list[dict[str, Any]]:
    documents = keys_collection.find(
        {"team_id": str(team_id or ""), "delete_at": None}
    ).sort("created_at", -1)
    return [serialize_agent_invocation_key(item) for item in documents]


def get_agent_invocation_key(key_id: str) -> dict[str, Any] | None:
    return keys_collection.find_one({"_id": str(key_id or ""), "delete_at": None})


def revoke_agent_invocation_key(key_id: str, *, actor_id: str) -> bool:
    now = _now()
    result = keys_collection.update_one(
        {"_id": str(key_id or ""), "delete_at": None, "active": True},
        {
            "$set": {
                "active": False,
                "revoked_at": now,
                "revoked_by": str(actor_id or ""),
                "updated_at": now,
            }
        },
    )
    return bool(result.modified_count)


def rotate_agent_invocation_key(
    key_id: str, *, actor_id: str, expiry_days: int = DEFAULT_EXPIRY_DAYS
) -> tuple[dict[str, Any], str]:
    current = get_agent_invocation_key(key_id)
    if not current:
        raise AgentInvocationKeyError("API key not found", status_code=404)
    if current.get("active") is not True or current.get("revoked_at") is not None:
        raise AgentInvocationKeyError(
            "Only an active API key can be rotated", status_code=409
        )
    created, token = create_agent_invocation_key(
        team_id=str(current.get("team_id") or ""),
        name=f"{str(current.get('name') or 'API key')} (rotated)",
        access_type=normalize_agent_invocation_access_type(
            current.get("access_type")
        ),
        allowed_agent_ids=current.get("allowed_agent_ids") or [],
        allowed_data_group_ids=current.get("allowed_data_group_ids") or [],
        allow_global_knowledge=current.get("allow_global_knowledge") is True,
        expiry_days=expiry_days,
        rate_limit_per_minute=int(
            current.get("rate_limit_per_minute") or DEFAULT_RATE_LIMIT_PER_MINUTE
        ),
        created_by=actor_id,
    )
    now = _now()
    result = keys_collection.update_one(
        {
            "_id": str(key_id),
            "delete_at": None,
            "active": True,
            "revoked_at": None,
        },
        {
            "$set": {
                "active": False,
                "revoked_at": now,
                "revoked_by": str(actor_id or ""),
                "replaced_by": created["_id"],
                "updated_at": now,
            }
        },
    )
    if not result.modified_count:
        revoke_agent_invocation_key(created["_id"], actor_id=actor_id)
        raise AgentInvocationKeyError(
            "API key could not be rotated because its state changed",
            status_code=409,
        )
    return created, token


def validate_agent_invocation_key_document(
    document: dict[str, Any] | None,
) -> dict[str, Any]:
    if not document:
        raise AgentInvocationKeyError("Invalid API key", status_code=401)
    if document.get("active") is not True or document.get("revoked_at") is not None:
        raise AgentInvocationKeyError("API key is revoked", status_code=401)
    expires_at = document.get("expires_at")
    if not isinstance(expires_at, datetime):
        raise AgentInvocationKeyError("API key expiry is invalid", status_code=401)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= _now():
        raise AgentInvocationKeyError("API key has expired", status_code=401)
    return document


def authenticate_agent_invocation_key(token: str) -> dict[str, Any]:
    normalized = str(token or "").strip()
    if not normalized.startswith(KEY_PREFIX) or "." not in normalized:
        raise AgentInvocationKeyError("Invalid API key", status_code=401)
    public_prefix = normalized.split(".", 1)[0]
    document = keys_collection.find_one(
        {"key_prefix": public_prefix, "delete_at": None}
    )
    if not document or not hmac.compare_digest(
        str(document.get("token_digest") or ""), _token_digest(normalized)
    ):
        raise AgentInvocationKeyError("Invalid API key", status_code=401)
    return validate_agent_invocation_key_document(document)


def enforce_agent_invocation_rate_limit(document: dict[str, Any]) -> None:
    now = _now()
    bucket = int(now.timestamp()) // 60
    counter = rate_limits_collection.find_one_and_update(
        {"_id": f"{document['_id']}:{bucket}"},
        {
            "$inc": {"requests": 1},
            "$setOnInsert": {"expires_at": now + timedelta(minutes=2)},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    limit = int(document.get("rate_limit_per_minute") or DEFAULT_RATE_LIMIT_PER_MINUTE)
    if int((counter or {}).get("requests") or 0) > limit:
        raise AgentInvocationKeyError("API key rate limit exceeded", status_code=429)


def mark_agent_invocation_key_used(key_id: str) -> None:
    keys_collection.update_one(
        {"_id": str(key_id or ""), "active": True, "delete_at": None},
        {"$set": {"last_used_at": _now()}},
    )


def insert_agent_invocation_audit(
    *,
    request_id: str,
    key_id: str,
    team_id: str,
    agent_id: str,
    event_type: str,
    status: str,
    duration_ms: int | None = None,
    error_code: str | None = None,
    access_type: str = ACCESS_TYPE_INTERNAL,
) -> None:
    retention_days = max(
        1,
        min(
            int(os.getenv("AGENT_INVOCATION_AUDIT_RETENTION_DAYS", "90")),
            3650,
        ),
    )
    now = _now()
    audit_collection.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "request_id": str(request_id),
            "key_id": str(key_id),
            "team_id": str(team_id),
            "agent_id": str(agent_id),
            "event_type": str(event_type),
            "access_type": normalize_agent_invocation_access_type(access_type),
            "status": str(status),
            "duration_ms": duration_ms,
            "error_code": str(error_code or "") or None,
            "created_at": now,
            "expires_at": now + timedelta(days=retention_days),
        }
    )
