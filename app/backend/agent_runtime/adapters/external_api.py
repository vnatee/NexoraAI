import ipaddress
import os
import socket
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import aiohttp

from agent_runtime.tools import ToolRegistry, ToolSpec
from mongo_table_connecters.external_apis import get_apis_by_id


async def _validate_target(url: str, *, allow_private: bool = False) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Integration URL must use http or https")
    if allow_private or os.getenv("ALLOW_PRIVATE_INTEGRATION_ENDPOINTS", "").lower() == "true":
        return
    addresses = (
        await __import__("asyncio")
        .get_running_loop()
        .run_in_executor(
            None,
            lambda: socket.getaddrinfo(
                parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM
            ),
        )
    )
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError(
                "Private integration targets are disabled; set ALLOW_PRIVATE_INTEGRATION_ENDPOINTS=true for trusted local services"
            )


def register_external_api_tools(
    registry: ToolRegistry, bindings: list[dict[str, Any]]
) -> None:
    for binding in bindings:
        if binding.get("enabled") is False or binding.get("integration_type") not in (
            None,
            "rest",
            "external_api",
        ):
            continue
        integration = get_apis_by_id(binding.get("integration_id"))
        if not integration:
            continue
        endpoint = next(
            (
                item
                for item in integration.get("endpoints", [])
                if item.get("name") == binding.get("endpoint_name")
            ),
            None,
        )
        if not endpoint:
            continue
        fields = binding.get("request_fields") or []
        properties = {
            field["field"]: {
                "type": "string",
                "description": field.get("description") or field["field"],
            }
            for field in fields
            if field.get("field")
        }

        async def call_api(
            arguments,
            context,
            _integration=integration,
            _endpoint=endpoint,
            _fields=fields,
        ):
            path = str(_endpoint.get("path") or "")
            query: dict[str, Any] = {}
            body: dict[str, Any] = {}
            for field in _fields:
                name = field.get("field")
                if name not in arguments:
                    continue
                location = field.get("location") or "body"
                if location == "path":
                    path = path.replace(
                        "{" + name + "}", quote(str(arguments[name]), safe="")
                    )
                elif location == "query":
                    query[name] = arguments[name]
                else:
                    body[name] = arguments[name]
            url = urljoin(
                str(_integration["base_url"]).rstrip("/") + "/", path.lstrip("/")
            )
            await _validate_target(url)
            headers = {}
            auth = _integration.get("auth") or {}
            if (
                auth.get("type") in ("api_key", "bearer")
                and auth.get("header")
                and auth.get("value")
            ):
                headers[str(auth["header"])] = str(auth["value"])
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    str(_endpoint.get("method") or "GET").upper(),
                    url,
                    params=query,
                    json=body or None,
                    headers=headers,
                ) as response:
                    text = await response.text()
                    if len(text) > 1_000_000:
                        text = text[:1_000_000] + "\n[response truncated]"
                    return {
                        "status": response.status,
                        "content_type": response.content_type,
                        "body": text,
                    }

        tool_name = f"api_{integration.get('name')}_{binding.get('endpoint_name')}_{str(binding.get('_id') or '')[:8]}"
        registry.register(
            ToolSpec(
                name=tool_name,
                description=(
                    f"Call {integration.get('name')} endpoint {binding.get('endpoint_name')}. "
                    + (
                        "Use when intent matches: "
                        + ", ".join(binding.get("trigger_keywords") or [])
                        if binding.get("trigger_keywords")
                        else ""
                    )
                ),
                input_schema={
                    "type": "object",
                    "properties": properties,
                    "required": list(properties),
                    "additionalProperties": False,
                },
                handler=call_api,
                source=f"external_api:{integration.get('_id')}",
                risk_level="external",
            )
        )
