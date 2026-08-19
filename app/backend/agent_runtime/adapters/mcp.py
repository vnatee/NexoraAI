import json
from dataclasses import dataclass, field
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from agent_runtime.tools import ToolRegistry, ToolSpec


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    allowed_tools: tuple[str, ...] = ()
    timeout_seconds: float = 60.0


def _render_result(result: Any) -> Any:
    if getattr(result, "structured_content", None) is not None:
        return result.structured_content
    rendered = []
    for block in getattr(result, "content", []):
        if hasattr(block, "text"):
            rendered.append(block.text)
        else:
            rendered.append(block.model_dump(mode="json", by_alias=True))
    return {"is_error": bool(getattr(result, "is_error", False)), "content": rendered}


async def register_mcp_tools(registry: ToolRegistry, servers: list[MCPServerConfig]) -> None:
    for server in servers:
        async with httpx2.AsyncClient(headers=server.headers, follow_redirects=True) as http_client:
            transport = streamable_http_client(server.url, http_client=http_client)
            async with Client(transport, read_timeout_seconds=server.timeout_seconds) as client:
                discovered = await client.list_tools()
        for remote_tool in discovered.tools:
            if server.allowed_tools and remote_tool.name not in server.allowed_tools:
                continue

            async def call_mcp(arguments, context, _server=server, _name=remote_tool.name):
                async with httpx2.AsyncClient(headers=_server.headers, follow_redirects=True) as http_client:
                    transport = streamable_http_client(_server.url, http_client=http_client)
                    async with Client(transport, read_timeout_seconds=_server.timeout_seconds) as client:
                        return _render_result(await client.call_tool(_name, arguments))

            registry.register(
                ToolSpec(
                    name=f"mcp_{server.name}_{remote_tool.name}",
                    description=remote_tool.description or f"Call MCP tool {remote_tool.name} on {server.name}",
                    input_schema=remote_tool.input_schema,
                    handler=call_mcp,
                    source=f"mcp:{server.name}",
                    timeout_seconds=server.timeout_seconds,
                )
            )


def load_mcp_servers(raw_json: str) -> list[MCPServerConfig]:
    if not raw_json.strip():
        return []
    data = json.loads(raw_json)
    if not isinstance(data, list):
        raise ValueError("MCP_SERVERS_JSON must be a JSON array")
    return [
        MCPServerConfig(
            name=str(item["name"]),
            url=str(item["url"]),
            headers={str(key): str(value) for key, value in (item.get("headers") or {}).items()},
            allowed_tools=tuple(item.get("allowed_tools") or ()),
            timeout_seconds=float(item.get("timeout_seconds") or 60),
        )
        for item in data
        if item.get("enabled", True)
    ]
