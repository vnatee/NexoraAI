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

## MCP configuration

MCP uses Streamable HTTP so the same configuration works in Docker and Kubernetes. Configuration is currently environment-based; the next migration slice can move it behind encrypted admin CRUD without changing the runtime or tool contract.

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

Use an allowlist for every production MCP server. Do not commit tokens in this JSON; inject them with container/Kubernetes secrets. MCP discovery failure does not take Chat down: the runtime logs the failure and continues with the available tools.

## Local REST integrations

REST tools block loopback, link-local and private targets by default to reduce SSRF risk. For trusted services on the same Docker network, enable private targets explicitly:

```bash
export ALLOW_PRIVATE_INTEGRATION_ENDPOINTS=true
```

Do not enable this flag for an environment where untrusted users can create integrations.

## Current migration boundary

- RAG is called on demand and reuses the existing Azure AI Search implementation, embedding configuration and permission filter.
- Existing REST bindings become real model tools; LangGraph no longer relies on the frontend `[y/n]` parsing workflow.
- Bound MongoDB data is queried on demand instead of being added to every prompt.
- MCP tools are discovered with the official Python SDK and namespaced per server.
- The sub-agent adapter includes recursion-depth protection; persistence and the binding UI are intentionally a later slice.
- Chat response and citation shapes remain compatible with the current frontend.

Recommended next slices are: encrypted MCP admin management and agent binding UI; persisted LangGraph checkpoints; sub-agent binding UI plus token/time budgets; then an open-source vector-store adapter behind the same RAG tool.
