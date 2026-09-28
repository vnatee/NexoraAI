from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core.effective_access import AccessControlError
from core.provider_secrets import decrypt_secret, encrypt_secret
from mongo_table_connecters.mongo_connector import get_database

LEASE_DURATION = timedelta(minutes=5)
DEFAULT_RETENTION_HOURS = 168
MAX_RETENTION_HOURS = 720

collection = get_database()["agent_invocation_jobs"]


class AgentInvocationJobError(AccessControlError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message, status_code=status_code)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _retention_hours() -> int:
    try:
        value = int(os.getenv("AGENT_INVOCATION_JOB_RETENTION_HOURS", str(DEFAULT_RETENTION_HOURS)))
    except ValueError:
        value = DEFAULT_RETENTION_HOURS
    return max(1, min(value, MAX_RETENTION_HOURS))


def _safe_error(error: Exception | str) -> dict[str, str]:
    code = (
        error.__class__.__name__ if isinstance(error, Exception) else "InvocationError"
    )
    return {"code": str(code)[:100], "message": "Agent invocation failed"}


def ensure_agent_invocation_job_indexes() -> None:
    collection.create_index([("status", 1), ("lease_expires_at", 1), ("updated_at", 1)])
    collection.create_index([("key_id", 1), ("created_at", -1)])
    collection.create_index("expires_at", expireAfterSeconds=0)
    collection.create_index(
        [("key_id", 1), ("idempotency_key_hash", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key_hash": {"$type": "string"}},
        name="agent_invocation_job_idempotency",
    )


def _request_fingerprint(agent_id: str, input_text: str, conversation_id: str | None) -> str:
    canonical = json.dumps(
        {
            "agent_id": str(agent_id),
            "input": str(input_text),
            "conversation_id": str(conversation_id or ""),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    signing_key = os.getenv("APP_DATA_ENCRYPTION_KEY", "").strip()
    if not signing_key:
        raise AgentInvocationJobError(
            "APP_DATA_ENCRYPTION_KEY is required for invocation jobs",
            status_code=503,
        )
    return hmac.new(
        signing_key.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _idempotency_hash(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if len(normalized) > 128:
        raise AgentInvocationJobError("Idempotency-Key must not exceed 128 characters")
    signing_key = os.getenv("APP_DATA_ENCRYPTION_KEY", "").strip()
    if not signing_key:
        raise AgentInvocationJobError(
            "APP_DATA_ENCRYPTION_KEY is required for invocation jobs",
            status_code=503,
        )
    return hmac.new(
        signing_key.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_agent_invocation_job(
    *,
    key_id: str,
    team_id: str,
    agent_id: str,
    input_text: str,
    conversation_id: str | None,
    idempotency_key: str | None,
) -> tuple[dict[str, Any], bool]:
    now = _now()
    idempotency_key_hash = _idempotency_hash(idempotency_key)
    fingerprint = _request_fingerprint(agent_id, input_text, conversation_id)
    if idempotency_key_hash:
        existing = collection.find_one(
            {"key_id": str(key_id), "idempotency_key_hash": idempotency_key_hash}
        )
        if existing:
            if existing.get("request_fingerprint") != fingerprint:
                raise AgentInvocationJobError(
                    "Idempotency-Key was already used for a different request",
                    status_code=409,
                )
            return existing, False

    document = {
        "_id": str(uuid.uuid4()),
        "key_id": str(key_id),
        "team_id": str(team_id),
        "agent_id": str(agent_id),
        "input_ciphertext": encrypt_secret(str(input_text)),
        "conversation_id": str(conversation_id or "") or None,
        "idempotency_key_hash": idempotency_key_hash,
        "request_fingerprint": fingerprint,
        "status": "queued",
        "attempt": 0,
        "worker_id": None,
        "lease_expires_at": None,
        "result_ciphertext": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "expires_at": now + timedelta(hours=_retention_hours()),
    }
    try:
        collection.insert_one(document)
        return document, True
    except DuplicateKeyError:
        existing = collection.find_one(
            {"key_id": str(key_id), "idempotency_key_hash": idempotency_key_hash}
        )
        if existing and existing.get("request_fingerprint") == fingerprint:
            return existing, False
        raise AgentInvocationJobError(
            "Idempotency-Key was already used for a different request",
            status_code=409,
        )


def get_agent_invocation_job(job_id: str) -> dict[str, Any] | None:
    return collection.find_one({"_id": str(job_id or "")})


def decrypt_agent_invocation_job_input(document: dict[str, Any]) -> str:
    value = decrypt_secret(document.get("input_ciphertext"))
    if not value:
        raise AgentInvocationJobError("Invocation job input is unavailable", status_code=409)
    return value


def serialize_agent_invocation_job(
    document: dict[str, Any], *, include_result: bool = True
) -> dict[str, Any]:
    result = None
    if include_result and document.get("status") == "succeeded":
        raw_result = decrypt_secret(document.get("result_ciphertext"))
        if raw_result:
            result = json.loads(raw_result)
    return {
        "id": str(document.get("_id") or ""),
        "object": "agent.invocation.job",
        "agent_id": str(document.get("agent_id") or ""),
        "conversation_id": document.get("conversation_id"),
        "status": str(document.get("status") or ""),
        "attempt": int(document.get("attempt") or 0),
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
        "started_at": document.get("started_at"),
        "completed_at": document.get("completed_at"),
        "expires_at": document.get("expires_at"),
        "result": result,
        "error": document.get("error") if document.get("status") == "failed" else None,
    }


def claim_agent_invocation_job(
    job_id: str, worker_id: str, *, at: datetime | None = None
) -> dict[str, Any] | None:
    now = at or _now()
    return collection.find_one_and_update(
        {
            "_id": str(job_id),
            "$or": [
                {"status": "queued", "worker_id": {"$in": [None, ""]}},
                {"status": "running", "lease_expires_at": {"$lte": now}},
            ],
        },
        {
            "$set": {
                "status": "running",
                "worker_id": str(worker_id),
                "lease_expires_at": now + LEASE_DURATION,
                "started_at": now,
                "updated_at": now,
                "error": None,
            },
            "$inc": {"attempt": 1},
        },
        return_document=ReturnDocument.AFTER,
    )


def heartbeat_agent_invocation_job(job_id: str, worker_id: str) -> bool:
    now = _now()
    result = collection.update_one(
        {"_id": str(job_id), "status": "running", "worker_id": str(worker_id)},
        {"$set": {"lease_expires_at": now + LEASE_DURATION, "updated_at": now}},
    )
    return bool(result.modified_count)


def release_agent_invocation_job(job_id: str, worker_id: str) -> None:
    now = _now()
    collection.update_one(
        {"_id": str(job_id), "status": "running", "worker_id": str(worker_id)},
        {
            "$set": {
                "status": "queued",
                "worker_id": None,
                "lease_expires_at": None,
                "updated_at": now,
            }
        },
    )


def complete_agent_invocation_job(
    job_id: str,
    worker_id: str,
    *,
    result: dict[str, Any] | None = None,
    error: Exception | str | None = None,
) -> dict[str, Any] | None:
    now = _now()
    succeeded = error is None and result is not None
    updates = {
        "status": "succeeded" if succeeded else "failed",
        "worker_id": None,
        "lease_expires_at": None,
        "updated_at": now,
        "completed_at": now,
        "result_ciphertext": (
            encrypt_secret(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
            if succeeded
            else None
        ),
        "error": None if succeeded else _safe_error(error or "Agent invocation failed"),
    }
    return collection.find_one_and_update(
        {"_id": str(job_id), "status": "running", "worker_id": str(worker_id)},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )


def retry_agent_invocation_job(job_id: str, key_id: str) -> dict[str, Any] | None:
    now = _now()
    return collection.find_one_and_update(
        {
            "_id": str(job_id),
            "key_id": str(key_id),
            "status": "failed",
            "input_ciphertext": {"$type": "string"},
            "expires_at": {"$gt": now},
        },
        {
            "$set": {
                "status": "queued",
                "worker_id": None,
                "lease_expires_at": None,
                "error": None,
                "completed_at": None,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )


def list_recoverable_agent_invocation_jobs(
    *, at: datetime | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    now = at or _now()
    return list(
        collection.find(
            {
                "expires_at": {"$gt": now},
                "$or": [
                    {"status": "queued", "worker_id": {"$in": [None, ""]}},
                    {"status": "running", "lease_expires_at": {"$lte": now}},
                ],
            }
        )
        .sort("updated_at", 1)
        .limit(max(1, min(int(limit), 100)))
    )
