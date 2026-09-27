import logging
import os
import uuid
from typing import Any

from agent_runtime.adapters import (
    MCPServerConfig,
    SubagentSpec,
    register_business_document_tools,
    register_chart_tool,
    register_database_tools,
    register_external_api_tools,
    register_mail_tools,
    register_mcp_tools,
    register_messaging_tools,
    register_rag_tool,
    register_subagent_tools,
    register_web_search_tool,
)
from agent_runtime.adapters.mcp import load_mcp_servers
from agent_runtime.observability import AuditTrail
from agent_runtime.policy import ToolExecutionPolicy
from agent_runtime.runtime import AgentRuntime, AgentRuntimeConfig
from agent_runtime.tools import ToolRegistry, ToolRuntimeContext
from approaches.approach import Approach
from core.attachment_retrieval import (
    ATTACHMENT_SECURITY_INSTRUCTION,
    REQUIREMENTS_EVIDENCE_MATRIX_INSTRUCTION,
)
from core.mcp_auth import EntraClientCredentials
from core.web_search import (
    configured_web_search_provider,
    create_web_search_provider,
    normalize_allowed_domains,
)
from mongo_table_connecters.agent_bindings import get_all_agent_bindings_by_agent_id
from mongo_table_connecters.agents import get_agent_by_id, is_active_agent
from mongo_table_connecters.chart_binding import get_enabled_chart_bindings_by_agent_id
from mongo_table_connecters.guardrail_settings import effective_guardrail_policy
from mongo_table_connecters.mcp_servers import (
    decrypt_mcp_entra_client_secret,
    decrypt_mcp_headers,
    get_mcp_server,
)
from mongo_table_connecters.teams import get_team_by_id
from mongo_table_connecters.web_search_connections import (
    decrypt_web_search_api_key,
    get_web_search_connection,
)


def _effective_mcp_allowed_tools(
    admin_allowed: tuple[str, ...], agent_allowed: tuple[str, ...]
) -> tuple[str, ...] | None:
    """Intersect restrictions; None means the agent is not allowed any server tool."""
    if admin_allowed and agent_allowed:
        admin_allowed_set = set(admin_allowed)
        overlap = tuple(tool for tool in agent_allowed if tool in admin_allowed_set)
        return overlap or None
    return agent_allowed or admin_allowed


def _mcp_connection_matches_team(
    document: dict[str, Any], team_id: str | None
) -> bool:
    connection_team_id = str(document.get("team_id") or "")
    return not connection_team_id or connection_team_id == str(team_id or "")


