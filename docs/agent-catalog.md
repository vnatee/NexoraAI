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

### Built-in template seeding

Deployments may seed all maintained built-in templates with:

```bash
docker compose --env-file .env.local-runtime \
  -f docker-compose.local-runtime.yml \
  exec app python -m core.catalog_seed --apply
```

For a source checkout using the project virtual environment, the equivalent
command is `.venv/bin/python scripts/seed_catalog_templates.py --apply`.

The command is idempotent. It creates version 1 when absent, creates a new
version only when the maintained template changes, and otherwise reports
`already-current`. Run it in the application environment so it uses the same
MongoDB configuration and encryption boundary as NexoraAI.

### Datadog Operations Analyst template

After installation, a Team administrator must bind the Team's own Datadog MCP
connection and assign the operational Knowledge Data Groups that contain its
approved runbooks, incident reviews, architecture, known errors, and change
procedures. No Datadog connection ID, tenant credential, or tool allowlist is
stored in the Catalog snapshot. Installation automatically creates a validated
Chart binding in auto mode for line, area, bar, gauge, scatter, and heatmap
visualizations. Charts must use exact numeric data from the successful Datadog
tool result; the Agent may not estimate missing points. The template is
read-only and prepares approval-ready remediation; it does not silence monitors
or change workloads.

### HR Employee Services Advisor template

The built-in HR template is a Knowledge-only, privacy-preserving employee
services advisor. It explains policies, eligibility conditions, approval paths,
deadlines, required documents, and service targets with source citations. It
does not access HR systems of record, disclose another employee's information,
submit requests, approve entitlements, or make employment decisions.

The fictional RAG demonstration package is under `docs/demo/hr`. Upload only
the three files under `docs/demo/hr/rag` to a restricted HR demo Data Group;
do not upload `HR_Demo_Guide.md`, because it contains presenter prompts rather
than policy evidence. The guide includes a six-step demonstration covering
annual leave, learning allowance, overseas hybrid work, employment letters,
privacy refusal, and missing evidence.

The application creates indexes for catalog items, versions, installations,
and audit events during normal startup. Catalog collections use the configured
MongoDB/Cosmos-compatible database and therefore require the same backup,
availability, and retention controls as the rest of the application metadata.
