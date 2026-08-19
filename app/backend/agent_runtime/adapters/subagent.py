from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from agent_runtime.tools import ToolRegistry, ToolSpec

SubagentRunner = Callable[[str, str, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class SubagentSpec:
    agent_id: str
    name: str
    description: str


def register_subagent_tools(
    registry: ToolRegistry,
    subagents: list[SubagentSpec],
    runner: SubagentRunner,
    *,
    max_depth: int = 3,
) -> None:
    """Expose selected agents as bounded tools; persistence/binding can be added without changing the graph."""
    current_depth = int(registry.context.metadata.get("subagent_depth") or 0)
    if current_depth >= max_depth:
        return
    for subagent in subagents:
        if subagent.agent_id == registry.context.agent_id:
            continue

        async def delegate(arguments, context, _subagent=subagent):
            task = str(arguments.get("task") or "").strip()
            if not task:
                raise ValueError("task is required")
            child_context = {**context.metadata, "subagent_depth": current_depth + 1, "parent_agent_id": context.agent_id}
            return await runner(_subagent.agent_id, task, child_context)

        registry.register(
            ToolSpec(
                name=f"delegate_{subagent.name}",
                description=f"Delegate a focused task to {_subagent_label(subagent)}. {subagent.description}",
                input_schema={
                    "type": "object",
                    "properties": {"task": {"type": "string", "description": "A self-contained task for the sub-agent"}},
                    "required": ["task"],
                    "additionalProperties": False,
                },
                handler=delegate,
                source=f"subagent:{subagent.agent_id}",
            )
        )


def _subagent_label(subagent: SubagentSpec) -> str:
    return subagent.name.strip() or subagent.agent_id