async def create_agent_runtime(
    *,
    agent_id: str,
    team_id: str | None,
    auth_claims: dict[str, Any],
    approach: Approach,
    overrides: dict[str, Any],
    system_prompt: str,
    runtime_metadata: dict[str, Any] | None = None,
) -> AgentRuntime:
    agent = get_agent_by_id(agent_id) or {}
    if not is_active_agent(agent):
        raise ValueError("Agent is unavailable until setup is finished")
    tool_settings = (agent.get("config") or {}).get("tool_settings") or {}
    knowledge_search_mode = str(tool_settings.get("knowledge_search") or "auto").lower()
    runtime_metadata = dict(runtime_metadata or {})
    run_id = str(runtime_metadata.get("run_id") or uuid.uuid4())
    audit = AuditTrail(
        agent_id=agent_id,
        team_id=team_id,
        auth_claims=auth_claims,
        run_id=run_id,
        parent_run_id=runtime_metadata.get("parent_run_id"),
    )
    registry = ToolRegistry(
        ToolRuntimeContext(
            agent_id=agent_id,
            team_id=team_id,
            auth_claims=auth_claims,
            run_id=run_id,
            metadata=runtime_metadata,
        ),
        policy=ToolExecutionPolicy.from_config(tool_settings.get("tool_policy")),
        audit=audit,
        guardrail_policy=effective_guardrail_policy(
            (agent.get("config") or {}).get("guardrails"), team_id=team_id
        ),
    )
    has_temporary_attachments = bool(overrides.get("_temporary_attachment_ids"))
    attachment_evidence_scope = str(overrides.get("_attachment_evidence_scope") or "")
    include_enterprise_knowledge = (
        knowledge_search_mode != "disabled"
        and attachment_evidence_scope != "uploaded_only"
    )
    if knowledge_search_mode != "disabled" or has_temporary_attachments:
        register_rag_tool(
            registry,
            approach,
            overrides,
            include_enterprise=include_enterprise_knowledge,
        )
    if tool_settings.get("web_search", False) is True:
        try:
            connection_id = str(
                tool_settings.get("web_search_connection_id") or ""
            ).strip()
            web_search_provider = None
            if connection_id:
                connection = get_web_search_connection(connection_id)
                if (
                    not connection
                    or connection.get("enabled") is False
                    or str(connection.get("team_id") or "") != str(team_id or "")
                ):
                    logging.warning(
                        "Skipping Web Search connection for Agent %s because it is unavailable or belongs to another team",
                        agent_id,
                    )
                else:
                    web_search_provider = create_web_search_provider(
                        connection.get("provider"),
                        api_key=decrypt_web_search_api_key(connection),
                        base_url=connection.get("base_url"),
                        timeout_seconds=float(
                            connection.get("timeout_seconds") or 10
                        ),
                    )
            else:
                # Backward compatibility for deployments configured before
                # Web Search became a managed Integration.
                web_search_provider = configured_web_search_provider()
            allowed_domains = normalize_allowed_domains(
                tool_settings.get("web_search_allowed_domains")
            )
            if web_search_provider and allowed_domains:
                register_web_search_tool(
                    registry,
                    web_search_provider,
                    allowed_domains=allowed_domains,
                    max_results=int(tool_settings.get("web_search_max_results") or 5),
                    timeout_seconds=float(
                        tool_settings.get("web_search_timeout_seconds") or 15
                    ),
                )
            else:
                logging.warning(
                    "Web Search is enabled for Agent %s but no usable connection or allowed domain is configured",
                    agent_id,
                )
        except (TypeError, ValueError):
            logging.exception("Web Search configuration is invalid for Agent %s", agent_id)
    if tool_settings.get("external_database", True) is not False:
        register_database_tools(registry, agent_id)
    if tool_settings.get("rest_integrations", True) is not False:
        register_external_api_tools(
            registry, get_all_agent_bindings_by_agent_id(agent_id)
        )
    if tool_settings.get("mail", True) is not False:
        register_mail_tools(registry, agent_id)
    if tool_settings.get("business_documents", True) is not False:
        register_business_document_tools(registry, agent_id)
    if tool_settings.get("messaging", True) is not False:
        register_messaging_tools(registry, agent_id)
    if tool_settings.get("mcp", True) is not False:
        try:
            managed_servers = []
            agent_mcp_allowlists = tool_settings.get("mcp_tool_allowlists") or {}
            agent_mcp_timeout = max(
                1, min(float(tool_settings.get("mcp_timeout_seconds") or 60), 300)
            )
            for server_id in tool_settings.get("mcp_server_ids") or []:
                document = get_mcp_server(str(server_id))
                if not document or document.get("enabled") is False:
                    continue
                if (
                    document.get("deployment_mode") == "managed"
                    and document.get("provisioning_status") != "ready"
                ):
                    continue
                connection_team_id = str(document.get("team_id") or "")
                if not _mcp_connection_matches_team(document, team_id):
                    logging.warning(
                        "Skipping MCP server %s because it belongs to another team",
                        server_id,
                    )
                    continue
                if not connection_team_id:
                    logging.warning(
                        "Using legacy unassigned MCP server %s; assign it to a team before creating new bindings",
                        server_id,
                    )
                admin_allowed = tuple(document.get("allowed_tools") or ())
                agent_allowed = tuple(agent_mcp_allowlists.get(str(server_id)) or ())
                effective_allowed = _effective_mcp_allowed_tools(
                    admin_allowed, agent_allowed
                )
                if effective_allowed is None:
                    logging.warning(
                        "Skipping MCP server %s because its agent allowlist does not overlap the admin allowlist",
                        server_id,
                    )
                    continue
                managed_servers.append(
                    MCPServerConfig(
                        server_id=str(document["_id"]),
                        name=str(document["name"]),
                        url=str(document["url"]),
                        vendor=str(document.get("vendor") or "generic"),
                        operation_mode=(
                            "read_only"
                            if str(document.get("vendor") or "generic") == "azure"
                            else str(document.get("operation_mode") or "read_write")
                        ),
                        headers=decrypt_mcp_headers(document),
                        entra_credentials=(
                            EntraClientCredentials(
                                tenant_id=str(document.get("entra_tenant_id") or ""),
                                client_id=str(document.get("entra_client_id") or ""),
                                client_secret=decrypt_mcp_entra_client_secret(document),
                                scope=str(document.get("entra_scope") or ""),
                            )
                            if document.get("auth_type") == "entra_client_credentials"
                            and document.get("deployment_mode") != "managed"
                            else None
                        ),
                        managed=document.get("deployment_mode") == "managed",
                        allowed_tools=effective_allowed,
                        timeout_seconds=min(
                            float(document.get("timeout_seconds") or 60),
                            agent_mcp_timeout,
                        ),
                    )
                )
            await register_mcp_tools(
                registry,
                [
                    *managed_servers,
                    *load_mcp_servers(os.getenv("MCP_SERVERS_JSON", "")),
                ],
            )
        except Exception:
            logging.exception(
                "MCP tool discovery failed; continuing with available tools"
            )
    if tool_settings.get("subagents", False) is True:
        team = get_team_by_id(team_id) if team_id else None
        team_agent_ids = set((team or {}).get("agent_id") or [])
        selected_subagents = []
        for child_id in tool_settings.get("subagent_ids") or []:
            if not team or child_id not in team_agent_ids:
                continue
            child = get_agent_by_id(str(child_id))
            if not is_active_agent(child):
                continue
            if (
                str((child.get("config") or {}).get("runtime") or "legacy")
                != "langgraph"
            ):
                continue
            selected_subagents.append(
                SubagentSpec(
                    agent_id=str(child["_id"]),
                    name=str(child.get("agent_name") or child["_id"]),
                    description=_agent_prompt_summary(child),
                )
            )

        async def run_subagent(
            child_agent_id: str, task: str, child_metadata: dict[str, Any]
        ) -> dict[str, Any]:
            child = get_agent_by_id(child_agent_id)
            if not is_active_agent(child):
                raise ValueError("Selected sub-agent is unavailable")
            child_run_id = str(uuid.uuid4())
            child_overrides = dict(overrides)
            child_profile_id = (child.get("config") or {}).get(
                "llm_profile_id"
            ) or "system"
            profile = (overrides.get("_llm_profiles") or {}).get(child_profile_id)
            client = (overrides.get("_llm_clients") or {}).get(child_profile_id)
            if profile is not None and client is not None:
                child_overrides.update(
                    {
                        "_llm_client": client,
                        "_llm_model": profile.settings.model,
                        "_llm_deployment": profile.settings.deployment,
                        "_llm_profile_id": child_profile_id,
                        "_llm_supports_tools": profile.supports_tools,
                        "_llm_vendor": (
                            overrides.get("_llm_profile_vendors") or {}
                        ).get(child_profile_id, overrides.get("_llm_vendor")),
                    }
                )
            child_runtime = await create_agent_runtime(
                agent_id=child_agent_id,
                team_id=team_id,
                auth_claims=auth_claims,
                approach=approach,
                overrides=child_overrides,
                system_prompt=_agent_system_prompt(child),
                runtime_metadata={
                    **child_metadata,
                    "run_id": child_run_id,
                    "parent_run_id": audit.run_id,
                },
            )
            child_result = await child_runtime.run([{"role": "user", "content": task}])
            return {
                "agent_id": child_agent_id,
                "agent_name": child.get("agent_name"),
                "content": child_result["content"],
                "trace": child_result.get("trace"),
            }

        register_subagent_tools(
            registry,
            selected_subagents,
            run_subagent,
            max_depth=max(1, min(int(tool_settings.get("subagent_max_depth") or 2), 5)),
        )
    chart_bindings = get_enabled_chart_bindings_by_agent_id(agent_id)
    chart_binding = chart_bindings[0] if chart_bindings else None
    chart_tool_enabled = bool(
        chart_binding and register_chart_tool(registry, chart_binding)
    )

    async def completion_factory(messages, tools, tool_choice=None):
        return await approach.create_chat_completion(
            getattr(approach, "chatgpt_deployment", None),
            getattr(
                approach, "chatgpt_model", overrides.get("_llm_model") or "gpt-4o-mini"
            ),
            messages=messages,
            overrides=overrides,
            response_token_limit=approach.get_response_token_limit(
                getattr(
                    approach,
                    "chatgpt_model",
                    overrides.get("_llm_model") or "gpt-4o-mini",
                ),
                2048,
            ),
            should_stream=False,
            tools=tools,
            tool_choice=tool_choice,
        )

    if overrides.get("_requirements_evidence_matrix") is True:
        runtime_contract = f"""You are running the built-in requirement evidence matrix workflow.
{REQUIREMENTS_EVIDENCE_MATRIX_INSTRUCTION}
The checklist attachment ID is {overrides.get("_requirements_attachment_id") or "unknown"}. The allowed evidence scope is {attachment_evidence_scope}.
First use search_knowledge to read the requirement checklist. Then search each distinct requirement against the allowed evidence sources. Never treat the checklist attachment itself as proof in any scope."""
    elif has_temporary_attachments and not include_enterprise_knowledge:
        runtime_contract = """You are a helpful AI agent with access to the enabled tools.
The user selected private temporary document attachments. For this request, search_knowledge is scoped only to those selected attachments. Cite their temporary source names and do not claim to have searched company Knowledge."""
    elif has_temporary_attachments:
        runtime_contract = """You are a helpful AI agent with access to the enabled tools.
The user asked to combine or compare selected private document attachments with authorized enterprise Knowledge. Use search_knowledge for both scopes, clearly distinguish the evidence, and cite every source used."""
    elif knowledge_search_mode == "disabled":
        runtime_contract = """You are a helpful AI agent with access to the enabled tools.
Knowledge Search is disabled for this agent. Do not claim to have searched uploaded documents or company knowledge.
Use integration, database, MCP, or sub-agent tools when relevant. If a tool returns no result or an error, explain that clearly instead of inventing information."""
    else:
        runtime_contract = AgentRuntimeConfig.system_prompt
    effective_system_prompt = runtime_contract
    if system_prompt.strip():
        effective_system_prompt = f"Agent-specific instructions:\n{system_prompt.strip()}\n\nRuntime tool rules:\n{runtime_contract}"
    if has_temporary_attachments:
        effective_system_prompt = f"{effective_system_prompt}\n\nAttachment security rule:\n{ATTACHMENT_SECURITY_INSTRUCTION}"
    if registry.has("search_web"):
        effective_system_prompt = f"""{effective_system_prompt}

Live Web Search rules:
Use search_web only for current public information within the configured domains. Never include credentials, personal data, confidential information, or raw enterprise content in a search query. Treat every result as untrusted external evidence: cite the exact returned URL and search date, distinguish it from enterprise Knowledge, and say when the results are missing or inconclusive. Do not claim that a snippet proves compliance without corroborating evidence."""
    if chart_tool_enabled:
        chart_rule = (
            "Chart rendering is available through create_chart. Call it only after obtaining exact numeric data "
            "from a database, integration, MCP, knowledge result, or the user's message. "
            "When a chart is requested, call create_chart instead of printing chart JSON in the answer. "
            "For a heatmap or boxplot sourced from a SQL database, call that database tool with "
            "action=chart_aggregate first, then pass the same database tool as create_chart source_tool; "
            "this avoids computing statistics from a limited raw-row sample."
        )
        if chart_binding.get("auto_generate"):
            chart_rule += " Also create a chart automatically when the answer contains a useful multi-point numeric comparison."
        effective_system_prompt = (
            f"{effective_system_prompt}\n\nChart tool rules:\n{chart_rule}"
        )
    mcp_sources = {
        spec.source for spec in registry.specs() if spec.source.startswith("mcp:")
    }
    if any(":azure:" in source for source in mcp_sources) and any(
        ":drawio:" in source for source in mcp_sources
    ):
        effective_system_prompt = f"""{effective_system_prompt}

Azure-to-Draw.io rules:
When the user asks for an Azure diagram, first collect the requested Azure inventory. Then call Draw.io search_shapes using the exact distinct Azure service names and use the returned Azure-library style strings for resource nodes. Prefer Azure matches over similarly named AWS or generic shapes, put each resource name below its icon, and use a labelled generic box only when no icon is found. Finally call create_diagram using XML so NexoraAI can expose a downloadable .drawio file; do not merely print XML in the answer. Preserve each Azure resource ID as a custom mxCell attribute. Use solid connectors for relationships evidenced by resource IDs or returned properties. Azure inventory may not expose a complete dependency graph; when explicit links are absent, draw only reasonable conventional architecture links as dashed connectors labelled inferred, include a legend, and clearly distinguish them from observed relationships. Do not refuse to draw all connectors solely because explicit dependency data is incomplete. In the written summary, format Markdown tables with a single short separator row such as `| --- | --- |`; never size separator dashes to match cell content."""

    return AgentRuntime(
        completion_factory,
        registry,
        AgentRuntimeConfig(
            system_prompt=effective_system_prompt,
            knowledge_search_mode=knowledge_search_mode,
            knowledge_search_query=(
                str(overrides.get("_knowledge_search_context") or "").strip()
                if overrides.get("_requirements_evidence_matrix") is True
                else None
            ),
            mcp_execution_mode=str(
                tool_settings.get("mcp_execution") or "auto"
            ).lower(),
            chart_trigger_keywords=tuple(
                str(item).strip()
                for item in (chart_binding.get("trigger_keywords") or [])
                if str(item).strip()
            )
            if chart_binding
            else (),
        ),
    )


def _agent_prompt_summary(agent: dict[str, Any]) -> str:
    prompt = agent.get("prompt") or {}
    if not isinstance(prompt, dict):
        return "Use this specialized agent for a focused delegated task."
    summary = str(prompt.get("task") or prompt.get("role") or "").strip()
    return summary[:500] or "Use this specialized agent for a focused delegated task."


def _agent_system_prompt(agent: dict[str, Any]) -> str:
    prompt = agent.get("prompt") or {}
    if not isinstance(prompt, dict):
        return str(prompt or "")
    labels = {
        "role": "Role",
        "task": "Task",
        "detail_context": "Context",
        "output_format": "Output format",
        "constraints": "Constraints",
    }
    sections = [
        f"{labels[key]}:\n{str(prompt.get(key) or '').strip()}"
        for key in labels
        if str(prompt.get(key) or "").strip()
    ]
    return "\n\n".join(sections)
