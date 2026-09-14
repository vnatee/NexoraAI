from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from mongo_table_connecters.mongo_connector import get_database

db = get_database()
identities_collection = db["auth_identities"]
sessions_collection = db["auth_sessions"]
requests_collection = db["auth_identity_link_requests"]
audit_collection = db["auth_identity_audit_events"]
users_collection = db["users"]
REQUEST_DAYS = 7
AUDIT_DAYS = 365


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ensure_identity_management_indexes() -> None:
    requests_collection.create_index("expires_at", expireAfterSeconds=0, name="auth_link_request_expiry")
    requests_collection.create_index(
        [("provider", 1), ("subject", 1)], unique=True, name="auth_link_request_provider_subject"
    )
    requests_collection.create_index([("status", 1), ("updated_at", -1)], name="auth_link_request_status")
    audit_collection.create_index("created_at", name="auth_identity_audit_created_at")
    audit_collection.create_index("expires_at", expireAfterSeconds=0, name="auth_identity_audit_expiry")


def record_federated_link_request(
    *, provider: str, issuer: str, subject: str, email: str, suggested_user_id: str
) -> dict[str, Any]:
    now = _now()
    request_id = _digest(f"{provider}\0{subject}")
    requests_collection.update_one(
        {"_id": request_id},
        {
            "$set": {
                "provider": provider,
                "issuer": issuer,
                "subject": subject,
                "email": email,
                "suggested_user_id": str(suggested_user_id),
                "status": "pending",
                "updated_at": now,
                "expires_at": now + timedelta(days=REQUEST_DAYS),
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return requests_collection.find_one({"_id": request_id}) or {"_id": request_id}


def record_oidc_link_request(
    *, provider: str, issuer: str, subject: str, email: str, suggested_user_id: str
) -> dict[str, Any]:
    """Compatibility wrapper for the first OIDC-only implementation."""
    return record_federated_link_request(
        provider=provider,
        issuer=issuer,
        subject=subject,
        email=email,
        suggested_user_id=suggested_user_id,
    )


def list_identity_link_requests() -> list[dict[str, Any]]:
    now = _now()
    return list(requests_collection.find({"status": "pending", "expires_at": {"$gt": now}}).sort("updated_at", -1))


def get_identity_link_request(request_id: str) -> dict[str, Any] | None:
    return requests_collection.find_one({"_id": str(request_id), "status": "pending"})


def list_federated_identities() -> list[dict[str, Any]]:
    return [
        item
        for item in identities_collection.find({"delete_at": None}).sort("created_at", -1)
        if str(item.get("provider") or "").startswith(("oidc:", "saml:"))
    ]


def list_oidc_identities() -> list[dict[str, Any]]:
    return list_federated_identities()


def federated_identity_user_ids(user_ids: list[str]) -> set[str]:
    if not user_ids:
        return set()
    return {
        str(item.get("user_id") or "")
        for item in identities_collection.find(
            {"user_id": {"$in": user_ids}, "delete_at": None, "active": True},
            {"user_id": 1, "provider": 1},
        )
        if str(item.get("provider") or "").startswith(("oidc:", "saml:"))
    }


def federated_identity_types_by_user_ids(user_ids: list[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    if not user_ids:
        return result
    for item in identities_collection.find(
        {"user_id": {"$in": user_ids}, "delete_at": None, "active": True},
        {"user_id": 1, "provider": 1},
    ):
        provider = str(item.get("provider") or "")
        provider_type = provider.split(":", 1)[0]
        if provider_type not in {"oidc", "saml"}:
            continue
        result.setdefault(str(item.get("user_id") or ""), set()).add(provider_type)
    return result


def oidc_identity_user_ids(user_ids: list[str]) -> set[str]:
    return federated_identity_user_ids(user_ids)


def approve_identity_link(request_id: str, user_id: str, *, actor_id: str) -> dict[str, Any]:
    request = requests_collection.find_one({"_id": str(request_id), "status": "pending"})
    if not request:
        raise ValueError("Identity link request was not found or is no longer pending")
    expires_at = request.get("expires_at")
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not expires_at or expires_at <= _now():
        raise ValueError("Identity link request has expired")
    user = users_collection.find_one({"_id": str(user_id), "delete_at": None, "active": True})
    if not user:
        raise ValueError("Target user is disabled or unavailable")
    if user.get("is_sys_admin") is True:
        raise ValueError("Federated identities cannot be linked to a System Administrator through this flow")
    provider = str(request.get("provider") or "")
    subject = str(request.get("subject") or "")
    if identities_collection.find_one(
        {"provider": provider, "username_normalized": subject, "delete_at": None}
    ):
        raise ValueError("This external identity is already linked")
    if identities_collection.find_one(
        {"provider": provider, "user_id": str(user_id), "delete_at": None, "active": True}
    ):
        raise ValueError("This user already has an identity for the selected provider")
    now = _now()
    identity = {
        "_id": str(uuid.uuid4()),
        "provider": provider,
        "issuer": str(request.get("issuer") or ""),
        "subject": subject,
        "username": str(request.get("email") or ""),
        "username_normalized": subject,
        "user_id": str(user_id),
        "active": True,
        "created_at": now,
        "updated_at": now,
        "delete_at": None,
    }
    try:
        identities_collection.insert_one(identity)
    except DuplicateKeyError as error:
        raise ValueError("This external identity is already linked") from error
    requests_collection.update_one(
        {"_id": str(request_id), "status": "pending"},
        {"$set": {"status": "approved", "reviewed_by": actor_id, "reviewed_at": now}},
    )
    _audit("linked", actor_id=actor_id, identity=identity)
    return identity


def reject_identity_link(request_id: str, *, actor_id: str) -> bool:
    now = _now()
    request = requests_collection.find_one({"_id": str(request_id), "status": "pending"})
    if not request:
        return False
    result = requests_collection.update_one(
        {"_id": str(request_id), "status": "pending"},
        {"$set": {"status": "rejected", "reviewed_by": actor_id, "reviewed_at": now}},
    )
    if result.modified_count:
        _audit(
            "link_rejected",
            actor_id=actor_id,
            identity={"provider": request.get("provider"), "user_id": request.get("suggested_user_id")},
        )
    return result.modified_count > 0


def unlink_federated_identity(identity_id: str, *, actor_id: str) -> bool:
    identity = identities_collection.find_one({"_id": str(identity_id), "delete_at": None, "active": True})
    if not identity or not str(identity.get("provider") or "").startswith(("oidc:", "saml:")):
        return False
    user_id = str(identity.get("user_id") or "")
    user = users_collection.find_one({"_id": user_id, "delete_at": None}) or {}
    other_identity = identities_collection.find_one(
        {"_id": {"$ne": str(identity_id)}, "user_id": user_id, "delete_at": None, "active": True}
    )
    has_implicit_entra = bool(
        user.get("ad_email") and user.get("created_by_auth_provider") not in {"local", "oidc", "saml"}
    )
    if not other_identity and not has_implicit_entra:
        raise ValueError("Add another sign-in method before unlinking the user's only identity")
    now = _now()
    sessions_collection.update_many(
        {"identity_id": str(identity_id), "revoked_at": None}, {"$set": {"revoked_at": now}}
    )
    result = identities_collection.delete_one({"_id": str(identity_id)})
    if result.deleted_count:
        _audit("unlinked", actor_id=actor_id, identity=identity)
    return result.deleted_count > 0


def unlink_oidc_identity(identity_id: str, *, actor_id: str) -> bool:
    return unlink_federated_identity(identity_id, actor_id=actor_id)


def list_identity_audit_events(limit: int = 50) -> list[dict[str, Any]]:
    return list(audit_collection.find({}).sort("created_at", -1).limit(max(1, min(int(limit), 100))))


def _audit(action: str, *, actor_id: str, identity: dict[str, Any]) -> None:
    audit_collection.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "action": action,
            "actor_id": str(actor_id),
            "target_user_id": str(identity.get("user_id") or ""),
            "provider": str(identity.get("provider") or ""),
            "identity_id": str(identity.get("_id") or ""),
            "created_at": _now(),
            "expires_at": _now() + timedelta(days=AUDIT_DAYS),
        }
    )
