import json
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from core.provider_secrets import decrypt_provider_secret, encrypt_provider_secret
from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["mcp_servers"]

MCP_CATEGORIES = {
    "observability",
    "diagram_collaboration",
    "cloud_platform",
    "developer_tools",
    "data_search",
    "custom",
}


def normalize_mcp_server_payload(
    data: object, *, existing: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("MCP server payload must be an object")
    name = str(data.get("name") or (existing or {}).get("name") or "").strip()
    url = str(data.get("url") or (existing or {}).get("url") or "").strip()
    parsed = urlparse(url)
    if not name:
        raise ValueError("MCP server name is required")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("MCP server URL must use http or https")
    vendor = (
        str(data.get("vendor") or (existing or {}).get("vendor") or "generic")
        .strip()
        .lower()
    )
    if vendor not in ("generic", "datadog"):
        raise ValueError("Unsupported MCP vendor")
    default_category = "observability" if vendor == "datadog" else "custom"
    category = (
        str(
            data.get("category")
            or (existing or {}).get("category")
            or default_category
        )
        .strip()
        .lower()
    )
    if category not in MCP_CATEGORIES:
        raise ValueError("Unsupported MCP category")
    if vendor == "datadog":
        category = "observability"
    default_auth_type = "bearer" if vendor == "datadog" else "headers"
    auth_type = (
        str(
            data.get("auth_type")
            or (existing or {}).get("auth_type")
            or default_auth_type
        )
        .strip()
        .lower()
    )
    allowed_auth_types = (
        ("bearer", "datadog_keys") if vendor == "datadog" else ("headers",)
    )
    if auth_type not in allowed_auth_types:
        raise ValueError(f"Unsupported authentication type for {vendor} MCP")
    allowed_tools = data.get("allowed_tools")
    if allowed_tools is None:
        allowed_tools = (existing or {}).get("allowed_tools") or []
    if not isinstance(allowed_tools, list):
        raise ValueError("allowed_tools must be an array")
    normalized_tools = []
    for item in allowed_tools[:200]:
        tool = str(item or "").strip()
        if tool and tool not in normalized_tools:
            normalized_tools.append(tool)

    headers_ciphertext = (existing or {}).get("headers_ciphertext")
    normalized_headers: dict[str, str] | None = None
    if data.get("clear_headers") is True:
        headers_ciphertext = None
    elif "headers" in data and data.get("headers") is not None:
        headers = data.get("headers")
        if not isinstance(headers, dict):
            raise ValueError("headers must be an object")
        normalized_headers = {
            str(key).strip(): str(value)
            for key, value in headers.items()
            if str(key).strip() and value is not None
        }
        headers_ciphertext = encrypt_provider_secret(
            json.dumps(normalized_headers, ensure_ascii=False)
        )

    if vendor == "datadog":
        hostname = str(parsed.hostname or "").lower()
        if not (
            hostname.startswith("mcp.")
            and (
                hostname.endswith(".datadoghq.com")
                or hostname.endswith(".datadoghq.eu")
                or hostname in ("mcp.datadoghq.com", "mcp.datadoghq.eu")
            )
        ):
            raise ValueError("Datadog MCP must use an official mcp.datadoghq endpoint")
        if not parsed.path.rstrip("/").endswith("/v1/mcp"):
            raise ValueError("Datadog MCP URL must end with /v1/mcp")
        if (
            existing
            and auth_type != existing.get("auth_type", default_auth_type)
            and normalized_headers is None
        ):
            raise ValueError(
                "Provide new credentials when changing Datadog authentication type"
            )
        if normalized_headers is not None:
            if auth_type == "bearer" and not normalized_headers.get(
                "Authorization", ""
            ).startswith("Bearer "):
                raise ValueError(
                    "Datadog PAT/SAT must use an Authorization Bearer header"
                )
            if auth_type == "datadog_keys" and not all(
                normalized_headers.get(key)
                for key in ("DD_API_KEY", "DD_APPLICATION_KEY")
            ):
                raise ValueError("Datadog API and application keys are both required")
        if (
            data.get("enabled", (existing or {}).get("enabled", True)) is not False
            and not headers_ciphertext
        ):
            raise ValueError("Datadog MCP requires PAT/SAT or API and application keys")

    return {
        "name": name[:100],
        "url": url[:2000],
        "vendor": vendor,
        "category": category,
        "auth_type": auth_type,
        "enabled": data.get("enabled", (existing or {}).get("enabled", True))
        is not False,
        "allowed_tools": normalized_tools,
        "timeout_seconds": max(
            1.0,
            min(
                float(
                    data.get("timeout_seconds")
                    or (existing or {}).get("timeout_seconds")
                    or 60
                ),
                300.0,
            ),
        ),
        "headers_ciphertext": headers_ciphertext,
    }


def insert_mcp_server(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    document = {
        "_id": str(uuid.uuid4()),
        **data,
        "create_at": now,
        "update_at": now,
        "delete_at": None,
    }
    collection.insert_one(document)
    return document


def list_mcp_servers(*, enabled_only: bool = False) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"delete_at": None}
    if enabled_only:
        query["enabled"] = True
    return list(collection.find(query).sort("name", 1))


def get_mcp_server(server_id: str) -> dict[str, Any] | None:
    return collection.find_one({"_id": server_id, "delete_at": None})


def update_mcp_server(server_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    collection.update_one(
        {"_id": server_id, "delete_at": None},
        {"$set": {**data, "update_at": datetime.now(timezone.utc)}},
    )
    return get_mcp_server(server_id)


def soft_delete_mcp_server(server_id: str) -> bool:
    return (
        collection.update_one(
            {"_id": server_id, "delete_at": None},
            {
                "$set": {
                    "enabled": False,
                    "delete_at": datetime.now(timezone.utc),
                }
            },
        ).modified_count
        > 0
    )


def decrypt_mcp_headers(document: dict[str, Any]) -> dict[str, str]:
    encrypted = document.get("headers_ciphertext")
    if not encrypted:
        return {}
    value = json.loads(decrypt_provider_secret(str(encrypted)) or "{}")
    if not isinstance(value, dict):
        raise ValueError("Stored MCP headers are invalid")
    return {str(key): str(item) for key, item in value.items()}


def serialize_mcp_server(document: dict[str, Any]) -> dict[str, Any]:
    serialized = {
        key: value
        for key, value in document.items()
        if key not in ("headers_ciphertext", "delete_at")
    }
    serialized.setdefault("vendor", "generic")
    serialized.setdefault(
        "category",
        "observability" if serialized.get("vendor") == "datadog" else "custom",
    )
    serialized.setdefault("auth_type", "headers")
    return serialized | {"has_headers": bool(document.get("headers_ciphertext"))}
