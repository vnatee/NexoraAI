from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pymongo.errors import DuplicateKeyError

from core.licensing import (
    EntitlementClaims,
    LicenseEvaluation,
    LicenseVerificationError,
    evaluate_verified_claims,
    unlicensed_evaluation,
    verify_license_key,
)
from core.provider_secrets import decrypt_secret, encrypt_secret
from mongo_table_connecters.mongo_connector import get_database

SETTINGS_ID = "licensing"
INSTALLATION_ID = "licensing:installation"
TRIAL_DAYS = 14
AUDIT_RETENTION_DAYS = 365

database = get_database()
collection = database["application_settings"]
audit_collection = database["license_audit_events"]


def ensure_license_indexes() -> None:
    try:
        audit_collection.create_index("expires_at", expireAfterSeconds=0, name="license_audit_expiry")
        audit_collection.create_index([("created_at", -1)], name="license_audit_created")
    except Exception:
        logging.warning("Unable to create license audit indexes", exc_info=True)


def get_or_create_installation_id() -> str:
    document = collection.find_one({"_id": INSTALLATION_ID})
    if document and document.get("installation_id"):
        return str(document["installation_id"])
    generated = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    collection.update_one(
        {"_id": INSTALLATION_ID},
        {"$setOnInsert": {"installation_id": generated, "created_at": now}},
        upsert=True,
    )
    document = collection.find_one({"_id": INSTALLATION_ID})
    if not document or not document.get("installation_id"):
        raise RuntimeError("Unable to persist installation identity")
    return str(document["installation_id"])


def start_trial(*, actor_id: str, now: datetime | None = None) -> dict[str, Any]:
    instant = _utc(now)
    installation_id = get_or_create_installation_id()
    current = collection.find_one({"_id": SETTINGS_ID}) or {}
    if current.get("license_ciphertext"):
        raise ValueError("A commercial license is already installed")
    if not current.get("trial_started_at"):
        activated = False
        try:
            result = collection.update_one(
                {"_id": SETTINGS_ID, "trial_started_at": {"$exists": False}},
                {
                    "$set": {
                        "trial_started_at": instant,
                        "trial_expires_at": instant + timedelta(days=TRIAL_DAYS),
                        "updated_at": instant,
                    },
                    "$setOnInsert": {"created_at": instant},
                },
                upsert=True,
            )
            activated = bool(result.matched_count or result.upserted_id)
        except DuplicateKeyError:
            pass
        current = collection.find_one({"_id": SETTINGS_ID}) or {}
        if not current.get("trial_started_at"):
            raise RuntimeError("Unable to persist trial activation")
        if activated:
            _audit("trial_started", actor_id=actor_id, state="active", instant=instant)
    return _serialize_trial(current, installation_id=installation_id, now=instant)


