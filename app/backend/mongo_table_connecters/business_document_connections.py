import json
import uuid
from datetime import datetime, timezone
from typing import Any

from core.provider_secrets import decrypt_secret, encrypt_secret
from mongo_table_connecters.mongo_connector import get_database


collection = get_database()["business_document_connections"]

PROVIDERS = {"microsoft365", "google_workspace"}
OPERATION_MODES = {"read_only", "read_write"}


def normalize_business_document_connection(
    data: object, *, existing: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Business document connection payload must be an object")
    old = existing or {}
    provider = str(data.get("provider") or old.get("provider") or "").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError("Unsupported business document provider")
    name = str(data.get("name") or old.get("name") or "").strip()
    if not name:
        raise ValueError("Connection name is required")

    public_config = dict(old.get("public_config") or {})
    incoming_config = data.get("public_config") or {}
    if not isinstance(incoming_config, dict):
        raise ValueError("public_config must be an object")
    public_config.update({str(key): value for key, value in incoming_config.items() if value is not None})

    required_public = (
        ("tenant_id", "client_id", "drive_id")
        if provider == "microsoft365"
        else ("client_id",)
    )
    missing_public = [field for field in required_public if not str(public_config.get(field) or "").strip()]
    if missing_public:
        raise ValueError(f"Missing provider configuration: {', '.join(missing_public)}")
    for key in ("tenant_id", "client_id", "drive_id", "root_folder_id", "shared_drive_id"):
        if key in public_config:
            public_config[key] = str(public_config.get(key) or "").strip()[:500]

    operation_mode = str(data.get("operation_mode") or old.get("operation_mode") or "read_only").strip().lower()
    if operation_mode not in OPERATION_MODES:
        raise ValueError("operation_mode must be read_only or read_write")

    secrets_ciphertext = old.get("secrets_ciphertext")
    secrets = data.get("secrets")
    if data.get("clear_secrets") is True:
        secrets_ciphertext = None
    elif secrets is not None:
        if not isinstance(secrets, dict):
            raise ValueError("secrets must be an object")
        normalized_secrets = {str(key): str(value) for key, value in secrets.items() if value not in (None, "")}
        required_secrets = {"client_secret"} if provider == "microsoft365" else {"client_secret", "refresh_token"}
        if not secrets_ciphertext and not required_secrets.issubset(normalized_secrets):
            missing = ", ".join(sorted(required_secrets - set(normalized_secrets)))
            raise ValueError(f"Missing credentials: {missing}")
        if normalized_secrets:
            secrets_ciphertext = encrypt_secret(json.dumps(normalized_secrets, ensure_ascii=False))
    if not secrets_ciphertext and data.get("enabled", old.get("enabled", True)) is not False:
        raise ValueError("Credentials are required for an enabled document connection")

    return {
        "team_id": str(data.get("team_id") or old.get("team_id") or "").strip(),
        "name": name[:100],
        "provider": provider,
        "public_config": public_config,
        "secrets_ciphertext": secrets_ciphertext,
        "operation_mode": operation_mode,
        "enabled": data.get("enabled", old.get("enabled", True)) is not False,
    }


def insert_business_document_connection(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document = {"_id": str(uuid.uuid4()), **data, "created_at": now, "updated_at": now, "delete_at": None}
    collection.insert_one(document)
    return document


def update_business_document_connection(connection_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    collection.update_one(
        {"_id": connection_id, "delete_at": None},
        {"$set": {**data, "updated_at": datetime.now(timezone.utc)}},
    )
    return get_business_document_connection(connection_id)


def get_business_document_connection(connection_id: str) -> dict[str, Any] | None:
    return collection.find_one({"_id": connection_id, "delete_at": None})


def list_business_document_connections(team_id: str, *, enabled_only: bool = False) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"team_id": team_id, "delete_at": None}
    if enabled_only:
        query["enabled"] = True
    return list(collection.find(query).sort("name", 1))


def soft_delete_business_document_connection(connection_id: str) -> bool:
    return collection.update_one(
        {"_id": connection_id, "delete_at": None},
        {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc)}},
    ).modified_count > 0


def decrypt_business_document_secrets(document: dict[str, Any]) -> dict[str, str]:
    raw = decrypt_secret(document.get("secrets_ciphertext")) or "{}"
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Stored document credentials are invalid")
    return {str(key): str(item) for key, item in value.items()}


def serialize_business_document_connection(document: dict[str, Any], *, usage_count: int = 0) -> dict[str, Any]:
    return {
        "_id": str(document["_id"]),
        "team_id": str(document.get("team_id") or ""),
        "name": document.get("name"),
        "provider": document.get("provider"),
        "public_config": document.get("public_config") or {},
        "operation_mode": document.get("operation_mode", "read_only"),
        "enabled": document.get("enabled", True),
        "has_credentials": bool(document.get("secrets_ciphertext")),
        "agent_usage_count": usage_count,
    }
