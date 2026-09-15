from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from core.provider_secrets import decrypt_secret, encrypt_secret
from mongo_table_connecters.auth_settings import get_auth_settings
from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["oidc_providers"]


def ensure_oidc_provider_indexes() -> None:
    collection.create_index("issuer", name="oidc_provider_issuer")
    collection.create_index("enabled", name="oidc_provider_enabled")


def _domains(value: Any) -> list[str]:
    values = value.split(",") if isinstance(value, str) else (value or [])
    domains = sorted({str(item).strip().lower().lstrip("@") for item in values if str(item).strip()})
    if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", item) for item in domains):
        raise ValueError("OIDC allowed email domains contain an invalid domain")
    return domains


def _legacy_provider(*, decrypt_client_secret: bool) -> dict[str, Any] | None:
    settings = get_auth_settings(decrypt_client_secret=decrypt_client_secret) or {}
    if not settings.get("oidc_issuer"):
        return None
    provider = {
        "_id": "legacy",
        "enabled": settings.get("oidc_enabled") is True,
        "display_name": str(settings.get("oidc_display_name") or "Enterprise SSO"),
        "issuer": str(settings.get("oidc_issuer") or "").rstrip("/"),
        "client_id": str(settings.get("oidc_client_id") or ""),
        "token_auth_method": str(settings.get("oidc_token_auth_method") or "client_secret_basic"),
        "jit_enabled": settings.get("oidc_jit_enabled") is True,
        "allowed_domains": [str(item) for item in (settings.get("oidc_allowed_domains") or [])],
        "has_client_secret": settings.get("oidc_has_client_secret") is True,
        "legacy": True,
    }
    if decrypt_client_secret:
        provider["client_secret"] = str(settings.get("oidc_client_secret") or "")
    return provider


def list_oidc_providers(*, decrypt_client_secret: bool = False) -> list[dict[str, Any]]:
    providers = []
    for document in collection.find({"delete_at": None}).sort("display_name", 1):
        provider = dict(document)
        ciphertext = provider.pop("client_secret_ciphertext", None)
        provider["has_client_secret"] = bool(ciphertext)
        if decrypt_client_secret and ciphertext:
            provider["client_secret"] = decrypt_secret(ciphertext)
        providers.append(provider)
    legacy = _legacy_provider(decrypt_client_secret=decrypt_client_secret)
    if legacy:
        providers.append(legacy)
    return providers


def get_oidc_provider(provider_id: str, *, decrypt_client_secret: bool = False) -> dict[str, Any] | None:
    if provider_id == "legacy":
        return _legacy_provider(decrypt_client_secret=decrypt_client_secret)
    document = collection.find_one({"_id": str(provider_id), "delete_at": None})
    if not document:
        return None
    provider = dict(document)
    ciphertext = provider.pop("client_secret_ciphertext", None)
    provider["has_client_secret"] = bool(ciphertext)
    if decrypt_client_secret and ciphertext:
        provider["client_secret"] = decrypt_secret(ciphertext)
    return provider


def serialize_oidc_provider(provider: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(provider.get("_id") or ""),
        "enabled": provider.get("enabled") is True,
        "display_name": str(provider.get("display_name") or "Enterprise SSO"),
        "issuer": str(provider.get("issuer") or ""),
        "client_id": str(provider.get("client_id") or ""),
        "token_auth_method": str(provider.get("token_auth_method") or "client_secret_basic"),
        "jit_enabled": provider.get("jit_enabled") is True,
        "allowed_domains": [str(item) for item in (provider.get("allowed_domains") or [])],
        "has_client_secret": provider.get("has_client_secret") is True,
        "legacy": provider.get("legacy") is True,
    }


def public_oidc_providers() -> list[dict[str, str]]:
    return [
        {"id": str(item.get("_id") or ""), "display_name": str(item.get("display_name") or "Enterprise SSO")}
        for item in list_oidc_providers()
        if item.get("enabled") is True
    ]


def save_oidc_provider(payload: dict[str, Any], provider_id: str | None = None) -> dict[str, Any]:
    provider_id = str(provider_id or uuid.uuid4())
    if provider_id == "legacy":
        raise ValueError("Save the legacy provider as a new connection before editing it")
    current = collection.find_one({"_id": provider_id, "delete_at": None}) or {}
    enabled = payload.get("enabled") is True
    display_name = str(payload.get("display_name") or "").strip()
    issuer = str(payload.get("issuer") or "").strip().rstrip("/")
    client_id = str(payload.get("client_id") or "").strip()
    token_auth_method = str(payload.get("token_auth_method") or "client_secret_basic").strip()
    jit_enabled = payload.get("jit_enabled") is True
    allowed_domains = _domains(payload.get("allowed_domains"))
    client_secret = str(payload.get("client_secret") or "")
    if not display_name or len(display_name) > 80:
        raise ValueError("OIDC provider name is required and must not exceed 80 characters")
    if not issuer.startswith("https://") or not client_id:
        raise ValueError("OIDC issuer URL must use HTTPS and client ID is required")
    if token_auth_method not in {"client_secret_basic", "client_secret_post"}:
        raise ValueError("OIDC token authentication method is invalid")
    if jit_enabled and not allowed_domains:
        raise ValueError("At least one allowed email domain is required when OIDC JIT provisioning is enabled")
    overlapping = collection.find_one(
        {
            "_id": {"$ne": provider_id},
            "delete_at": None,
            "enabled": True,
            "allowed_domains": {"$in": allowed_domains},
        },
        {"_id": 1},
    ) if enabled and allowed_domains else None
    if overlapping:
        raise ValueError("An enabled OIDC provider already uses one of these email domains")
    legacy = _legacy_provider(decrypt_client_secret=False)
    if (
        enabled
        and allowed_domains
        and legacy
        and legacy.get("enabled") is True
        and set(allowed_domains).intersection(legacy.get("allowed_domains") or [])
    ):
        raise ValueError("The enabled legacy OIDC provider already uses one of these email domains")
    update = {
        "enabled": enabled,
        "display_name": display_name,
        "issuer": issuer,
        "client_id": client_id,
        "token_auth_method": token_auth_method,
        "jit_enabled": jit_enabled,
        "allowed_domains": allowed_domains,
        "updated_at": datetime.now(timezone.utc),
        "delete_at": None,
    }
    if client_secret:
        update["client_secret_ciphertext"] = encrypt_secret(client_secret)
    elif payload.get("clear_client_secret") is True:
        update["client_secret_ciphertext"] = None
    elif current.get("client_secret_ciphertext"):
        update["client_secret_ciphertext"] = current["client_secret_ciphertext"]
    if enabled and not update.get("client_secret_ciphertext"):
        raise ValueError("OIDC client secret is required")
    collection.update_one(
        {"_id": provider_id},
        {"$set": update, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return get_oidc_provider(provider_id) or {"_id": provider_id, **update}


def delete_oidc_provider(provider_id: str) -> bool:
    if provider_id == "legacy":
        raise ValueError("Disable the legacy provider in authentication settings")
    result = collection.update_one(
        {"_id": str(provider_id), "delete_at": None},
        {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


def enabled_oidc_provider_count() -> int:
    return sum(1 for item in list_oidc_providers() if item.get("enabled") is True)
