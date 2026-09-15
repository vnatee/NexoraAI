import json
import uuid
from datetime import datetime, timezone
from typing import Any

from core.provider_secrets import decrypt_secret, encrypt_secret
from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["messaging_connections"]
PROVIDERS = {"line", "slack", "discord"}
REQUIRED_SECRETS = {"line": {"channel_access_token"}, "slack": {"bot_token"}, "discord": {"webhook_url"}}


def normalize_messaging_connection(data: object, *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Messaging connection payload must be an object")
    old = existing or {}
    provider = str(data.get("provider") or old.get("provider") or "").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError("Unsupported messaging provider")
    name = str(data.get("name") or old.get("name") or "").strip()
    if not name:
        raise ValueError("Connection name is required")
    public_config = dict(old.get("public_config") or {})
    incoming = data.get("public_config") or {}
    if not isinstance(incoming, dict):
        raise ValueError("public_config must be an object")
    public_config.update({str(k): v for k, v in incoming.items() if v is not None})
    secrets_ciphertext = old.get("secrets_ciphertext")
    secrets = data.get("secrets")
    if secrets is not None:
        if not isinstance(secrets, dict):
            raise ValueError("secrets must be an object")
        normalized = {str(k): str(v).strip() for k, v in secrets.items() if str(v or "").strip()}
        if not secrets_ciphertext and not REQUIRED_SECRETS[provider].issubset(normalized):
            raise ValueError(f"Missing credential: {', '.join(sorted(REQUIRED_SECRETS[provider] - set(normalized)))}")
        if normalized:
            secrets_ciphertext = encrypt_secret(json.dumps(normalized))
    if not secrets_ciphertext:
        raise ValueError("Provider credentials are required")
    return {
        "team_id": str(data.get("team_id") or old.get("team_id") or ""),
        "name": name[:100], "provider": provider, "public_config": public_config,
        "secrets_ciphertext": secrets_ciphertext,
        "enabled": data.get("enabled", old.get("enabled", True)) is not False,
    }


def insert_messaging_connection(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document = {"_id": str(uuid.uuid4()), **data, "created_at": now, "updated_at": now, "delete_at": None}
    collection.insert_one(document)
    return document


def get_messaging_connection(connection_id: str) -> dict[str, Any] | None:
    return collection.find_one({"_id": connection_id, "delete_at": None})


def list_messaging_connections(team_id: str) -> list[dict[str, Any]]:
    return list(collection.find({"team_id": team_id, "delete_at": None}).sort("name", 1))


def update_messaging_connection(connection_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    collection.update_one({"_id": connection_id, "delete_at": None}, {"$set": {**data, "updated_at": datetime.now(timezone.utc)}})
    return get_messaging_connection(connection_id)


def delete_messaging_connection(connection_id: str) -> bool:
    return collection.update_one({"_id": connection_id, "delete_at": None}, {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc)}}).matched_count > 0


def decrypt_messaging_secrets(document: dict[str, Any]) -> dict[str, str]:
    value = json.loads(decrypt_secret(document.get("secrets_ciphertext")) or "{}")
    return {str(k): str(v) for k, v in value.items()}


def serialize_messaging_connection(document: dict[str, Any], usage_count: int = 0) -> dict[str, Any]:
    return {"_id": str(document["_id"]), "team_id": document.get("team_id"), "name": document.get("name"),
            "provider": document.get("provider"), "public_config": document.get("public_config") or {},
            "enabled": document.get("enabled", True), "has_credentials": bool(document.get("secrets_ciphertext")),
            "agent_usage_count": usage_count}
