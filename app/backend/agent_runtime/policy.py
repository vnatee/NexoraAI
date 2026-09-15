from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class ToolPolicyViolation(ValueError):
    pass


@dataclass(frozen=True)
class ToolExecutionPolicy:
    max_total_calls: int = 24
    max_calls_per_tool: int = 8
    max_argument_chars: int = 20_000
    max_output_chars: int = 100_000
    max_timeout_seconds: float = 90.0
    blocked_tools: tuple[str, ...] = ()
    blocked_sources: tuple[str, ...] = ()

    @classmethod
    def from_config(cls, value: object) -> ToolExecutionPolicy:
        data = value if isinstance(value, dict) else {}
        return cls(
            max_total_calls=max(1, min(int(data.get("max_total_calls") or 24), 100)),
            max_calls_per_tool=max(
                1, min(int(data.get("max_calls_per_tool") or 8), 50)
            ),
            max_argument_chars=max(
                1_000, min(int(data.get("max_argument_chars") or 20_000), 200_000)
            ),
            max_output_chars=max(
                1_000, min(int(data.get("max_output_chars") or 100_000), 1_000_000)
            ),
            max_timeout_seconds=max(
                1.0, min(float(data.get("max_timeout_seconds") or 90.0), 300.0)
            ),
            blocked_tools=_string_tuple(data.get("blocked_tools"), 100),
            blocked_sources=_string_tuple(data.get("blocked_sources"), 50),
        )

    def validate(
        self,
        *,
        tool_name: str,
        source: str,
        arguments: dict[str, Any],
        total_calls: int,
        tool_calls: int,
    ) -> int:
        if tool_name in self.blocked_tools:
            raise ToolPolicyViolation(f"Tool '{tool_name}' is blocked by agent policy")
        if any(
            source == item or source.startswith(f"{item}:")
            for item in self.blocked_sources
        ):
            raise ToolPolicyViolation(
                f"Tool source '{source}' is blocked by agent policy"
            )
        if total_calls >= self.max_total_calls:
            raise ToolPolicyViolation(
                f"Agent tool call limit ({self.max_total_calls}) has been reached"
            )
        if tool_calls >= self.max_calls_per_tool:
            raise ToolPolicyViolation(
                f"Per-tool call limit ({self.max_calls_per_tool}) has been reached for '{tool_name}'"
            )
        argument_size = len(
            json.dumps(
                arguments, ensure_ascii=False, default=str, separators=(",", ":")
            )
        )
        if argument_size > self.max_argument_chars:
            raise ToolPolicyViolation(
                f"Tool arguments exceed the {self.max_argument_chars}-character policy limit"
            )
        return argument_size


def normalize_tool_policy(value: object) -> dict[str, Any]:
    policy = ToolExecutionPolicy.from_config(value)
    return {
        "max_total_calls": policy.max_total_calls,
        "max_calls_per_tool": policy.max_calls_per_tool,
        "max_argument_chars": policy.max_argument_chars,
        "max_output_chars": policy.max_output_chars,
        "max_timeout_seconds": policy.max_timeout_seconds,
        "blocked_tools": list(policy.blocked_tools),
        "blocked_sources": list(policy.blocked_sources),
    }


def _string_tuple(value: object, maximum: int) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("Tool policy block lists must be arrays")
    result = []
    for item in value[:maximum]:
        normalized = str(item or "").strip().lower()
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)
