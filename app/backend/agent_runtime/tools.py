import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import ConfigDict, Field, create_model

ToolHandler = Callable[[dict[str, Any], "ToolRuntimeContext"], Awaitable[Any]]


@dataclass(frozen=True)
class ToolRuntimeContext:
    agent_id: str
    auth_claims: dict[str, Any]
    team_id: str | None = None
    run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    source: str = "builtin"
    timeout_seconds: float = 30.0
    max_output_chars: int = 50_000


def _python_type(schema: dict[str, Any]) -> type:
    return {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }.get(str(schema.get("type")), Any)


def _args_model(spec: ToolSpec):
    required = set(spec.input_schema.get("required") or [])
    fields = {}
    for name, schema in (spec.input_schema.get("properties") or {}).items():
        default = ... if name in required else None
        fields[name] = (
            _python_type(schema),
            Field(default=default, description=schema.get("description")),
        )
    return create_model(
        f"{spec.name.title().replace('_', '')}Input",
        __config__=ConfigDict(
            extra="forbid"
            if spec.input_schema.get("additionalProperties") is False
            else "allow"
        ),
        **fields,
    )


class ToolRegistry:
    """Canonical registry used by LangGraph, LangChain and MCP adapters."""

    def __init__(self, context: ToolRuntimeContext):
        self.context = context
        self._tools: dict[str, ToolSpec] = {}
        self.execution_log: list[dict[str, Any]] = []

    @staticmethod
    def normalize_name(name: str) -> str:
        normalized = "".join(
            char if char.isalnum() or char == "_" else "_"
            for char in name.strip().lower()
        )
        normalized = "_".join(part for part in normalized.split("_") if part)
        if not normalized or not normalized[0].isalpha():
            normalized = f"tool_{normalized}"
        return normalized[:64]

    def register(self, spec: ToolSpec) -> str:
        name = self.normalize_name(spec.name)
        if name in self._tools:
            raise ValueError(f"Duplicate tool name '{name}'")
        self._tools[name] = ToolSpec(
            name=name,
            description=spec.description.strip(),
            input_schema=spec.input_schema,
            handler=spec.handler,
            source=spec.source,
            timeout_seconds=spec.timeout_seconds,
            max_output_chars=spec.max_output_chars,
        )
        return name

    def specs(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def has(self, name: str) -> bool:
        return self.normalize_name(name) in self._tools

    def openai_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.input_schema,
                },
            }
            for spec in self.specs()
        ]

    def langchain_tools(self) -> list[StructuredTool]:
        result = []
        for spec in self.specs():

            async def invoke(_spec: ToolSpec = spec, **kwargs: Any) -> str:
                return await self.execute(_spec.name, kwargs)

            result.append(
                StructuredTool.from_function(
                    coroutine=invoke,
                    name=spec.name,
                    description=spec.description,
                    args_schema=_args_model(spec),
                )
            )
        return result

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        spec = self._tools.get(self.normalize_name(name))
        if spec is None:
            return json.dumps({"error": f"Unknown tool '{name}'"}, ensure_ascii=False)
        try:
            value = await asyncio.wait_for(
                spec.handler(arguments, self.context), timeout=spec.timeout_seconds
            )
            rendered = (
                value
                if isinstance(value, str)
                else json.dumps(value, ensure_ascii=False, default=str)
            )
            if len(rendered) > spec.max_output_chars:
                rendered = (
                    rendered[: spec.max_output_chars] + "\n[tool output truncated]"
                )
            self.execution_log.append(
                {
                    "name": spec.name,
                    "source": spec.source,
                    "output": rendered,
                    "raw_output": value,
                    "is_error": False,
                }
            )
            return rendered
        except Exception as error:
            logging.exception("Agent tool %s (%s) failed", spec.name, spec.source)
            rendered = json.dumps(
                {"error": str(error), "tool": spec.name}, ensure_ascii=False
            )
            self.execution_log.append(
                {
                    "name": spec.name,
                    "source": spec.source,
                    "output": rendered,
                    "is_error": True,
                }
            )
            return rendered
