# Agent Catalog

## Phase 1 scope

Agent Catalog is NexoraAI's internal, governed marketplace for reusable Agent
templates. A published entry is not a shared live Agent. Publishing records an
immutable version snapshot; installation creates a new Agent owned by the
destination Team.

### User flows

- A Team administrator with **Manage agents** publishes an Agent from
  **Team workspace → AI workspace → Agents**. Team administrators can publish
  only to their own Team.
- A System administrator uses **System administration → Agent Catalog
  Governance** to create a System-owned template directly, publish/unpublish
  entries, and select selected-Team or all-Team visibility. Team-published
  entries may additionally remain restricted to their publisher Team.
- Team members browse entries available to their current Team from the Chat
  Agent selector or **Team workspace → AI workspace → Agent Catalog**.
- A Team administrator installs an available entry from Agent Catalog. The
  installed Agent then appears in that Team's normal Agent selector.
- Publishing the same source Agent again creates a new version. Existing
  installations remain pinned and display `Update available`; controlled
  upgrade is intentionally deferred.

Each catalog card includes the Agent name, purpose summary, author, publisher,
category, tags, version, runtime/tool requirements, and usage instructions.
Usage instructions should describe suitable inputs, expected output,
limitations, and any Team-local setup required after installation. The author
identity is derived from the authenticated account and cannot be supplied by
the browser.

The browse screen uses a responsive card grid. Cards intentionally show only
status, icon/initials, name, a short purpose, author, category, and version.
Long usage guidance, dependency details, installation, visibility, and
publication actions are available from the card detail or overflow menu.

## Security boundaries

- Catalog browse responses contain metadata and requirements only. They never
  include prompts, full configuration, credentials, or tool output.
- A snapshot clears `mcp_server_ids`, `mcp_tool_allowlists`, `subagent_ids`,
  and does not copy Data Groups or binding collections.
- An install is authorized with the destination Team's **Manage agents**
  permission and creates a distinct Agent ID.
- The installed snapshot is revalidated against currently available model
  profiles and runtime capabilities. An unavailable model fails explicitly.
- Publish, version publish, install, and governance changes write metadata-only
  audit events. Raw prompts and configuration are excluded from audit records.
- Unpublish prevents discovery and new installation. In Phase 1 it does not
  delete or disable already installed Team-local copies.

## Phase 1 API

- `GET /agent-catalog?team_id=<id>` — Team-visible metadata for members.
- `GET /agent-catalog` — all entries for System administrators.
- `POST /agent-catalog/publish` — publish a new snapshot version.
- `POST /admin/agent-catalog` — create a System-owned catalog template without
  creating a live or Team-owned Agent.
- `POST /agent-catalog/<id>/install` — install latest version into one Team.
- `PATCH /agent-catalog/<id>` — update metadata, status, and authorized
  visibility fields.

## Operational notes

The application creates indexes for catalog items, versions, installations,
and audit events during normal startup. Catalog collections use the configured
MongoDB/Cosmos-compatible database and therefore require the same backup,
availability, and retention controls as the rest of the application metadata.
