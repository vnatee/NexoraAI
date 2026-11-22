"""Governed GPUStack control-plane configuration and rollout records."""

from __future__ import annotations

import ipaddress
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from core.provider_secrets import encrypt_secret
from mongo_table_connecters.mongo_connector import get_database

SETTINGS_ID = "system"
_MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")
_CONSOLE_AUTH_MODES = {"local", "oidc", "saml"}


def _settings_collection():
    return get_database()["private_llm_control_plane_settings"]


def _rollouts_collection():
    return get_database()["private_llm_rollouts"]


def default_private_llm_settings() -> dict[str, Any]:
    return {
        "_id": SETTINGS_ID,
        "base_url": os.getenv("GPUSTACK_CONTROL_PLANE_URL", "").strip().rstrip("/"),
        "console_url": os.getenv("GPUSTACK_CONSOLE_URL", "").strip().rstrip("/"),
        "console_auth_mode": "local",
        "api_key_ciphertext": None,
        "timeout_seconds": 30,
        "updated_at": None,
        "updated_by": "",
    }


def get_private_llm_settings() -> dict[str, Any]:
    return _settings_collection().find_one({"_id": SETTINGS_ID}) or default_private_llm_settings()


def _internal_http_host(hostname: str) -> bool:
    value = hostname.lower().rstrip(".")
    if value in {"localhost", "gpustack"}:
        return True
    try:
        address = ipaddress.ip_address(value)
        if address.is_loopback:
            return True
        private_networks = (
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"),
            ipaddress.ip_network("fc00::/7"),
        )
        return any(address in network for network in private_networks)
    except ValueError:
        return value.endswith((".local", ".internal"))


def normalize_private_llm_settings(
    data: object,
    *,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Private LLM settings payload must be an object")
    old = existing or default_private_llm_settings()
    base_url = str(data.get("base_url", old.get("base_url") or "")).strip().rstrip("/")
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or (parsed.scheme == "http" and not _internal_http_host(parsed.hostname))
    ):
        raise ValueError(
            "GPUStack URL must be credential-free HTTPS, or HTTP on an internal host"
        )

    console_url = str(
        data.get("console_url", old.get("console_url") or "")
    ).strip().rstrip("/")
    if console_url:
        parsed_console = urlsplit(console_url)
        if (
            parsed_console.scheme not in {"https", "http"}
            or not parsed_console.hostname
            or parsed_console.username
            or parsed_console.password
            or parsed_console.query
            or parsed_console.fragment
            or (parsed_console.scheme == "http" and not _internal_http_host(parsed_console.hostname))
        ):
            raise ValueError(
                "GPUStack Console URL must be credential-free HTTPS, or HTTP on an internal host"
            )

    console_auth_mode = str(
        data.get("console_auth_mode", old.get("console_auth_mode") or "local")
    ).strip().lower()
    if console_auth_mode not in _CONSOLE_AUTH_MODES:
        raise ValueError("GPUStack Console sign-in must be local, oidc, or saml")

    api_key_ciphertext = old.get("api_key_ciphertext")
    if data.get("clear_api_key") is True:
        api_key_ciphertext = None
    api_key = str(data.get("api_key") or "").strip()
    if api_key:
        if len(api_key) > 16_384:
            raise ValueError("GPUStack API key exceeds the allowed size")
        api_key_ciphertext = encrypt_secret(api_key)

    try:
        timeout_seconds = int(data.get("timeout_seconds", old.get("timeout_seconds", 30)) or 30)
    except (TypeError, ValueError) as error:
        raise ValueError("GPUStack timeout must be an integer") from error

    return {
        "base_url": base_url,
        "console_url": console_url,
        "console_auth_mode": console_auth_mode,
        "api_key_ciphertext": api_key_ciphertext,
        "timeout_seconds": max(5, min(timeout_seconds, 120)),
    }


def save_private_llm_settings(data: dict[str, Any], *, actor_id: str) -> dict[str, Any]:
    document = {
        "_id": SETTINGS_ID,
        **data,
        "updated_at": datetime.now(timezone.utc),
        "updated_by": str(actor_id or "")[:100],
    }
    _settings_collection().replace_one({"_id": SETTINGS_ID}, document, upsert=True)
    return document


def serialize_private_llm_settings(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "base_url": str(document.get("base_url") or ""),
        "console_url": str(document.get("console_url") or ""),
        "console_auth_mode": str(document.get("console_auth_mode") or "local"),
        "timeout_seconds": int(document.get("timeout_seconds") or 30),
        "has_api_key": bool(document.get("api_key_ciphertext")),
        "updated_at": document.get("updated_at"),
    }


def normalize_rollout_request(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Rollout payload must be an object")
    proxy_id = str(data.get("proxy_id") or "").strip()
    candidate_model = str(data.get("candidate_model") or "").strip()
    if not proxy_id or len(proxy_id) > 128:
        raise ValueError("Select an Enterprise Gateway proxy")
    if not _MODEL_NAME.fullmatch(candidate_model):
        raise ValueError("Candidate model contains unsupported characters")
    try:
        min_ready_replicas = int(data.get("min_ready_replicas") or 1)
        min_ready_workers = int(data.get("min_ready_workers") or 1)
    except (TypeError, ValueError) as error:
        raise ValueError("Ready replica and worker requirements must be integers") from error
    if not 1 <= min_ready_replicas <= 100 or not 1 <= min_ready_workers <= 100:
        raise ValueError("Ready replica and worker requirements must be between 1 and 100")
    return {
        "proxy_id": proxy_id,
        "candidate_model": candidate_model,
        "min_ready_replicas": min_ready_replicas,
        "min_ready_workers": min_ready_workers,
    }


def create_rollout_plan(
    data: dict[str, Any],
    *,
    previous_model: str,
    actor_id: str,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document = {
        "_id": str(uuid.uuid4()),
        **data,
        "previous_model": str(previous_model)[:255],
        "status": "pending_approval",
        "preflight": preflight,
        "created_at": now,
        "created_by": str(actor_id or "")[:100],
        "updated_at": now,
        "updated_by": str(actor_id or "")[:100],
    }
    _rollouts_collection().insert_one(document)
    return document


def get_rollout_plan(plan_id: str) -> dict[str, Any] | None:
    return _rollouts_collection().find_one({"_id": str(plan_id)})


def list_rollout_plans(limit: int = 25) -> list[dict[str, Any]]:
    cursor = _rollouts_collection().find({}).sort("created_at", -1).limit(max(1, min(limit, 100)))
    return list(cursor)


def update_rollout_plan(plan_id: str, *, actor_id: str, **updates: Any) -> dict[str, Any]:
    safe_updates = {
        key: value
        for key, value in updates.items()
        if key in {"status", "activated_at", "rolled_back_at", "last_error_type", "conformance"}
    }
    safe_updates.update(
        {
            "updated_at": datetime.now(timezone.utc),
            "updated_by": str(actor_id or "")[:100],
        }
    )
    _rollouts_collection().update_one({"_id": str(plan_id)}, {"$set": safe_updates})
    updated = get_rollout_plan(plan_id)
    if updated is None:
        raise ValueError("Rollout plan was not found")
    return updated


def serialize_rollout_plan(document: dict[str, Any]) -> dict[str, Any]:
    return {
        key: document.get(key)
        for key in (
            "_id",
            "proxy_id",
            "candidate_model",
            "previous_model",
            "min_ready_replicas",
            "min_ready_workers",
            "status",
            "preflight",
            "conformance",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "activated_at",
            "rolled_back_at",
            "last_error_type",
        )
        if key in document
    }
