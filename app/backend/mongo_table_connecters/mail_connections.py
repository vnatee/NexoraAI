import json
import uuid
from datetime import datetime, timezone
from typing import Any

from core.provider_secrets import decrypt_secret, encrypt_secret
from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["mail_connections"]

PROVIDERS = {"microsoft365", "gmail", "generic"}
RECEIVE_PROTOCOLS = {"imap", "pop3"}
SECURITY_MODES = {"ssl", "starttls", "none"}


def normalize_mail_connection(data: object, *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Mail connection payload must be an object")
    old = existing or {}
    provider = str(data.get("provider") or old.get("provider") or "generic").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError("Unsupported mail provider")
    name = str(data.get("name") or old.get("name") or "").strip()
    email_address = str(data.get("email_address") or data.get("email") or old.get("email_address") or "").strip()
    if not name or not email_address:
        raise ValueError("Connection name and email address are required")

    public_config = dict(old.get("public_config") or {})
    incoming_public = data.get("public_config") or {}
    if not isinstance(incoming_public, dict):
        raise ValueError("public_config must be an object")
    public_config.update({str(k): v for k, v in incoming_public.items() if v is not None})

    if provider == "microsoft365":
        for field in ("tenant_id", "client_id"):
            if not str(public_config.get(field) or "").strip():
                raise ValueError(f"Microsoft 365 {field} is required")
    elif provider == "gmail":
        for field in ("client_id",):
            if not str(public_config.get(field) or "").strip():
                raise ValueError(f"Gmail {field} is required")
    else:
        public_config.setdefault("username", email_address)
        receive_protocol = str(public_config.get("receive_protocol") or "imap").lower()
        receive_security = str(public_config.get("receive_security") or "ssl").lower()
        smtp_security = str(public_config.get("smtp_security") or "starttls").lower()
        if receive_protocol not in RECEIVE_PROTOCOLS:
            raise ValueError("Receive protocol must be IMAP or POP3")
        if receive_security not in SECURITY_MODES or smtp_security not in SECURITY_MODES:
            raise ValueError("Mail security must be SSL, STARTTLS, or None")
        public_config["receive_protocol"] = receive_protocol
        public_config["receive_security"] = receive_security
        public_config["smtp_security"] = smtp_security
        for field in ("receive_host", "receive_port", "smtp_host", "smtp_port"):
            if not public_config.get(field):
                raise ValueError(f"Generic mail {field} is required")

    secrets_ciphertext = old.get("secrets_ciphertext")
    secrets = data.get("secrets")
    if data.get("clear_secrets") is True:
        secrets_ciphertext = None
    elif secrets is not None:
        if not isinstance(secrets, dict):
            raise ValueError("secrets must be an object")
        normalized = {str(k): str(v) for k, v in secrets.items() if v not in (None, "")}
        required_secrets = {
            "microsoft365": {"client_secret"},
            "gmail": {"client_secret", "refresh_token"},
            "generic": {"password"},
        }[provider]
        if not secrets_ciphertext and not required_secrets.issubset(normalized):
            missing = ", ".join(sorted(required_secrets - set(normalized)))
            raise ValueError(f"Missing credentials: {missing}")
        if normalized:
            secrets_ciphertext = encrypt_secret(json.dumps(normalized, ensure_ascii=False))
    if not secrets_ciphertext and data.get("enabled", old.get("enabled", True)) is not False:
        raise ValueError("Credentials are required for an enabled mail connection")

    return {
        "team_id": str(data.get("team_id") or old.get("team_id") or ""),
        "name": name[:100],
        "provider": provider,
        "email_address": email_address[:320],
        "public_config": public_config,
        "secrets_ciphertext": secrets_ciphertext,
        "enabled": data.get("enabled", old.get("enabled", True)) is not False,
    }


def insert_mail_connection(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document = {"_id": str(uuid.uuid4()), **data, "created_at": now, "updated_at": now, "delete_at": None}
    collection.insert_one(document)
    return document


def update_mail_connection(connection_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    collection.update_one({"_id": connection_id, "delete_at": None}, {"$set": {**data, "updated_at": datetime.now(timezone.utc)}})
    return get_mail_connection(connection_id)


def get_mail_connection(connection_id: str) -> dict[str, Any] | None:
    return collection.find_one({"_id": connection_id, "delete_at": None})


def list_mail_connections(team_id: str, *, enabled_only: bool = False) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"team_id": team_id, "delete_at": None}
    if enabled_only:
        query["enabled"] = True
    return list(collection.find(query).sort("name", 1))


def soft_delete_mail_connection(connection_id: str) -> bool:
    return collection.update_one(
        {"_id": connection_id, "delete_at": None},
        {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc)}},
    ).modified_count > 0


def decrypt_mail_secrets(document: dict[str, Any]) -> dict[str, str]:
    raw = decrypt_secret(document.get("secrets_ciphertext")) or "{}"
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Stored mail credentials are invalid")
    return {str(k): str(v) for k, v in value.items()}


def serialize_mail_connection(document: dict[str, Any], *, usage_count: int = 0) -> dict[str, Any]:
    return {
        "_id": str(document["_id"]),
        "team_id": document.get("team_id"),
        "name": document.get("name"),
        "provider": document.get("provider", "generic"),
        "email_address": document.get("email_address"),
        "public_config": document.get("public_config") or {},
        "enabled": document.get("enabled", True),
        "has_credentials": bool(document.get("secrets_ciphertext")),
        "agent_usage_count": usage_count,
    }
