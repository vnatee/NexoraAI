import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import ConfigDict, Field, create_model

from agent_runtime.observability import AuditTrail
from agent_runtime.policy import ToolExecutionPolicy, ToolPolicyViolation
from core.guardrails import GuardrailPolicy, evaluate_output, sanitize_untrusted_context

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
    risk_level: str = "read"


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

    def __init__(
        self,
        context: ToolRuntimeContext,
        *,
        policy: ToolExecutionPolicy | None = None,
        audit: AuditTrail | None = None,
        guardrail_policy: GuardrailPolicy | None = None,
    ):
        self.context = context
        self.policy = policy or ToolExecutionPolicy()
        self.audit = audit
        self.guardrail_policy = guardrail_policy
        self._tools: dict[str, ToolSpec] = {}
        self.execution_log: list[dict[str, Any]] = []
        self._total_calls = 0
        self._calls_by_tool: dict[str, int] = {}

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
            risk_level=spec.risk_level,
        )
        return name

    def specs(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def has(self, name: str) -> bool:
        return self.normalize_name(name) in self._tools

    def openai_tools(self, *, source_prefix: str | None = None) -> list[dict[str, Any]]:
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
            if source_prefix is None
            or spec.source == source_prefix
            or spec.source.startswith(f"{source_prefix}:")
        ]

    def query_mentions_source(self, source_prefix: str, query: str) -> bool:
        normalized_query = query.casefold()
        if source_prefix.casefold() in normalized_query:
            return True
        for spec in self.specs():
            if not (
                spec.source == source_prefix
                or spec.source.startswith(f"{source_prefix}:")
            ):
                continue
            alias = spec.source.rsplit(":", 1)[-1].strip().casefold()
            if len(alias) >= 3 and alias in normalized_query:
                return True
        return False

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
        normalized_name = self.normalize_name(name)
        spec = self._tools.get(normalized_name)
        if spec is None:
            rendered = json.dumps(
                {"error": f"Unknown tool '{name}'"}, ensure_ascii=False
            )
            if self.audit:
                await self.audit.emit(
                    "tool_execution",
                    status="unknown_tool",
                    tool_name=normalized_name,
                    details={"argument_keys": sorted(arguments)},
                )
            return rendered
        started = time.perf_counter()
        argument_size = 0
        try:
            argument_size = self.policy.validate(
                tool_name=spec.name,
                source=spec.source,
                arguments=arguments,
                total_calls=self._total_calls,
                tool_calls=self._calls_by_tool.get(spec.name, 0),
            )
            self._total_calls += 1
            self._calls_by_tool[spec.name] = self._calls_by_tool.get(spec.name, 0) + 1
            value = await asyncio.wait_for(
                spec.handler(arguments, self.context),
                timeout=min(spec.timeout_seconds, self.policy.max_timeout_seconds),
            )
            rendered = (
                value
                if isinstance(value, str)
                else json.dumps(value, ensure_ascii=False, default=str)
            )
            output_limit = min(spec.max_output_chars, self.policy.max_output_chars)
            if len(rendered) > output_limit:
                rendered = rendered[:output_limit] + "\n[tool output truncated]"
            if self.guardrail_policy and self.guardrail_policy.enabled:
                untrusted_result = sanitize_untrusted_context(rendered, self.guardrail_policy)
                output_result = evaluate_output(untrusted_result.text, self.guardrail_policy)
                guardrail_findings = (*untrusted_result.findings, *output_result.findings)
                if guardrail_findings and self.audit:
                    await self.audit.emit(
                        "guardrail_tool_output_evaluated",
                        status=(
                            "denied"
                            if output_result.blocked
                            else "redacted"
                            if untrusted_result.redacted or output_result.redacted
                            else "warning"
                        ),
                        tool_name=spec.name,
                        source=spec.source,
                        details={
                            "direction": "tool_output",
                            "categories": sorted({item.category for item in guardrail_findings}),
                            "detector_ids": sorted({item.detector_id for item in guardrail_findings}),
                            "finding_count": len(guardrail_findings),
                            "blocked": output_result.blocked,
                            "redacted": untrusted_result.redacted or output_result.redacted,
                        },
                    )
                rendered = (
                    json.dumps(
                        {
                            "error": "Tool output was blocked because it may contain sensitive information",
                            "tool": spec.name,
                            "guardrail_denied": True,
                        },
                        ensure_ascii=False,
                    )
                    if output_result.blocked
                    else output_result.text
                )
            self.execution_log.append(
                {
                    "name": spec.name,
                    "source": spec.source,
                    "output": rendered,
                    "raw_output": value,
                    "is_error": False,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
            if self.audit:
                await self.audit.emit(
                    "tool_execution",
                    tool_name=spec.name,
                    source=spec.source,
                    details={
                        "risk_level": spec.risk_level,
                        "argument_keys": sorted(arguments),
                        "argument_size": argument_size,
                        "output_size": len(rendered),
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                )
            return rendered
        except ToolPolicyViolation as error:
            rendered = json.dumps(
                {"error": str(error), "tool": spec.name, "policy_denied": True},
                ensure_ascii=False,
            )
            self.execution_log.append(
                {
                    "name": spec.name,
                    "source": spec.source,
                    "output": rendered,
                    "is_error": True,
                    "policy_denied": True,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
            if self.audit:
                await self.audit.emit(
                    "tool_execution",
                    status="policy_denied",
                    tool_name=spec.name,
                    source=spec.source,
                    details={
                        "reason": str(error),
                        "argument_keys": sorted(arguments),
                        "argument_size": argument_size,
                    },
                )
            return rendered
        except Exception as error:
            logging.exception("Agent tool %s (%s) failed", spec.name, spec.source)
            rendered = json.dumps(
                {
                    "error": str(error),
                    "error_type": type(error).__name__,
                    "tool": spec.name,
                },
                ensure_ascii=False,
            )
            self.execution_log.append(
                {
                    "name": spec.name,
                    "source": spec.source,
                    "output": rendered,
                    "is_error": True,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
            if self.audit:
                await self.audit.emit(
                    "tool_execution",
                    status="error",
                    tool_name=spec.name,
                    source=spec.source,
                    details={
                        "error_type": type(error).__name__,
                        "error": str(error)[:2000],
                        "argument_keys": sorted(arguments),
                        "argument_size": argument_size,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                )
            return rendered
