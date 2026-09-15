from typing import Any

from agent_runtime.tools import ToolRegistry, ToolSpec
from business_document_connectors import create_document, read_document, search_documents
from mongo_table_connecters.business_document_bindings import list_business_document_bindings
from mongo_table_connecters.business_document_connections import (
    decrypt_business_document_secrets,
    get_business_document_connection,
)


def register_business_document_tools(registry: ToolRegistry, agent_id: str) -> None:
    for binding in list_business_document_bindings(agent_id, enabled_only=True):
        connection = get_business_document_connection(str(binding.get("connection_id") or ""))
        if not connection or connection.get("enabled") is False:
            continue
        secrets = decrypt_business_document_secrets(connection)
        alias = str(connection.get("name") or connection.get("provider") or "documents")
        suffix = str(binding.get("_id") or connection.get("_id"))[:8]
        permissions = set(binding.get("permissions") or ["read"])
        source = f"documents:{connection['_id']}"

        if "read" in permissions:
            async def search_handler(arguments: dict[str, Any], context: Any, _connection=connection, _secrets=secrets):
                return {
                    "documents": await search_documents(
                        _connection,
                        _secrets,
                        query=str(arguments.get("query") or ""),
                        limit=int(arguments.get("limit") or 10),
                    )
                }

            async def read_handler(arguments: dict[str, Any], context: Any, _connection=connection, _secrets=secrets):
                return await read_document(
                    _connection,
                    _secrets,
                    document_id=str(arguments.get("document_id") or ""),
                )

            registry.register(ToolSpec(
                name=f"documents_{alias}_search_{suffix}",
                description=f"Search Word, Excel, PowerPoint and other supported files in the assigned {connection['provider']} document library '{alias}'.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search text; blank lists items from the configured root folder."},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "additionalProperties": False,
                },
                handler=search_handler,
                source=source,
                risk_level="external",
            ))
            registry.register(ToolSpec(
                name=f"documents_{alias}_read_{suffix}",
                description=f"Read the text and cell content of a document returned by the '{alias}' document search tool.",
                input_schema={
                    "type": "object",
                    "properties": {"document_id": {"type": "string", "description": "Provider document ID returned by search."}},
                    "required": ["document_id"],
                    "additionalProperties": False,
                },
                handler=read_handler,
                source=source,
                timeout_seconds=75,
                risk_level="external",
            ))

        if "create" in permissions and connection.get("operation_mode") == "read_write":
            async def create_handler(arguments: dict[str, Any], context: Any, _connection=connection, _secrets=secrets):
                return await create_document(
                    _connection,
                    _secrets,
                    kind=str(arguments.get("kind") or ""),
                    title=str(arguments.get("title") or ""),
                    content=str(arguments.get("content") or ""),
                )

            registry.register(ToolSpec(
                name=f"documents_{alias}_create_{suffix}",
                description=(
                    f"Create a new Word, Excel, or PowerPoint document in '{alias}'. "
                    "This is a write action. Use it only when the user explicitly asks to create and save a cloud document."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["word", "excel", "powerpoint"]},
                        "title": {"type": "string", "description": "New document title or filename."},
                        "content": {"type": "string", "description": "Word body; CSV rows for Excel; slides separated by --- for PowerPoint."},
                    },
                    "required": ["kind", "title", "content"],
                    "additionalProperties": False,
                },
                handler=create_handler,
                source=source,
                timeout_seconds=90,
                max_output_chars=10_000,
                risk_level="write",
            ))