def import_license(
    license_key: str,
    verification_keys: Mapping[str, Ed25519PublicKey],
    *,
    actor_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    instant = _utc(now)
    installation_id = get_or_create_installation_id()
    claims = verify_license_key(license_key, verification_keys)
    evaluation = evaluate_verified_claims(claims, installation_id=installation_id, now=instant)
    if evaluation.state not in {"active", "grace"}:
        _audit(
            "license_import_rejected",
            actor_id=actor_id,
            state=evaluation.state,
            instant=instant,
            license_id=claims.license_id,
        )
        raise LicenseVerificationError(f"license cannot be activated: {evaluation.reason}")

    ciphertext = encrypt_secret(license_key)
    if not ciphertext:
        raise RuntimeError("Unable to protect license key")
    collection.update_one(
        {"_id": SETTINGS_ID},
        {
            "$set": {
                "license_ciphertext": ciphertext,
                "license_id": claims.license_id,
                "customer_id": claims.customer_id,
                "edition": claims.edition,
                "license_expires_at": claims.expires_at,
                "license_imported_at": instant,
                "license_imported_by": str(actor_id)[:128],
                "last_validated_at": instant,
                "last_validation_state": evaluation.state,
                "updated_at": instant,
            },
            "$setOnInsert": {"created_at": instant},
        },
        upsert=True,
    )
    _audit(
        "license_imported",
        actor_id=actor_id,
        state=evaluation.state,
        instant=instant,
        license_id=claims.license_id,
    )
    return _serialize_license(evaluation, installation_id=installation_id)


def get_license_status(
    verification_keys: Mapping[str, Ed25519PublicKey],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    instant = _utc(now)
    installation_id = get_or_create_installation_id()
    document = collection.find_one({"_id": SETTINGS_ID}) or {}
    encrypted = document.get("license_ciphertext")
    if encrypted:
        try:
            license_key = decrypt_secret(str(encrypted))
            if not license_key:
                raise LicenseVerificationError("stored license is unavailable")
            claims = verify_license_key(license_key, verification_keys)
            evaluation = evaluate_verified_claims(claims, installation_id=installation_id, now=instant)
            return _serialize_license(evaluation, installation_id=installation_id)
        except (LicenseVerificationError, ValueError):
            return {
                "status": "invalid",
                "reason": "stored_license_invalid",
                "source": "license",
                "installation_id": installation_id,
                "audit_mode": True,
                "trial_available": False,
            }
    if document.get("trial_started_at"):
        return _serialize_trial(document, installation_id=installation_id, now=instant)
    return _serialize_evaluation(
        unlicensed_evaluation(now=instant),
        source="none",
        installation_id=installation_id,
        trial_available=True,
    )


def _serialize_license(evaluation: LicenseEvaluation, *, installation_id: str) -> dict[str, Any]:
    claims = evaluation.claims
    if claims is None:
        raise ValueError("license evaluation has no claims")
    result = _serialize_evaluation(
        evaluation,
        source="license",
        installation_id=installation_id,
        trial_available=False,
    )
    result["license"] = _serialize_claims(claims)
    return result


def _serialize_trial(document: dict[str, Any], *, installation_id: str, now: datetime) -> dict[str, Any]:
    started_at = _stored_utc(document["trial_started_at"])
    expires_at = _stored_utc(document.get("trial_expires_at") or (started_at + timedelta(days=TRIAL_DAYS)))
    state = "active" if now <= expires_at else "expired"
    return {
        "status": state,
        "reason": "trial_active" if state == "active" else "trial_expired",
        "source": "trial",
        "installation_id": installation_id,
        "audit_mode": True,
        "trial_available": False,
        "trial": {
            "started_at": started_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "duration_days": TRIAL_DAYS,
        },
    }


def _serialize_evaluation(
    evaluation: LicenseEvaluation,
    *,
    source: str,
    installation_id: str,
    trial_available: bool,
) -> dict[str, Any]:
    return {
        "status": evaluation.state,
        "reason": evaluation.reason,
        "source": source,
        "installation_id": installation_id,
        "audit_mode": True,
        "trial_available": trial_available,
        "evaluated_at": evaluation.evaluated_at.isoformat(),
    }


def _serialize_claims(claims: EntitlementClaims) -> dict[str, Any]:
    return {
        "license_id": claims.license_id,
        "customer_id": claims.customer_id,
        "product": claims.product,
        "edition": claims.edition,
        "issuer": claims.issuer,
        "key_id": claims.key_id,
        "not_before": claims.not_before.isoformat(),
        "expires_at": claims.expires_at.isoformat(),
        "grace_days": claims.grace_days,
        "features": dict(claims.features),
        "capacities": dict(claims.capacities),
        "installation_id": claims.installation_id,
    }


def _audit(
    action: str,
    *,
    actor_id: str,
    state: str,
    instant: datetime,
    license_id: str = "",
) -> None:
    if os.getenv("DISABLE_LICENSE_AUDIT_PERSISTENCE", "").lower() == "true":
        return
    try:
        audit_collection.insert_one(
            {
                "_id": str(uuid.uuid4()),
                "action": str(action)[:50],
                "actor_id": str(actor_id)[:128],
                "state": str(state)[:20],
                "license_id": str(license_id)[:128],
                "created_at": instant,
                "expires_at": instant + timedelta(days=AUDIT_RETENTION_DAYS),
            }
        )
    except Exception:
        logging.warning("Unable to persist license audit event", exc_info=True)


def _utc(value: datetime | None) -> datetime:
    instant = value or datetime.now(timezone.utc)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("license timestamps must include a timezone")
    return instant.astimezone(timezone.utc)


def _stored_utc(value: datetime) -> datetime:
    """Normalize MongoDB datetimes, which PyMongo returns as naive UTC by default."""

    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
