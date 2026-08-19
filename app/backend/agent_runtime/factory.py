import logging
import os
from typing import Any

from agent_runtime.adapters import (
    register_chart_tool,
    register_database_tools,
    register_external_api_tools,
    register_mcp_tools,
    register_rag_tool,
)
from agent_runtime.adapters.mcp import load_mcp_servers
from agent_runtime.runtime import AgentRuntime, AgentRuntimeConfig
from agent_runtime.tools import ToolRegistry, ToolRuntimeContext
from approaches.approach import Approach
from mongo_table_connecters.agent_bindings import get_all_agent_bindings_by_agent_id
from mongo_table_connecters.agents import get_agent_by_id
from mongo_table_connecters.chart_binding import get_enabled_chart_bindings_by_agent_id


async def create_agent_runtime(
    *,
    agent_id: str,
    team_id: str | None,
    auth_claims: dict[str, Any],
    approach: Approach,
    overrides: dict[str, Any],
    system_prompt: str,
) -> AgentRuntime:
    agent = get_agent_by_id(agent_id) or {}
    tool_settings = (agent.get("config") or {}).get("tool_settings") or {}
    knowledge_search_mode = str(tool_settings.get("knowledge_search") or "auto").lower()
    registry = ToolRegistry(
        ToolRuntimeContext(agent_id=agent_id, team_id=team_id, auth_claims=auth_claims)
    )
    if knowledge_search_mode != "disabled":
        register_rag_tool(registry, approach, overrides)
    if tool_settings.get("external_database", True) is not False:
        register_database_tools(registry, agent_id)
    if tool_settings.get("rest_integrations", True) is not False:
        register_external_api_tools(
            registry, get_all_agent_bindings_by_agent_id(agent_id)
        )
    if tool_settings.get("mcp", True) is not False:
        try:
            await register_mcp_tools(
                registry, load_mcp_servers(os.getenv("MCP_SERVERS_JSON", ""))
            )
        except Exception:
            logging.exception(
                "MCP tool discovery failed; continuing with available tools"
            )
    chart_bindings = get_enabled_chart_bindings_by_agent_id(agent_id)
    chart_binding = chart_bindings[0] if chart_bindings else None
    chart_tool_enabled = bool(
        chart_binding and register_chart_tool(registry, chart_binding)
    )

    async def completion_factory(messages, tools):
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
        )

    if knowledge_search_mode == "disabled":
        runtime_contract = """You are a helpful AI agent with access to the enabled tools.
Knowledge Search is disabled for this agent. Do not claim to have searched uploaded documents or company knowledge.
Use integration, database, MCP, or sub-agent tools when relevant. If a tool returns no result or an error, explain that clearly instead of inventing information."""
    else:
        runtime_contract = AgentRuntimeConfig.system_prompt
    effective_system_prompt = runtime_contract
    if system_prompt.strip():
        effective_system_prompt = f"Agent-specific instructions:\n{system_prompt.strip()}\n\nRuntime tool rules:\n{runtime_contract}"
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
        ),
    )
