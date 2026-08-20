# LangGraph agent runtime

The new runtime is an opt-in compatibility layer. The legacy chat path remains the default while agents are migrated and smoke-tested one at a time.

```mermaid
flowchart LR
    Chat --> Runtime[LangGraph runtime]
    Runtime --> Model[Agent-selected LLM]
    Runtime --> Registry[LangChain tool registry]
    Registry --> RAG[Permission-aware RAG]
    Registry --> API[REST integrations]
    Registry --> DB[External databases]
    Registry --> MCP[MCP servers]
    Registry --> Sub[Bound sub-agents]
```

## Enable it

Enable all agents for a development smoke test:

```bash
export AGENT_RUNTIME_MODE=langgraph
./app/start.sh
```

For a gradual rollout, leave the environment variable unset (or set it to `per_agent`) and select **Agent Runtime → LangGraph (Tools / MCP)** on one agent. Select **Legacy** for rollback. Setting the environment variable explicitly to `legacy` or `langgraph` overrides every agent. Models used by a LangGraph agent must have **Supports tool / function calling** enabled.

Each LangGraph agent has independent **Built-in Tools** settings. Knowledge Search supports `Auto` (the model decides), `Always search` (RAG runs before the first model call, close to Legacy behavior), and `Disabled` (the tool schema is not sent). External Database, REST, MCP, and Sub-agent tools can also be disabled independently. Disabling a tool removes it from the registry rather than merely asking the model not to use it.

MCP Invocation supports `Auto` and `Required`. Auto forces an MCP call on the first model iteration when the user explicitly names the configured MCP server (for example, Datadog); otherwise the model decides. Required exposes only MCP tools on the first iteration and sends `tool_choice=required`, guaranteeing that a dedicated MCP agent retrieves external data before its first answer. Later iterations return to normal tool selection so the agent can render charts or use another enabled capability.

## MCP management

MCP uses Streamable HTTP so the same configuration works in Docker and Kubernetes. System administrators manage servers from **Admin Management → MCP Servers**. Each agent receives only the enabled managed servers selected in its configuration. Header values are encrypted with `APP_DATA_ENCRYPTION_KEY`, are never returned by the API, and a blank header field during editing preserves the existing secret.

The server **Test** action performs tool discovery and reports the names exposed by the server. Use an allowlist for every production MCP server. Discovery failure is isolated to that server, so the remaining agent tools continue to work.

`MCP_SERVERS_JSON` remains supported as a deployment-level compatibility option:

```bash
export MCP_SERVERS_JSON='[
  {
    "name": "drawio",
    "url": "http://drawio-mcp:8000/mcp",
    "enabled": true,
    "headers": {"Authorization": "Bearer replace-from-secret-store"},
    "allowed_tools": ["create_diagram", "edit_diagram"],
    "timeout_seconds": 60
  }
]'
```

Do not commit tokens in this JSON; inject them with container/Kubernetes secrets.

### Datadog MCP preset

Use **Admin Management → MCP Servers → Add Datadog**. The preset uses Datadog's current Streamable HTTP endpoint (`/v1/mcp`), supports US1, EU and another official Datadog site, and can scope discovery with the `toolsets` query parameter. For this server-side runtime, authenticate with either a Personal/Service Access Token (Bearer, recommended) or Datadog API and Application keys. Credentials are encrypted using `APP_DATA_ENCRYPTION_KEY`.

The Datadog identity needs `mcp_read` plus permission for each underlying product. Grant `mcp_write` only if the agent is intentionally allowed to modify Datadog resources. OAuth browser login is not part of this preset yet because it requires per-user callback, token refresh and revocation storage; the header-based service identity is deterministic for Docker/Kubernetes deployments.

## Local REST integrations

REST tools block loopback, link-local and private targets by default to reduce SSRF risk. For trusted services on the same Docker network, enable private targets explicitly:

```bash
export ALLOW_PRIVATE_INTEGRATION_ENDPOINTS=true
```

Do not enable this flag for an environment where untrusted users can create integrations.

## Sub-agents

An agent can delegate focused work only to explicitly selected LangGraph agents in the same team. The child uses its own prompt, model profile and enabled tools. The runtime propagates a parent run ID and agent stack, rejects cycles, and enforces a configurable delegation depth from 1 to 5. Legacy-runtime agents are intentionally excluded from the sub-agent selector because delegation requires the tool runtime contract.

## Tool execution policy

Every agent has a server-enforced policy independent of its prompt. The policy limits total calls, calls per tool, argument/output size and timeout, and can block exact tool names or source prefixes such as `mcp`, `external_database`, `external_api`, `subagent`, `rag`, or `chart`. A denied call is returned to the model as a structured `policy_denied` tool result and is recorded in the audit trail.

Tool calls execute automatically, matching the current product decision. This policy is the enforcement boundary; it does not add a per-call confirmation dialog.

## Audit events and tracing

Each root and delegated run gets a UUID trace ID. Structured events cover run start/completion/failure, model iterations, token usage, tool success/failure, unknown tools and policy denial. Audit documents contain actor/team/agent IDs, parent-child run linkage, durations, argument field names and payload sizes. Raw prompts, arguments, tool outputs and credentials are deliberately not persisted.

System administrators can view recent events in **Admin Management → Agent Audit** or query `GET /admin/agent-audit-events` and filter by agent, run, event type, status and time window. Chat responses expose only the trace ID and event count. Set `DISABLE_AGENT_AUDIT_PERSISTENCE=true` only for tests or constrained local development.

## Current migration boundary

- RAG is called on demand and reuses the existing Azure AI Search implementation, embedding configuration and permission filter.
- Existing REST bindings become real model tools; LangGraph no longer relies on the frontend `[y/n]` parsing workflow.
- Bound MongoDB data is queried on demand instead of being added to every prompt.
- MCP tools are discovered with the official Python SDK, namespaced per server, and managed through encrypted admin CRUD.
- Sub-agent selection is persisted in agent configuration with same-team and recursion-depth protection.
- Execution policies and metadata-only audit events are persisted server-side.
- Chat response and citation shapes remain compatible with the current frontend.

Recommended next slices are: shared time/token budgets across a whole delegation tree; persisted LangGraph checkpoints; audit retention/index policies; then an open-source vector-store adapter behind the same RAG tool.
