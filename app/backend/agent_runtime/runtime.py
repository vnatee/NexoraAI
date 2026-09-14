import json
import time
from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from openai.types.chat import ChatCompletion

from agent_runtime.tools import ToolRegistry


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    iterations: int


@dataclass(frozen=True)
class AgentRuntimeConfig:
    system_prompt: str = """You are a helpful AI agent with access to tools.
For questions that may depend on uploaded documents, indexed websites, company knowledge, policies, or other private information, call search_knowledge before answering.
Do not claim that the knowledge base has no information until search_knowledge has been called for the current question.
Treat search_knowledge results as authoritative sources. Base factual claims on those results and cite their source names in square brackets.
Use integration, database, MCP, or sub-agent tools when they are more relevant to the user's request.
If a relevant tool returns no results or an error, explain that clearly instead of inventing information.
When a tool returns a structured error, report the tool name and its exact actionable error message. Do not replace it with a generic temporary system error.
When a tool error includes explicit recovery instructions and the required discovery or search tool is available, follow those instructions and retry once before giving the user a final answer.
Never invent tool parameters, pagination, truncation, result limits, or token-limit explanations. Mention such a limitation only when the tool schema or returned payload explicitly provides evidence for it.
If a returned count conflicts with a count stated by the user, retry with a broader valid query or a more appropriate enabled tool before concluding that records are missing."""
    max_iterations: int = 8
    knowledge_search_mode: Literal["auto", "always", "disabled"] = "auto"
    knowledge_search_query: str | None = None
    mcp_execution_mode: Literal["auto", "required"] = "auto"


def _to_openai_message(message: BaseMessage) -> dict[str, Any]:
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": message.content}
    if isinstance(message, SystemMessage):
        return {"role": "system", "content": message.content}
    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "content": message.content,
            "tool_call_id": message.tool_call_id,
        }
    if isinstance(message, AIMessage):
        result: dict[str, Any] = {
            "role": "assistant",
            # Some Azure OpenAI deployments reject JSON null here even though
            # the assistant message contains a valid tool call. An empty string
            # is accepted by Azure and other OpenAI-compatible providers.
            "content": message.content if message.content is not None else "",
        }
        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call["args"], ensure_ascii=False),
                    },
                }
                for call in message.tool_calls
            ]
        return result
    return {"role": "user", "content": str(message.content)}


