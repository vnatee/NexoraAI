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


class IntegrationAssignmentError(ValueError):
    pass


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
