import logging
import os
import uuid
from typing import Any

from agent_runtime.adapters import (
    MCPServerConfig,
    SubagentSpec,
    register_chart_tool,
    register_database_tools,
    register_external_api_tools,
    register_mcp_tools,
    register_mail_tools,
    register_messaging_tools,
    register_rag_tool,
    register_subagent_tools,
)
from agent_runtime.adapters.mcp import load_mcp_servers
from agent_runtime.observability import AuditTrail
from agent_runtime.policy import ToolExecutionPolicy
from agent_runtime.runtime import AgentRuntime, AgentRuntimeConfig
from agent_runtime.tools import ToolRegistry, ToolRuntimeContext
from approaches.approach import Approach
from core.attachment_retrieval import ATTACHMENT_SECURITY_INSTRUCTION, REQUIREMENTS_EVIDENCE_MATRIX_INSTRUCTION
from mongo_table_connecters.agent_bindings import get_all_agent_bindings_by_agent_id
from mongo_table_connecters.agents import get_agent_by_id
from mongo_table_connecters.chart_binding import get_enabled_chart_bindings_by_agent_id
from mongo_table_connecters.mcp_servers import (
    decrypt_mcp_headers,
    get_mcp_server,
)
from mongo_table_connecters.teams import get_team_by_id


def _effective_mcp_allowed_tools(
    admin_allowed: tuple[str, ...], agent_allowed: tuple[str, ...]
) -> tuple[str, ...] | None:
    """Intersect restrictions; None means the agent is not allowed any server tool."""
    if admin_allowed and agent_allowed:
        admin_allowed_set = set(admin_allowed)
        overlap = tuple(tool for tool in agent_allowed if tool in admin_allowed_set)
        return overlap or None
    return agent_allowed or admin_allowed


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
    if tool_settings.get("external_database", True) is not False:
        register_database_tools(registry, agent_id)
    if tool_settings.get("rest_integrations", True) is not False:
        register_external_api_tools(
            registry, get_all_agent_bindings_by_agent_id(agent_id)
        )
    if tool_settings.get("mail", True) is not False:
        register_mail_tools(registry, agent_id)
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
                        headers=decrypt_mcp_headers(document),
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
            if not child:
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
            if not child:
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

    return AgentRuntime(
        completion_factory,
        registry,
        AgentRuntimeConfig(
            system_prompt=effective_system_prompt,
            knowledge_search_mode=knowledge_search_mode,
            mcp_execution_mode=str(
                tool_settings.get("mcp_execution") or "auto"
            ).lower(),
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