class AgentRuntime:
    """A small provider-neutral LangGraph ReAct loop over the existing OpenAI-compatible clients."""

    def __init__(
        self,
        completion_factory,
        tools: ToolRegistry,
        config: AgentRuntimeConfig | None = None,
    ):
        self.completion_factory = completion_factory
        self.tools = tools
        self.config = config or AgentRuntimeConfig()
        self.graph = self._build_graph()

    def _build_graph(self):
        async def call_model(state: AgentState) -> dict[str, Any]:
            started = time.perf_counter()
            first_iteration = state.get("iterations", 0) == 0
            latest_user_query = next(
                (
                    str(message.content)
                    for message in reversed(state["messages"])
                    if isinstance(message, HumanMessage)
                ),
                "",
            )
            require_mcp = (
                first_iteration
                and bool(self.tools.openai_tools(source_prefix="mcp"))
                and (
                    self.config.mcp_execution_mode == "required"
                    or self.tools.query_mentions_source("mcp", latest_user_query)
                )
            )
            available_tools = (
                self.tools.openai_tools(source_prefix="mcp")
                if require_mcp
                else self.tools.openai_tools()
            )
            completion: ChatCompletion = await self.completion_factory(
                [_to_openai_message(message) for message in state["messages"]],
                available_tools,
                "required" if require_mcp else None,
            )
            response = completion.choices[0].message
            usage = (
                completion.usage.model_dump(exclude_none=True)
                if completion.usage is not None
                else None
            )
            calls = []
            for call in response.tool_calls or []:
                try:
                    arguments = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {"_invalid_json": call.function.arguments}
                calls.append(
                    {
                        "name": call.function.name,
                        "args": arguments,
                        "id": call.id,
                        "type": "tool_call",
                    }
                )
            if self.tools.audit:
                await self.tools.audit.emit(
                    "model_iteration",
                    details={
                        "iteration": state.get("iterations", 0) + 1,
                        "tool_calls": [call["name"] for call in calls],
                        "tool_choice": "required" if require_mcp else "auto",
                        "usage": usage,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                )
            return {
                "messages": [
                    AIMessage(content=response.content or "", tool_calls=calls)
                ],
                "iterations": state.get("iterations", 0) + 1,
            }

        async def execute_tools(state: AgentState) -> dict[str, Any]:
            message = state["messages"][-1]
            if not isinstance(message, AIMessage):
                return {"messages": []}
            outputs = []
            for call in message.tool_calls:
                content = await self.tools.execute(call["name"], call["args"])
                outputs.append(
                    ToolMessage(
                        content=content, tool_call_id=call["id"], name=call["name"]
                    )
                )
            return {"messages": outputs}

        async def route(state: AgentState) -> Literal["tools", "__end__"]:
            last = state["messages"][-1]
            if (
                isinstance(last, AIMessage)
                and last.tool_calls
                and state.get("iterations", 0) < self.config.max_iterations
            ):
                return "tools"
            return END

        builder = StateGraph(AgentState)
        builder.add_node("model", call_model)
        builder.add_node("tools", execute_tools)
        builder.add_edge(START, "model")
        builder.add_conditional_edges("model", route, {"tools": "tools", END: END})
        builder.add_edge("tools", "model")
        return builder.compile()

    async def run(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        started = time.perf_counter()
        if self.tools.audit:
            await self.tools.audit.emit(
                "agent_run_started",
                details={"message_count": len(messages)},
            )
        graph_messages: list[BaseMessage] = [
            SystemMessage(content=self.config.system_prompt)
        ]
        for message in messages:
            role = message.get("role")
            content = message.get("content") or ""
            if role == "assistant":
                graph_messages.append(AIMessage(content=content))
            elif role == "system":
                graph_messages.append(SystemMessage(content=content))
            else:
                graph_messages.append(HumanMessage(content=content))
        if self.config.knowledge_search_mode == "always" and self.tools.has(
            "search_knowledge"
        ):
            latest_query = next(
                (
                    str(message.get("content") or "")
                    for message in reversed(messages)
                    if message.get("role") == "user"
                ),
                "",
            ).strip()
            automatic_query = str(self.config.knowledge_search_query or "").strip() or latest_query
            if automatic_query:
                tool_call_id = "automatic_knowledge_search"
                graph_messages[0] = SystemMessage(
                    content=f"{self.config.system_prompt}\nKnowledge Search is executed automatically for each question. Use its results; call it again only to refine the query."
                )
                graph_messages.append(
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "search_knowledge",
                                "args": {"query": automatic_query},
                                "id": tool_call_id,
                                "type": "tool_call",
                            }
                        ],
                    )
                )
                graph_messages.append(
                    ToolMessage(
                        content=await self.tools.execute(
                            "search_knowledge", {"query": automatic_query}
                        ),
                        tool_call_id=tool_call_id,
                        name="search_knowledge",
                    )
                )
        try:
            state = await self.graph.ainvoke(
                {"messages": graph_messages, "iterations": 0}
            )
            last = state["messages"][-1]
            result = {
                "content": str(last.content),
                "role": "assistant",
                "iterations": state.get("iterations", 0),
                "tool_trace": list(self.tools.execution_log),
                "artifacts": dict(self.tools.context.metadata),
                "trace": self.tools.audit.public_summary()
                if self.tools.audit
                else None,
            }
            if self.tools.audit:
                await self.tools.audit.emit(
                    "agent_run_completed",
                    details={
                        "iterations": result["iterations"],
                        "tool_calls": len(result["tool_trace"]),
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                )
                result["trace"] = self.tools.audit.public_summary()
            return result
        except Exception as error:
            if self.tools.audit:
                await self.tools.audit.emit(
                    "agent_run_failed",
                    status="error",
                    details={
                        "error_type": type(error).__name__,
                        "error": str(error)[:2000],
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                )
            raise
