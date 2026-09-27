"""Encrypted, Team-scoped Web Search provider connections."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from core.provider_secrets import decrypt_secret, encrypt_secret
from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["web_search_connections"]
PROVIDERS = {"brave", "searxng"}


def normalize_web_search_connection(data: object, *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Web Search connection payload must be an object")
    old = existing or {}
    provider = str(data.get("provider") or old.get("provider") or "").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError("Web Search provider must be brave or searxng")
    name = str(data.get("name") or old.get("name") or "").strip()
    if not name:
        raise ValueError("Connection name is required")
    base_url = str(data.get("base_url") or old.get("base_url") or "").strip().rstrip("/")
    if provider == "searxng":
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("A valid SearXNG HTTP(S) base URL is required")
    if provider == "brave":
        base_url = ""
    api_key_ciphertext = old.get("api_key_ciphertext")
    api_key = str(data.get("api_key") or "").strip()
    if data.get("clear_api_key") is True:
        api_key_ciphertext = None
    elif api_key:
        api_key_ciphertext = encrypt_secret(api_key)
    enabled = data.get("enabled", old.get("enabled", True)) is not False
    if provider == "brave" and enabled and not api_key_ciphertext:
        raise ValueError("Brave Search API key is required for an enabled connection")
    return {
        "team_id": str(data.get("team_id") or old.get("team_id") or "").strip(),
        "name": name[:100],
        "provider": provider,
        "base_url": base_url[:1000],
        "api_key_ciphertext": api_key_ciphertext,
        "timeout_seconds": max(1, min(int(data.get("timeout_seconds", old.get("timeout_seconds", 10)) or 10), 30)),
        "enabled": enabled,
    }


def insert_web_search_connection(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document = {"_id": str(uuid.uuid4()), **data, "created_at": now, "updated_at": now, "delete_at": None}
    collection.insert_one(document)
    return document


def update_web_search_connection(connection_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    collection.update_one(
        {"_id": connection_id, "delete_at": None},
        {"$set": {**data, "updated_at": datetime.now(timezone.utc)}},
    )
    return get_web_search_connection(connection_id)


def get_web_search_connection(connection_id: str) -> dict[str, Any] | None:
    return collection.find_one({"_id": connection_id, "delete_at": None})


def list_web_search_connections(team_id: str, *, enabled_only: bool = False) -> list[dict[str, Any]]:
    query: dict[str, Any] = {
        "team_id": team_id if team_id else {"$in": [None, ""]},
        "delete_at": None,
    }
    if enabled_only:
        query["enabled"] = True
    return list(collection.find(query).sort("name", 1))


def soft_delete_web_search_connection(connection_id: str) -> bool:
    return collection.update_one(
        {"_id": connection_id, "delete_at": None},
        {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc)}},
    ).modified_count > 0


def decrypt_web_search_api_key(document: dict[str, Any]) -> str:
    return decrypt_secret(document.get("api_key_ciphertext")) or ""


def web_search_connection_usage_count(connection_id: str) -> int:
    return int(get_database()["agents"].count_documents({
        "config.tool_settings.web_search_connection_id": connection_id,
        "delete_at": None,
    }))


def serialize_web_search_connection(document: dict[str, Any], *, usage_count: int = 0) -> dict[str, Any]:
    return {
        "_id": str(document["_id"]),
        "team_id": str(document.get("team_id") or ""),
        "name": str(document.get("name") or ""),
        "provider": str(document.get("provider") or ""),
        "base_url": str(document.get("base_url") or ""),
        "timeout_seconds": int(document.get("timeout_seconds") or 10),
        "enabled": document.get("enabled", True) is not False,
        "has_api_key": bool(document.get("api_key_ciphertext")),
        "agent_usage_count": usage_count,
    }
