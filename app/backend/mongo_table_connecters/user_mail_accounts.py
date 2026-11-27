"""User-owned mailbox credentials linked to a Team Mail Profile."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from core.provider_secrets import decrypt_secret, encrypt_secret
from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["user_mail_accounts"]


def ensure_user_mail_account_indexes() -> None:
    collection.create_index(
        [("user_id", 1), ("profile_id", 1)],
        unique=True,
        partialFilterExpression={"delete_at": None},
        name="unique_active_user_mail_profile",
    )


def normalize_user_mail_account(
    data: object,
    *,
    profile: dict[str, Any],
    existing: dict[str, Any] | None = None,
    managed_email: str = "",
) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Mail account payload must be an object")
    if profile.get("account_mode", "shared") != "personal":
        raise ValueError("The selected Team Mail Profile does not use personal accounts")
    old = existing or {}
    provider = str(profile.get("provider") or "")
    email_address = (
        managed_email
        if provider == "microsoft365"
        else str(data.get("email_address") or old.get("email_address") or "").strip()
    )
    if not email_address or "@" not in email_address:
        if provider == "microsoft365":
            raise ValueError("A managed Microsoft identity email is required")
        raise ValueError("Mailbox email address is required")

    public_config = dict(old.get("public_config") or {})
    incoming_public = data.get("public_config") or {}
    if not isinstance(incoming_public, dict):
        raise ValueError("public_config must be an object")
    if provider == "generic":
        public_config["username"] = str(
            incoming_public.get("username") or email_address
        ).strip()[:320]

    secrets_ciphertext = old.get("secrets_ciphertext")
    secrets = data.get("secrets")
    if secrets is not None:
        if not isinstance(secrets, dict):
            raise ValueError("secrets must be an object")
        normalized = {
            str(key): str(value)
            for key, value in secrets.items()
            if value not in (None, "")
        }
        required = {
            "microsoft365": set(),
            "gmail": {"refresh_token"},
            "generic": {"password"},
        }[provider]
        if not secrets_ciphertext and not required.issubset(normalized):
            missing = ", ".join(sorted(required - set(normalized)))
            raise ValueError(f"Missing personal mail credentials: {missing}")
        if normalized:
            secrets_ciphertext = encrypt_secret(
                json.dumps(normalized, ensure_ascii=False)
            )
    if provider != "microsoft365" and not secrets_ciphertext:
        raise ValueError("Personal mail credentials are required")

    return {
        "profile_id": str(profile["_id"]),
        "team_id": str(profile.get("team_id") or ""),
        "email_address": email_address[:320],
        "public_config": public_config,
        "secrets_ciphertext": secrets_ciphertext,
        "enabled": data.get("enabled", old.get("enabled", True)) is not False,
        # Any credential or mailbox change requires a successful connection test.
        "verification_status": "pending",
        "verified_profile_revision": None,
        "verified_at": None,
    }


def get_user_mail_account(user_id: str, profile_id: str) -> dict[str, Any] | None:
    return collection.find_one(
        {
            "user_id": str(user_id),
            "profile_id": str(profile_id),
            "delete_at": None,
        }
    )


def list_user_mail_accounts(user_id: str, team_id: str) -> list[dict[str, Any]]:
    return list(
        collection.find(
            {
                "user_id": str(user_id),
                "team_id": str(team_id),
                "delete_at": None,
            }
        )
    )


def save_user_mail_account(
    user_id: str, profile_id: str, values: dict[str, Any]
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    collection.update_one(
        {
            "user_id": str(user_id),
            "profile_id": str(profile_id),
            "delete_at": None,
        },
        {
            "$set": {**values, "updated_at": now},
            "$setOnInsert": {
                "_id": str(uuid.uuid4()),
                "user_id": str(user_id),
                "created_at": now,
                "delete_at": None,
            },
        },
        upsert=True,
    )
    return get_user_mail_account(user_id, profile_id) or {}


def verify_user_mail_account(
    user_id: str, profile_id: str, *, connection_revision: int
) -> bool:
    return collection.update_one(
        {
            "user_id": str(user_id),
            "profile_id": str(profile_id),
            "delete_at": None,
        },
        {
            "$set": {
                "verification_status": "verified",
                "verified_profile_revision": max(1, int(connection_revision)),
                "verified_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    ).matched_count > 0


def invalidate_user_mail_accounts(profile_id: str) -> int:
    return collection.update_many(
        {"profile_id": str(profile_id), "delete_at": None},
        {
            "$set": {
                "verification_status": "pending",
                "verified_profile_revision": None,
                "verified_at": None,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    ).modified_count


def delete_user_mail_accounts_for_profile(profile_id: str) -> int:
    return collection.update_many(
        {"profile_id": str(profile_id), "delete_at": None},
        {
            "$set": {
                "enabled": False,
                "secrets_ciphertext": None,
                "delete_at": datetime.now(timezone.utc),
            }
        },
    ).modified_count


def delete_user_mail_account(user_id: str, profile_id: str) -> bool:
    return collection.update_one(
        {
            "user_id": str(user_id),
            "profile_id": str(profile_id),
            "delete_at": None,
        },
        {
            "$set": {
                "enabled": False,
                "secrets_ciphertext": None,
                "delete_at": datetime.now(timezone.utc),
            }
        },
    ).modified_count > 0


def decrypt_user_mail_secrets(document: dict[str, Any]) -> dict[str, str]:
    raw = decrypt_secret(document.get("secrets_ciphertext")) or "{}"
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Stored personal mail credentials are invalid")
    return {str(key): str(item) for key, item in value.items()}


def materialize_user_mail_connection(
    profile: dict[str, Any], account: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    from mongo_table_connecters.mail_connections import decrypt_mail_secrets

    if str(account.get("profile_id") or "") != str(profile.get("_id") or ""):
        raise ValueError("Personal mail account does not match the Team Mail Profile")
    connection = {
        **profile,
        "email_address": account.get("email_address"),
        "public_config": {
            **(profile.get("public_config") or {}),
            **(account.get("public_config") or {}),
        },
    }
    return connection, {
        **decrypt_mail_secrets(profile),
        **decrypt_user_mail_secrets(account),
    }


def serialize_user_mail_account(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "_id": str(document.get("_id") or ""),
        "profile_id": str(document.get("profile_id") or ""),
        "team_id": str(document.get("team_id") or ""),
        "email_address": str(document.get("email_address") or ""),
        "public_config": document.get("public_config") or {},
        "enabled": document.get("enabled", True),
        "verification_status": str(
            document.get("verification_status") or "pending"
        ),
        "verified_profile_revision": document.get("verified_profile_revision"),
        "verified_at": document.get("verified_at"),
        "has_credentials": bool(document.get("secrets_ciphertext")),
    }
