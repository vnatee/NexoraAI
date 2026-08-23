from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.provider_secrets import decrypt_secret, encrypt_secret
from mongo_table_connecters.mongo_connector import get_database


SETTINGS_ID = "authentication"
collection = get_database()["application_settings"]


def get_auth_settings(*, decrypt_client_secret: bool = False) -> dict[str, Any] | None:
    document = collection.find_one({"_id": SETTINGS_ID})
    if not document:
        return None
    result = dict(document)
    encrypted = result.pop("client_secret_ciphertext", None)
    result["has_client_secret"] = bool(encrypted)
    if decrypt_client_secret and encrypted:
        result["client_secret"] = decrypt_secret(encrypted)
    return result


def save_auth_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = collection.find_one({"_id": SETTINGS_ID}) or {}
    enabled = payload.get("entra_enabled") is True
    tenant_id = str(payload.get("tenant_id") or "").strip()
    server_app_id = str(payload.get("server_app_id") or "").strip()
    client_app_id = str(payload.get("client_app_id") or "").strip()
    client_secret = str(payload.get("client_secret") or "")
    if enabled and (not tenant_id or not server_app_id or not client_app_id):
        raise ValueError("Tenant ID, API application ID and SPA application ID are required")
    update: dict[str, Any] = {
        "entra_enabled": enabled,
        "tenant_id": tenant_id,
        "server_app_id": server_app_id,
        "client_app_id": client_app_id,
        "updated_at": datetime.now(timezone.utc),
    }
    if client_secret:
        update["client_secret_ciphertext"] = encrypt_secret(client_secret)
    elif payload.get("clear_client_secret") is True:
        update["client_secret_ciphertext"] = None
    elif current.get("client_secret_ciphertext"):
        update["client_secret_ciphertext"] = current["client_secret_ciphertext"]
    if enabled and not update.get("client_secret_ciphertext"):
        raise ValueError("API application client secret is required")
    collection.update_one(
        {"_id": SETTINGS_ID},
        {"$set": update, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return get_auth_settings() or {"_id": SETTINGS_ID, **update}


def serialize_auth_settings(document: dict[str, Any] | None) -> dict[str, Any]:
    document = document or {}
    return {
        "entra_enabled": document.get("entra_enabled") is True,
        "tenant_id": str(document.get("tenant_id") or ""),
        "server_app_id": str(document.get("server_app_id") or ""),
        "client_app_id": str(document.get("client_app_id") or ""),
        "has_client_secret": document.get("has_client_secret") is True,
    }


def delete_auth_settings() -> None:
    collection.delete_one({"_id": SETTINGS_ID})
