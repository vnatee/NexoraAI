from __future__ import annotations

from datetime import datetime, timezone
import re
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
    oidc_encrypted = result.pop("oidc_client_secret_ciphertext", None)
    result["oidc_has_client_secret"] = bool(oidc_encrypted)
    if decrypt_client_secret and oidc_encrypted:
        result["oidc_client_secret"] = decrypt_secret(oidc_encrypted)
    return result


def save_auth_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = collection.find_one({"_id": SETTINGS_ID}) or {}
    enabled = payload.get("entra_enabled") is True
    tenant_id = str(payload.get("tenant_id") or "").strip()
    server_app_id = str(payload.get("server_app_id") or "").strip()
    client_app_id = str(payload.get("client_app_id") or "").strip()
    client_secret = str(payload.get("client_secret") or "")
    oidc_enabled = payload.get("oidc_enabled") is True
    oidc_display_name = str(payload.get("oidc_display_name") or "Enterprise SSO").strip()
    oidc_issuer = str(payload.get("oidc_issuer") or "").strip().rstrip("/")
    oidc_client_id = str(payload.get("oidc_client_id") or "").strip()
    oidc_client_secret = str(payload.get("oidc_client_secret") or "")
    oidc_token_auth_method = str(payload.get("oidc_token_auth_method") or "client_secret_basic").strip()
    oidc_jit_enabled = payload.get("oidc_jit_enabled") is True
    raw_domains = payload.get("oidc_allowed_domains") or []
    if isinstance(raw_domains, str):
        raw_domains = raw_domains.split(",")
    oidc_allowed_domains = sorted(
        {str(domain).strip().lower().lstrip("@") for domain in raw_domains if str(domain).strip()}
    )
    if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", domain) for domain in oidc_allowed_domains):
        raise ValueError("OIDC allowed email domains contain an invalid domain")
    if enabled and (not tenant_id or not server_app_id or not client_app_id):
        raise ValueError("Tenant ID, API application ID and SPA application ID are required")
    update: dict[str, Any] = {
        "entra_enabled": enabled,
        "tenant_id": tenant_id,
        "server_app_id": server_app_id,
        "client_app_id": client_app_id,
        "oidc_enabled": oidc_enabled,
        "oidc_display_name": oidc_display_name or "Enterprise SSO",
        "oidc_issuer": oidc_issuer,
        "oidc_client_id": oidc_client_id,
        "oidc_token_auth_method": oidc_token_auth_method,
        "oidc_jit_enabled": oidc_jit_enabled,
        "oidc_allowed_domains": oidc_allowed_domains,
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
    if oidc_client_secret:
        update["oidc_client_secret_ciphertext"] = encrypt_secret(oidc_client_secret)
    elif payload.get("oidc_clear_client_secret") is True:
        update["oidc_client_secret_ciphertext"] = None
    elif current.get("oidc_client_secret_ciphertext"):
        update["oidc_client_secret_ciphertext"] = current["oidc_client_secret_ciphertext"]
    if oidc_enabled:
        if not oidc_issuer or not oidc_client_id:
            raise ValueError("OIDC issuer URL and client ID are required")
        if not update.get("oidc_client_secret_ciphertext"):
            raise ValueError("OIDC client secret is required")
        if not oidc_issuer.startswith("https://"):
            raise ValueError("OIDC issuer URL must use HTTPS")
        if oidc_token_auth_method not in {"client_secret_basic", "client_secret_post"}:
            raise ValueError("OIDC token authentication method is invalid")
        if oidc_jit_enabled and not oidc_allowed_domains:
            raise ValueError("At least one allowed email domain is required when OIDC JIT provisioning is enabled")
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
        "oidc_enabled": document.get("oidc_enabled") is True,
        "oidc_display_name": str(document.get("oidc_display_name") or "Enterprise SSO"),
        "oidc_issuer": str(document.get("oidc_issuer") or ""),
        "oidc_client_id": str(document.get("oidc_client_id") or ""),
        "oidc_token_auth_method": str(document.get("oidc_token_auth_method") or "client_secret_basic"),
        "oidc_has_client_secret": document.get("oidc_has_client_secret") is True,
        "oidc_jit_enabled": document.get("oidc_jit_enabled") is True,
        "oidc_allowed_domains": [str(item) for item in (document.get("oidc_allowed_domains") or [])],
    }


def delete_auth_settings() -> None:
    collection.delete_one({"_id": SETTINGS_ID})
