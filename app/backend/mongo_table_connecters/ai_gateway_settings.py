"""System-level AI Gateway routing configuration with encrypted credentials."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from core.provider_secrets import encrypt_secret
from mongo_table_connecters.mongo_connector import get_database

SETTINGS_ID = "system"
MODES = {"built_in", "external", "direct_development"}
GATEWAY_ADAPTERS = {"generic_openai", "mulesoft"}
AUTH_TYPES = {
    "none",
    "api_key",
    "oauth2_client_credentials",
    "mulesoft_client_id_enforcement",
}
OAUTH_CLIENT_AUTH_METHODS = {"client_secret_post", "client_secret_basic"}
ROUTING_STRATEGIES = {"model_based", "semantic"}
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _collection():
    return get_database()["ai_gateway_settings"]


def default_ai_gateway_settings() -> dict[str, Any]:
    return {
        "_id": SETTINGS_ID,
        "mode": "built_in",
        "name": "",
        "gateway_adapter": "generic_openai",
        "base_url": "",
        "auth_type": "none",
        "api_key_ciphertext": None,
        "token_url": "",
        "client_id": "",
        "client_secret_ciphertext": None,
        "oauth_scope": "",
        "oauth_audience": "",
        "oauth_client_auth_method": "client_secret_post",
        "mtls_enabled": False,
        "ca_certificate_ciphertext": None,
        "client_certificate_ciphertext": None,
        "client_private_key_ciphertext": None,
        "models": [],
        "default_model_id": "",
        "timeout_seconds": 60,
        "updated_at": None,
        "updated_by": "",
    }


def get_ai_gateway_settings() -> dict[str, Any]:
    return _collection().find_one({"_id": SETTINGS_ID}) or default_ai_gateway_settings()


def _secret_update(
    data: dict[str, Any],
    old: dict[str, Any],
    *,
    field: str,
    clear_field: str,
    ciphertext_field: str,
    max_length: int,
) -> str | None:
    current = old.get(ciphertext_field)
    if data.get(clear_field) is True:
        return None
    value = str(data.get(field) or "").strip()
    if not value:
        return current
    if len(value) > max_length:
        raise ValueError(f"{field} exceeds the allowed size")
    return encrypt_secret(value)


def _validated_url(value: object, field: str, *, allow_http: bool) -> str:
    normalized = str(value or "").strip().rstrip("/")
    parsed = urlsplit(normalized)
    allowed_schemes = {"https", "http"} if allow_http else {"https"}
    if (
        parsed.scheme not in allowed_schemes
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        requirement = "HTTP(S)" if allow_http else "HTTPS"
        raise ValueError(f"{field} must be a valid credential-free {requirement} URL")
    return normalized


def _normalize_models(
    value: object,
    *,
    gateway_adapter: str,
    allow_insecure_http: bool,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("External AI Gateway requires at least one route")
    if len(value) > 50:
        raise ValueError("External AI Gateway supports at most 50 routes")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Each gateway route must be an object")
        model_id = str(item.get("id") or "").strip()
        model_alias = str(item.get("model") or "").strip()
        routing_strategy = str(
            item.get("routing_strategy") or "model_based"
        ).strip().lower()
        if not _MODEL_ID.fullmatch(model_id):
            raise ValueError(
                "Gateway model id must use letters, numbers, dots, underscores, or hyphens"
            )
        if model_id in seen:
            raise ValueError(f"Duplicate gateway model id '{model_id}'")
        if routing_strategy not in ROUTING_STRATEGIES:
            raise ValueError(
                "Gateway route strategy must be model_based or semantic"
            )
        if routing_strategy == "semantic" and gateway_adapter != "mulesoft":
            raise ValueError("Semantic routing requires the MuleSoft gateway template")
        if not model_alias:
            model_alias = f"semantic/{model_id}" if routing_strategy == "semantic" else ""
        if not model_alias or len(model_alias) > 255:
            raise ValueError("Each gateway route requires a model or virtual route alias")
        route_base_url = str(item.get("base_url") or "").strip().rstrip("/")
        if route_base_url:
            route_base_url = _validated_url(
                route_base_url,
                "Gateway route base URL",
                allow_http=allow_insecure_http,
            )
        seen.add(model_id)
        result.append(
            {
                "id": model_id,
                "label": str(item.get("label") or model_alias).strip()[:100],
                "model": model_alias,
                "routing_strategy": routing_strategy,
                "base_url": route_base_url,
                "supports_tools": item.get("supports_tools", True) is not False,
                "supports_vision": item.get("supports_vision", False) is True,
            }
        )
    return result


def normalize_ai_gateway_settings(
    data: object,
    *,
    existing: dict[str, Any] | None = None,
    allow_insecure_http: bool = False,
    allow_direct_development: bool = False,
) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("AI Gateway settings payload must be an object")
    old = existing or default_ai_gateway_settings()
    mode = str(data.get("mode") or old.get("mode") or "built_in").strip().lower()
    if mode not in MODES:
        raise ValueError(
            "AI Gateway mode must be built_in, external, or direct_development"
        )
    if mode == "direct_development" and not allow_direct_development:
        raise ValueError("Direct provider mode is disabled for this deployment")

    name = str(data.get("name", old.get("name") or "")).strip()[:100]
    adapter_default = (
        "mulesoft"
        if str(old.get("auth_type") or "") == "mulesoft_client_id_enforcement"
        else "generic_openai"
    )
    gateway_adapter = str(
        data.get("gateway_adapter")
        or old.get("gateway_adapter")
        or adapter_default
    ).strip().lower()
    if gateway_adapter not in GATEWAY_ADAPTERS:
        raise ValueError("Gateway adapter must be generic_openai or mulesoft")
    base_url_source = data.get("base_url", old.get("base_url") or "")
    base_url = str(base_url_source or "").strip().rstrip("/")
    auth_type = (
        str(data.get("auth_type") or old.get("auth_type") or "none").strip().lower()
    )
    if auth_type not in AUTH_TYPES:
        raise ValueError(
            "Gateway authentication must be none, api_key, "
            "oauth2_client_credentials, or mulesoft_client_id_enforcement"
        )

    api_key_ciphertext = _secret_update(
        data,
        old,
        field="api_key",
        clear_field="clear_api_key",
        ciphertext_field="api_key_ciphertext",
        max_length=16_384,
    )
    client_secret_ciphertext = _secret_update(
        data,
        old,
        field="client_secret",
        clear_field="clear_client_secret",
        ciphertext_field="client_secret_ciphertext",
        max_length=16_384,
    )
    ca_certificate_ciphertext = _secret_update(
        data,
        old,
        field="ca_certificate",
        clear_field="clear_ca_certificate",
        ciphertext_field="ca_certificate_ciphertext",
        max_length=131_072,
    )
    client_certificate_ciphertext = _secret_update(
        data,
        old,
        field="client_certificate",
        clear_field="clear_client_certificate",
        ciphertext_field="client_certificate_ciphertext",
        max_length=131_072,
    )
    client_private_key_ciphertext = _secret_update(
        data,
        old,
        field="client_private_key",
        clear_field="clear_client_private_key",
        ciphertext_field="client_private_key_ciphertext",
        max_length=131_072,
    )

    token_url_source = data.get("token_url", old.get("token_url") or "")
    token_url = str(token_url_source or "").strip().rstrip("/")
    client_id = str(data.get("client_id", old.get("client_id") or "")).strip()[:500]
    oauth_scope = str(data.get("oauth_scope", old.get("oauth_scope") or "")).strip()[
        :2_000
    ]
    oauth_audience = str(
        data.get("oauth_audience", old.get("oauth_audience") or "")
    ).strip()[:2_000]
    oauth_client_auth_method = str(
        data.get(
            "oauth_client_auth_method",
            old.get("oauth_client_auth_method") or "client_secret_post",
        )
    ).strip()
    if oauth_client_auth_method not in OAUTH_CLIENT_AUTH_METHODS:
        raise ValueError(
            "OAuth client authentication must be client_secret_post or client_secret_basic"
        )
    mtls_enabled = data.get("mtls_enabled", old.get("mtls_enabled", False)) is True
    if mode == "external":
        if not name:
            raise ValueError("External AI Gateway name is required")
        base_url = _validated_url(
            base_url, "Gateway base URL", allow_http=allow_insecure_http
        )
    models_source = data.get("models", old.get("models") or [])
    models = (
        _normalize_models(
            models_source,
            gateway_adapter=gateway_adapter,
            allow_insecure_http=allow_insecure_http,
        )
        if mode == "external"
        else list(models_source or [])
    )
    default_model_id = str(
        data.get("default_model_id", old.get("default_model_id") or "")
    ).strip()

    try:
        timeout_seconds = int(
            data.get("timeout_seconds", old.get("timeout_seconds", 60)) or 60
        )
    except (TypeError, ValueError) as error:
        raise ValueError("Gateway timeout must be an integer") from error
    timeout_seconds = max(5, min(timeout_seconds, 300))

    if mode == "external":
        if default_model_id not in {item["id"] for item in models}:
            raise ValueError(
                "Select a default route from the configured gateway routes"
            )
        if auth_type == "api_key" and not api_key_ciphertext:
            raise ValueError("External AI Gateway API key is required")
        if auth_type == "oauth2_client_credentials":
            token_url = _validated_url(
                token_url, "OAuth token URL", allow_http=allow_insecure_http
            )
            if not client_id or not client_secret_ciphertext:
                raise ValueError("OAuth client id and client secret are required")
        if auth_type == "mulesoft_client_id_enforcement" and (
            not client_id or not client_secret_ciphertext
        ):
            raise ValueError(
                "MuleSoft client id and client secret are required"
            )
        if mtls_enabled and not (
            client_certificate_ciphertext and client_private_key_ciphertext
        ):
            raise ValueError("mTLS requires a client certificate and private key")

    return {
        "mode": mode,
        "name": name,
        "gateway_adapter": gateway_adapter,
        "base_url": base_url,
        "auth_type": auth_type,
        "api_key_ciphertext": api_key_ciphertext,
        "token_url": token_url,
        "client_id": client_id,
        "client_secret_ciphertext": client_secret_ciphertext,
        "oauth_scope": oauth_scope,
        "oauth_audience": oauth_audience,
        "oauth_client_auth_method": oauth_client_auth_method,
        "mtls_enabled": mtls_enabled,
        "ca_certificate_ciphertext": ca_certificate_ciphertext,
        "client_certificate_ciphertext": client_certificate_ciphertext,
        "client_private_key_ciphertext": client_private_key_ciphertext,
        "models": models,
        "default_model_id": default_model_id,
        "timeout_seconds": timeout_seconds,
    }


def save_ai_gateway_settings(data: dict[str, Any], *, actor_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document = {
        "_id": SETTINGS_ID,
        **data,
        "updated_at": now,
        "updated_by": str(actor_id or "")[:100],
    }
    _collection().replace_one({"_id": SETTINGS_ID}, document, upsert=True)
    return document


def serialize_ai_gateway_settings(document: dict[str, Any]) -> dict[str, Any]:
    mode = str(document.get("mode") or "built_in")
    models = [
        {
            **item,
            "routing_strategy": str(item.get("routing_strategy") or "model_based"),
            "base_url": str(item.get("base_url") or ""),
        }
        for item in document.get("models") or []
    ]
    return {
        "mode": mode,
        "name": str(document.get("name") or ""),
        "gateway_adapter": str(
            document.get("gateway_adapter")
            or (
                "mulesoft"
                if document.get("auth_type") == "mulesoft_client_id_enforcement"
                else "generic_openai"
            )
        ),
        "base_url": str(document.get("base_url") or ""),
        "auth_type": str(document.get("auth_type") or "none"),
        "token_url": str(document.get("token_url") or ""),
        "client_id": str(document.get("client_id") or ""),
        "oauth_scope": str(document.get("oauth_scope") or ""),
        "oauth_audience": str(document.get("oauth_audience") or ""),
        "oauth_client_auth_method": str(
            document.get("oauth_client_auth_method") or "client_secret_post"
        ),
        "mtls_enabled": document.get("mtls_enabled") is True,
        "models": models,
        "default_model_id": str(document.get("default_model_id") or ""),
        "timeout_seconds": int(document.get("timeout_seconds") or 60),
        "has_api_key": bool(document.get("api_key_ciphertext")),
        "has_client_secret": bool(document.get("client_secret_ciphertext")),
        "has_ca_certificate": bool(document.get("ca_certificate_ciphertext")),
        "has_client_certificate": bool(document.get("client_certificate_ciphertext")),
        "has_client_private_key": bool(document.get("client_private_key_ciphertext")),
        "direct_provider_access_blocked": mode == "external",
        "direct_development_allowed": os.getenv(
            "ALLOW_DIRECT_AI_PROVIDER_MODE", ""
        ).lower()
        == "true",
        "insecure_http_allowed": os.getenv("AI_GATEWAY_ALLOW_INSECURE_HTTP", "").lower()
        == "true",
        "updated_at": document.get("updated_at").isoformat()
        if document.get("updated_at")
        else None,
    }
