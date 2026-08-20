import json
import logging
import re
from builtins import BaseExceptionGroup
from dataclasses import dataclass, field
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from agent_runtime.adapters.external_api import _validate_target
from agent_runtime.tools import ToolRegistry, ToolSpec


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    url: str
    server_id: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    allowed_tools: tuple[str, ...] = ()
    timeout_seconds: float = 60.0


class MCPToolExecutionError(RuntimeError):
    """Actionable remote MCP failure safe to return to the agent model."""


def _tool_description(server: MCPServerConfig, remote_tool: Any) -> str:
    description = (
        remote_tool.description or f"Call MCP tool {remote_tool.name} on {server.name}"
    )
    if "datadog" not in server.name.casefold():
        return description
    reliability_rule = (
        " Use only arguments declared in this tool's input schema. Do not claim pagination, truncation, "
        "or a result limit unless the returned payload explicitly reports it."
    )
    guidance = {
        "search_datadog_monitors": (
            " This tool retrieves monitor definitions and their current statuses. It does not retrieve "
            "historical alert occurrences. For alerts over a past time range, call search_datadog_events. "
            "A grouped monitor is one monitor definition even when several groups are alerting; use "
            "search_datadog_monitor_groups for group-level alert status when that tool is enabled."
        ),
        "search_datadog_events": (
            " Use this tool for historical monitor alert occurrences, deployments, and other events over "
            "a requested time range."
        ),
        "search_datadog_logs": (
            " Use this tool to retrieve individual logs and inspect the actual attributes returned by "
            "Datadog. When the available log fields are unknown, call this tool before "
            "analyze_datadog_logs and build any later analysis only from fields confirmed by the result."
        ),
        "analyze_datadog_logs": (
            " Use this tool for log statistics and aggregations, after the queryable fields are known. "
            "Datadog log attributes are dataset-dependent: do not assume that names such as source, "
            "service, host, or status are directly queryable SQL columns. If field availability is "
            "unknown, call search_datadog_logs first. If Datadog reports that a column cannot be "
            "resolved, do not repeat the same query; discover the actual fields with "
            "search_datadog_logs, then rebuild the analysis using only confirmed fields."
        ),
    }.get(remote_tool.name, "")
    return f"{description}{guidance}{reliability_rule}"


def _augment_tool_error(server: MCPServerConfig, tool_name: str, message: str) -> str:
    """Add recovery guidance to known remote errors without hiding their cause."""
    if "datadog" not in server.name.casefold() or tool_name != "analyze_datadog_logs":
        return message
    unresolved = re.search(
        r"Column\s+['\"](?P<column>[^'\"]+)['\"]\s+cannot be resolved",
        message,
        flags=re.IGNORECASE,
    )
    if not unresolved:
        return message
    column = unresolved.group("column")
    return (
        f"{message}\nRecovery: '{column}' is not a queryable column for this log dataset. "
        "Do not retry the same advanced query. Call search_datadog_logs for the same time range "
        "to inspect real returned attributes, then retry analyze_datadog_logs using only fields "
        "confirmed by that result. If no suitable field is confirmed, return the searched logs "
        "without inventing an aggregation."
    )


def _render_content_blocks(result: Any) -> list[Any]:
    rendered = []
    for block in getattr(result, "content", []):
        if hasattr(block, "text"):
            rendered.append(block.text)
        elif hasattr(block, "model_dump"):
            rendered.append(block.model_dump(mode="json", by_alias=True))
        else:
            rendered.append(str(block))
    return rendered


def _error_message(result: Any) -> str:
    rendered = _render_content_blocks(result)
    parts = [
        item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        for item in rendered
    ]
    return (
        "\n".join(part.strip() for part in parts if part and part.strip())
        or "Remote MCP tool returned an unspecified error"
    )


def _render_result(result: Any) -> Any:
    if bool(getattr(result, "is_error", False)):
        raise MCPToolExecutionError(_error_message(result))
    if getattr(result, "structured_content", None) is not None:
        return result.structured_content
    return {"is_error": False, "content": _render_content_blocks(result)}


def _root_mcp_error(error: Exception) -> Exception:
    if isinstance(error, BaseExceptionGroup):
        leaves = [
            _root_mcp_error(item)
            for item in error.exceptions
            if isinstance(item, Exception)
        ]
        return next(
            (item for item in leaves if isinstance(item, MCPToolExecutionError)),
            leaves[0] if leaves else error,
        )
    return error


async def register_mcp_tools(
    registry: ToolRegistry, servers: list[MCPServerConfig]
) -> None:
    for server in servers:
        try:
            discovered = await discover_mcp_tools(server)
        except Exception as error:
            logging.exception("MCP discovery failed for server %s", server.name)
            if registry.audit:
                await registry.audit.emit(
                    "mcp_discovery",
                    status="error",
                    source=f"mcp:{server.server_id or server.name}:{server.name}",
                    details={
                        "server_name": server.name,
                        "error_type": type(error).__name__,
                        "error": str(error)[:2000],
                    },
                )
            continue
        for remote_tool in discovered:
            if server.allowed_tools and remote_tool.name not in server.allowed_tools:
                continue

            async def call_mcp(
                arguments, context, _server=server, _name=remote_tool.name
            ):
                try:
                    await _validate_target(_server.url)
                    async with httpx2.AsyncClient(
                        headers=_server.headers, follow_redirects=True
                    ) as http_client:
                        transport = streamable_http_client(
                            _server.url, http_client=http_client
                        )
                        async with Client(
                            transport, read_timeout_seconds=_server.timeout_seconds
                        ) as client:
                            return _render_result(
                                await client.call_tool(_name, arguments)
                            )
                except Exception as error:
                    root = _root_mcp_error(error)
                    message = str(root).strip() or type(root).__name__
                    message = _augment_tool_error(_server, _name, message)
                    raise MCPToolExecutionError(message) from None

            registry.register(
                ToolSpec(
                    name=f"mcp_{server.name}_{remote_tool.name}",
                    description=_tool_description(server, remote_tool),
                    input_schema=remote_tool.input_schema,
                    handler=call_mcp,
                    source=f"mcp:{server.server_id or server.name}",
                    timeout_seconds=server.timeout_seconds,
                    risk_level="external",
                )
            )


async def discover_mcp_tools(server: MCPServerConfig) -> list[Any]:
    await _validate_target(server.url)
    async with httpx2.AsyncClient(
        headers=server.headers, follow_redirects=True
    ) as http_client:
        transport = streamable_http_client(server.url, http_client=http_client)
        async with Client(
            transport, read_timeout_seconds=server.timeout_seconds
        ) as client:
            discovered = await client.list_tools()
    return list(discovered.tools)


def load_mcp_servers(raw_json: str) -> list[MCPServerConfig]:
    if not raw_json.strip():
        return []
    data = json.loads(raw_json)
    if not isinstance(data, list):
        raise ValueError("MCP_SERVERS_JSON must be a JSON array")
    return [
        MCPServerConfig(
            server_id=str(item.get("id") or "") or None,
            name=str(item["name"]),
            url=str(item["url"]),
            headers={
                str(key): str(value)
                for key, value in (item.get("headers") or {}).items()
            },
            allowed_tools=tuple(item.get("allowed_tools") or ()),
            timeout_seconds=float(item.get("timeout_seconds") or 60),
        )
        for item in data
        if item.get("enabled", True)
    ]
