# Unified integration control plane

NexoraAI presents native connectors and MCP connections as one Integration
concept. MCP describes the connection protocol; it is not a separate business
capability.

## Current compatibility architecture

The provider-specific collections remain the source of truth:

- `external_apis`
- `external_databases`
- `mail_connections`
- `messaging_connections`
- `business_document_connections`
- `mcp_servers`

`list_integration_connections()` projects these records into one secret-free
shape containing connection ID, kind, connection type, provider, Team, status,
detail, and Agent usage count. The management UI consumes this projection to
show all configured connections in one list under **Configured connections**.
Creation entry points live separately under **Browse catalog**. Both views show
the active Team or System/Unassigned scope. Selecting a connection still opens
its provider-specific editor.

Agent bindings are also projected into one normalized read shape by
`list_agent_integration_bindings()`. It reads the existing binding collections
and the legacy `config.tool_settings.mcp_server_ids` field without changing
their runtime behavior.

## Migration rule

Do not copy encrypted credentials into a common collection. Provider-specific
records own their credential lifecycle and validation. A future canonical
binding collection may be introduced with dual reads and writes, followed by a
separately verified data migration. Until then, existing identifiers and Agent
bindings remain authoritative.

## Shared security contract

Every connection type must retain Team ownership, management authorization,
encrypted secrets, Agent assignment checks, operation/tool policy, timeout
limits, and metadata-only audit events. Provider adapters may implement
different authentication, discovery, and execution protocols behind that
common control plane.
