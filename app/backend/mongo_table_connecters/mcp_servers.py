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
    "business_workflows",
    "data_search",
    "custom",
}
MCP_VENDORS = {
    "generic",
    "datadog",
    "azure",
    "drawio",
    "atlassian",
    "servicenow",
}
MCP_OPERATION_MODES = {"read_only", "read_write"}
MCP_DEPLOYMENT_MODES = {"external", "managed"}


def normalize_mcp_server_payload(
    data: object, *, existing: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("MCP server payload must be an object")
    name = str(data.get("name") or (existing or {}).get("name") or "").strip()
    if not name:
        raise ValueError("MCP server name is required")
    vendor = (
        str(data.get("vendor") or (existing or {}).get("vendor") or "generic")
        .strip()
        .lower()
    )
    if vendor not in MCP_VENDORS:
        raise ValueError("Unsupported MCP vendor")
    if existing and "vendor" in data and vendor != str(
        existing.get("vendor") or "generic"
    ):
        raise ValueError("MCP vendor cannot be changed after creation")
    deployment_mode = str(
        data.get("deployment_mode")
        or (existing or {}).get("deployment_mode")
        or "external"
    ).strip().lower()
    if deployment_mode not in MCP_DEPLOYMENT_MODES:
        raise ValueError("MCP deployment_mode must be external or managed")
    if existing and "deployment_mode" in data and deployment_mode != str(
        existing.get("deployment_mode") or "external"
    ):
        raise ValueError("MCP deployment mode cannot be changed after creation")
    if deployment_mode == "managed" and vendor != "azure":
        raise ValueError("Managed MCP provisioning currently supports only Azure")
    url = str(data.get("url") or (existing or {}).get("url") or "").strip()
    if deployment_mode == "managed":
        url = str((existing or {}).get("url") or "").strip()
    parsed = urlparse(url)
    if deployment_mode != "managed" and (
        parsed.scheme not in ("http", "https") or not parsed.hostname
    ):
        raise ValueError("MCP server URL must use http or https")
    if url and (parsed.scheme not in ("http", "https") or not parsed.hostname):
        raise ValueError("MCP server URL must use http or https")
    default_category = {
        "datadog": "observability",
        "azure": "cloud_platform",
        "drawio": "diagram_collaboration",
        "atlassian": "business_workflows",
        "servicenow": "business_workflows",
    }.get(vendor, "custom")
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
    elif vendor == "azure":
        category = "cloud_platform"
    elif vendor == "drawio":
        category = "diagram_collaboration"
    elif vendor in {"atlassian", "servicenow"}:
        category = "business_workflows"
    default_auth_type = (
        "bearer"
        if vendor in {"datadog", "atlassian", "servicenow"}
        else "headers"
    )
    auth_type = (
        str(
            data.get("auth_type")
            or (existing or {}).get("auth_type")
            or default_auth_type
        )
        .strip()
        .lower()
    )
    allowed_auth_types = {
        "datadog": ("bearer", "datadog_keys"),
        "azure": ("headers", "entra_client_credentials"),
        "atlassian": ("bearer",),
        "servicenow": ("bearer",),
    }.get(vendor, ("headers",))
    if vendor == "azure" and deployment_mode == "managed":
        auth_type = "headers"
    if auth_type not in allowed_auth_types:
        raise ValueError(f"Unsupported authentication type for {vendor} MCP")
    operation_mode = str(
        data.get("operation_mode")
        or (existing or {}).get("operation_mode")
        or ("read_only" if vendor == "azure" else "read_write")
    ).strip().lower()
    if operation_mode not in MCP_OPERATION_MODES:
        raise ValueError("MCP operation_mode must be read_only or read_write")
    if vendor == "azure":
        operation_mode = "read_only"
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

    if vendor == "atlassian":
        if (
            parsed.scheme != "https"
            or str(parsed.hostname or "").lower() != "mcp.atlassian.com"
            or parsed.path.rstrip("/") != "/v1/mcp/authv2"
        ):
            raise ValueError(
                "Atlassian MCP must use https://mcp.atlassian.com/v1/mcp/authv2"
            )
        if normalized_headers is not None and not normalized_headers.get(
            "Authorization", ""
        ).startswith("Bearer "):
            raise ValueError("Atlassian MCP requires an OAuth Bearer token")
        if (
            data.get("enabled", (existing or {}).get("enabled", True)) is not False
            and not headers_ciphertext
        ):
            raise ValueError("Atlassian MCP requires an OAuth Bearer token")

    if vendor == "servicenow":
        hostname = str(parsed.hostname or "").lower()
        if parsed.scheme != "https" or not (
            hostname == "service-now.com" or hostname.endswith(".service-now.com")
        ):
            raise ValueError(
                "ServiceNow MCP must use an HTTPS endpoint on the ServiceNow instance"
            )
        if normalized_headers is not None and not normalized_headers.get(
            "Authorization", ""
        ).startswith("Bearer "):
            raise ValueError("ServiceNow MCP requires an OAuth Bearer token")
        if (
            data.get("enabled", (existing or {}).get("enabled", True)) is not False
            and not headers_ciphertext
        ):
            raise ValueError("ServiceNow MCP requires an OAuth Bearer token")

    def bounded_text(field: str, maximum: int = 255) -> str:
        return str(data.get(field) or (existing or {}).get(field) or "").strip()[:maximum]

    entra_secret_ciphertext = (existing or {}).get("entra_client_secret_ciphertext")
    azure_secret_ciphertext = (existing or {}).get("azure_client_secret_ciphertext")
    if data.get("clear_entra_client_secret") is True:
        entra_secret_ciphertext = None
    elif str(data.get("entra_client_secret") or "").strip():
        entra_secret_ciphertext = encrypt_provider_secret(
            str(data["entra_client_secret"]).strip()
        )
    if data.get("clear_azure_client_secret") is True:
        azure_secret_ciphertext = None
    elif str(data.get("azure_client_secret") or "").strip():
        azure_secret_ciphertext = encrypt_provider_secret(
            str(data["azure_client_secret"]).strip()
        )

    entra_tenant_id = bounded_text("entra_tenant_id")
    entra_client_id = bounded_text("entra_client_id")
    entra_scope = bounded_text("entra_scope", 500)
    azure_tenant_id = bounded_text("azure_tenant_id")
    azure_client_id = bounded_text("azure_client_id")
    subscription_values = data.get("azure_subscription_ids")
    if subscription_values is None:
        subscription_values = (existing or {}).get("azure_subscription_ids") or []
    if not isinstance(subscription_values, list):
        raise ValueError("azure_subscription_ids must be an array")
    azure_subscription_ids = []
    for value in subscription_values[:100]:
        subscription_id = str(value or "").strip()
        if subscription_id and subscription_id not in azure_subscription_ids:
            azure_subscription_ids.append(subscription_id[:100])

    if vendor == "azure" and auth_type == "entra_client_credentials":
        if not all((entra_tenant_id, entra_client_id, entra_scope)):
            raise ValueError(
                "Azure MCP Entra authentication requires tenant ID, client ID, and scope"
            )
        if data.get("enabled", (existing or {}).get("enabled", True)) is not False and not entra_secret_ciphertext:
            raise ValueError("Azure MCP Entra authentication requires a client secret")
    if vendor == "azure" and deployment_mode == "managed":
        entra_tenant_id = ""
        entra_client_id = ""
        entra_scope = ""
        entra_secret_ciphertext = None
        if not all((azure_tenant_id, azure_client_id)):
            raise ValueError(
                "Managed Azure MCP requires Azure tenant and workload client IDs"
            )
        if not azure_subscription_ids:
            raise ValueError("Managed Azure MCP requires at least one subscription ID")
        if data.get("enabled", (existing or {}).get("enabled", True)) is not False and not azure_secret_ciphertext:
            raise ValueError("Managed Azure MCP requires an Azure workload client secret")

    return {
        "team_id": str(data.get("team_id") or (existing or {}).get("team_id") or "").strip(),
        "name": name[:100],
        "url": url[:2000],
        "vendor": vendor,
        "deployment_mode": deployment_mode,
        "category": category,
        "auth_type": auth_type,
        "operation_mode": operation_mode,
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
        "entra_tenant_id": entra_tenant_id,
        "entra_client_id": entra_client_id,
        "entra_scope": entra_scope,
        "entra_client_secret_ciphertext": entra_secret_ciphertext,
        "azure_tenant_id": azure_tenant_id,
        "azure_client_id": azure_client_id,
        "azure_subscription_ids": azure_subscription_ids,
        "azure_client_secret_ciphertext": azure_secret_ciphertext,
        "provisioning_status": str(
            (existing or {}).get("provisioning_status")
            or ("pending" if deployment_mode == "managed" else "external")
        ),
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


def list_mcp_servers(team_id: str, *, enabled_only: bool = False) -> list[dict[str, Any]]:
    normalized_team_id = str(team_id or "")
    query: dict[str, Any] = {
        "team_id": normalized_team_id if normalized_team_id else {"$in": [None, ""]},
        "delete_at": None,
    }
    if enabled_only:
        query["enabled"] = True
    servers = list(collection.find(query).sort("name", 1))
    if enabled_only:
        servers = [
            item
            for item in servers
            if str(item.get("deployment_mode") or "external") != "managed"
            or item.get("provisioning_status") == "ready"
        ]
    return servers


def list_enabled_managed_azure_mcp_servers() -> list[dict[str, Any]]:
    return list(
        collection.find(
            {
                "vendor": "azure",
                "deployment_mode": "managed",
                "enabled": True,
                "delete_at": None,
            }
        )
    )


def list_pending_managed_azure_mcp_deletions() -> list[dict[str, Any]]:
    return list(
        collection.find(
            {
                "vendor": "azure",
                "deployment_mode": "managed",
                "provisioning_status": "cleanup_pending",
                "delete_at": {"$ne": None},
            }
        )
    )


def list_pending_managed_azure_mcp_stops() -> list[dict[str, Any]]:
    return list(
        collection.find(
            {
                "vendor": "azure",
                "deployment_mode": "managed",
                "enabled": False,
                "provisioning_status": "stop_pending",
                "delete_at": None,
            }
        )
    )


def get_mcp_server(server_id: str) -> dict[str, Any] | None:
    return collection.find_one({"_id": server_id, "delete_at": None})


def update_mcp_server(server_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    collection.update_one(
        {"_id": server_id, "delete_at": None},
        {"$set": {**data, "update_at": datetime.now(timezone.utc)}},
    )
    return get_mcp_server(server_id)


def soft_delete_mcp_server(
    server_id: str,
    *,
    provisioning_status: str | None = None,
    provisioning_error: str = "",
) -> bool:
    values: dict[str, Any] = {
        "enabled": False,
        "delete_at": datetime.now(timezone.utc),
    }
    if provisioning_status:
        values["provisioning_status"] = provisioning_status
        values["provisioning_error"] = provisioning_error[:500]
    return (
        collection.update_one(
            {"_id": server_id, "delete_at": None},
            {
                "$set": values,
                "$unset": {
                    "headers_ciphertext": "",
                    "entra_client_secret_ciphertext": "",
                    "azure_client_secret_ciphertext": "",
                },
            },
        ).modified_count
        > 0
    )


def complete_mcp_server_cleanup(server_id: str) -> None:
    collection.update_one(
        {"_id": server_id, "provisioning_status": "cleanup_pending"},
        {
            "$set": {
                "provisioning_status": "deleted",
                "provisioning_error": "",
                "update_at": datetime.now(timezone.utc),
            }
        },
    )


def decrypt_mcp_headers(document: dict[str, Any]) -> dict[str, str]:
    encrypted = document.get("headers_ciphertext")
    if not encrypted:
        return {}
    value = json.loads(decrypt_provider_secret(str(encrypted)) or "{}")
    if not isinstance(value, dict):
        raise ValueError("Stored MCP headers are invalid")
    return {str(key): str(item) for key, item in value.items()}


def decrypt_mcp_entra_client_secret(document: dict[str, Any]) -> str:
    return decrypt_provider_secret(document.get("entra_client_secret_ciphertext")) or ""


def decrypt_azure_mcp_runtime_secret(document: dict[str, Any]) -> str:
    return decrypt_provider_secret(document.get("azure_client_secret_ciphertext")) or ""


def azure_mcp_runtime_config(document: dict[str, Any]) -> dict[str, Any]:
    if (
        str(document.get("vendor") or "") != "azure"
        or str(document.get("deployment_mode") or "external") != "managed"
    ):
        raise ValueError("MCP connection is not a managed Azure deployment")
    return {
        "azure_tenant_id": str(document.get("azure_tenant_id") or ""),
        "azure_client_id": str(document.get("azure_client_id") or ""),
        "azure_client_secret": decrypt_azure_mcp_runtime_secret(document),
        "azure_subscription_ids": tuple(document.get("azure_subscription_ids") or ()),
    }


def serialize_mcp_server(document: dict[str, Any]) -> dict[str, Any]:
    serialized = {
        key: value
        for key, value in document.items()
        if key
        not in (
            "headers_ciphertext",
            "entra_client_secret_ciphertext",
            "azure_client_secret_ciphertext",
            "server_app_client_id",
            "delete_at",
        )
    }
    serialized.setdefault("vendor", "generic")
    serialized.setdefault(
        "category",
        "observability" if serialized.get("vendor") == "datadog" else "custom",
    )
    serialized.setdefault("auth_type", "headers")
    serialized.setdefault(
        "operation_mode",
        "read_only" if serialized.get("vendor") == "azure" else "read_write",
    )
    serialized.setdefault("team_id", "")
    serialized.setdefault("deployment_mode", "external")
    return serialized | {
        "has_headers": bool(document.get("headers_ciphertext")),
        "has_entra_client_secret": bool(document.get("entra_client_secret_ciphertext")),
        "has_azure_client_secret": bool(document.get("azure_client_secret_ciphertext")),
    }
