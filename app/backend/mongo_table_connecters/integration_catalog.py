from datetime import datetime, timezone
from typing import Any

from mongo_table_connecters.mongo_connector import get_database

_COLLECTIONS = {
    "rest_api": "external_apis",
    "database": "external_databases",
    "mail": "mail_connections",
    "messaging": "messaging_connections",
    "mcp": "mcp_servers",
    "business_documents": "business_document_connections",
}

_BINDINGS = {
    "rest_api": ("agent_bindings", "integration_id"),
    "database": ("database_bindings", "integration_id"),
    "mail": ("mail_bindings", "email_id"),
    "messaging": ("messaging_bindings", "connection_id"),
    "mcp": ("agents", "config.tool_settings.mcp_server_ids"),
    "business_documents": ("business_document_bindings", "connection_id"),
}

_CONNECTION_METADATA = {
    "rest_api": {
        "connection_type": "native",
        "provider_field": "type",
        "default_provider": "rest_api",
    },
    "database": {
        "connection_type": "native",
        "provider_field": "db_type",
        "default_provider": "database",
    },
    "mail": {
        "connection_type": "native",
        "provider_field": "provider",
        "default_provider": "mail",
    },
    "messaging": {
        "connection_type": "native",
        "provider_field": "provider",
        "default_provider": "messaging",
    },
    "mcp": {
        "connection_type": "mcp",
        "provider_field": "vendor",
        "default_provider": "generic",
    },
    "business_documents": {
        "connection_type": "native",
        "provider_field": "provider",
        "default_provider": "documents",
    },
}


class IntegrationAssignmentError(ValueError):
    pass


def _team_query(team_id: str) -> object:
    normalized = str(team_id or "")
    return normalized if normalized else {"$in": [None, ""]}


def _agent_usage_count(database: Any, kind: str, connection_id: str) -> int:
    binding_collection, integration_field = _BINDINGS[kind]
    query = {integration_field: connection_id, "delete_at": None}
    if kind == "mcp":
        return int(database[binding_collection].count_documents(query))
    return len(database[binding_collection].distinct("agent_id", query))


def _connection_detail(kind: str, document: dict[str, Any]) -> str:
    if kind == "mcp":
        return str(document.get("url") or "")
    if kind == "rest_api":
        return str(document.get("base_url") or "")
    if kind == "database":
        host = str(document.get("host") or "")
        database = str(document.get("database") or "")
        return " / ".join(value for value in (host, database) if value)
    if kind == "mail":
        return str(document.get("email_address") or "")
    public_config = document.get("public_config") or {}
    if not isinstance(public_config, dict):
        return ""
    if kind == "messaging":
        return str(public_config.get("default_target") or "")
    return str(
        public_config.get("drive_id")
        or public_config.get("shared_drive_id")
        or public_config.get("root_folder_id")
        or ""
    )


def list_integration_connections(team_id: str) -> list[dict[str, Any]]:
    """Return a secret-free projection across legacy connection collections.

    This is intentionally a compatibility read model. Provider-specific records
    remain the source of truth until their CRUD and binding migrations are
    completed.
    """

    database = get_database()
    connections: list[dict[str, Any]] = []
    for kind, collection_name in _COLLECTIONS.items():
        metadata = _CONNECTION_METADATA[kind]
        documents = database[collection_name].find(
            {"team_id": _team_query(team_id), "delete_at": None}
        )
        for document in documents:
            connection_id = str(document.get("_id") or "")
            provider = str(
                document.get(metadata["provider_field"])
                or metadata["default_provider"]
            ).strip().lower()
            enabled = document.get("enabled", True) is not False
            provisioning_status = str(document.get("provisioning_status") or "")
            status = (
                provisioning_status
                if kind == "mcp" and provisioning_status not in {"", "external"}
                else "enabled" if enabled else "disabled"
            )
            connections.append(
                {
                    "id": connection_id,
                    "kind": kind,
                    "connection_type": metadata["connection_type"],
                    "provider": provider,
                    "name": str(document.get("name") or provider or kind),
                    "team_id": str(document.get("team_id") or ""),
                    "enabled": enabled,
                    "status": status,
                    "detail": _connection_detail(kind, document),
                    "agent_usage_count": _agent_usage_count(
                        database, kind, connection_id
                    ),
                }
            )
    return sorted(
        connections,
        key=lambda item: (str(item["name"]).casefold(), str(item["kind"])),
    )


def list_agent_integration_bindings(
    agent_id: str, *, agent_document: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Project all legacy Agent bindings into one provider-neutral shape."""

    database = get_database()
    bindings: list[dict[str, Any]] = []
    for kind, (collection_name, integration_field) in _BINDINGS.items():
        if kind == "mcp":
            continue
        for document in database[collection_name].find(
            {"agent_id": agent_id, "delete_at": None}
        ):
            connection_id = str(document.get(integration_field) or "")
            if not connection_id:
                continue
            bindings.append(
                {
                    "id": str(document.get("_id") or ""),
                    "agent_id": agent_id,
                    "connection_id": connection_id,
                    "kind": kind,
                    "enabled": document.get("enabled", True) is not False,
                    "source": "legacy",
                }
            )

    agent = agent_document or database["agents"].find_one(
        {"_id": agent_id, "delete_at": None}
    )
    tool_settings = ((agent or {}).get("config") or {}).get("tool_settings") or {}
    for connection_id in tool_settings.get("mcp_server_ids") or []:
        normalized_id = str(connection_id or "").strip()
        if normalized_id:
            bindings.append(
                {
                    "id": f"legacy-mcp:{agent_id}:{normalized_id}",
                    "agent_id": agent_id,
                    "connection_id": normalized_id,
                    "kind": "mcp",
                    "enabled": True,
                    "source": "legacy_agent_config",
                }
            )
    return bindings


def assign_unassigned_integration(kind: str, integration_id: str, team_id: str) -> dict[str, Any]:
    collection_name = _COLLECTIONS.get(kind)
    if not collection_name:
        raise IntegrationAssignmentError("Unsupported integration type")
    if not integration_id or not team_id:
        raise IntegrationAssignmentError("integration_id and team_id are required")

    database = get_database()
    collection = database[collection_name]
    document = collection.find_one({"_id": integration_id, "delete_at": None})
    if not document:
        raise IntegrationAssignmentError("Integration not found")
    if str(document.get("team_id") or ""):
        raise IntegrationAssignmentError("Integration is already assigned to a team")

    binding_collection, integration_field = _BINDINGS[kind]
    if database[binding_collection].count_documents(
        {integration_field: integration_id, "delete_at": None}
    ):
        raise IntegrationAssignmentError("Remove Agent bindings before assigning this integration")

    timestamp_field = "update_at" if kind == "mcp" else "updated_at"
    result = collection.update_one(
        {"_id": integration_id, "delete_at": None, "team_id": {"$in": [None, ""]}},
        {"$set": {"team_id": team_id, timestamp_field: datetime.now(timezone.utc)}},
    )
    if result.modified_count != 1:
        raise IntegrationAssignmentError("Integration assignment changed; refresh and try again")
    return {"integration_id": integration_id, "integration_type": kind, "team_id": team_id}
