import json
import operator
import re
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
from core.observability import (
    agent_run_span,
    mark_span_error,
    mark_span_success,
    model_completion_span,
)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    iterations: int
    model_calls: Annotated[list[dict[str, Any]], operator.add]
    execution_trace: Annotated[list[dict[str, Any]], operator.add]


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
    chart_trigger_keywords: tuple[str, ...] = ()


def _query_requests_chart(query: str, trigger_keywords: tuple[str, ...]) -> bool:
    normalized_query = str(query or "").casefold()
    keywords = {
        "chart",
        "graph",
        "plot",
        "visualize",
        "visualise",
        "กราฟ",
        "แผนภูมิ",
        *(str(item).strip().casefold() for item in trigger_keywords),
    }
    return any(keyword and keyword in normalized_query for keyword in keywords)


def _query_contains_numeric_data(query: str) -> bool:
    return bool(re.search(r"(?<!\w)[+-]?(?:\d+(?:[,.]\d+)*|\.\d+)(?!\w)", query))


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
            chart_requested = self.tools.has("create_chart") and _query_requests_chart(
                latest_user_query, self.config.chart_trigger_keywords
            )
            chart_attempted = any(
                event.get("name") == "create_chart"
                for event in self.tools.execution_log
            )
            successful_source_result = any(
                event.get("name") != "create_chart" and not event.get("is_error")
                for event in self.tools.execution_log
            )
            require_chart = (
                not require_mcp
                and chart_requested
                and not chart_attempted
                and (
                    successful_source_result
                    or (first_iteration and _query_contains_numeric_data(latest_user_query))
                )
            )
            available_tools = (
                self.tools.openai_tools(source_prefix="mcp")
                if require_mcp
                else self.tools.openai_tools(source_prefix="chart")
                if require_chart
                else self.tools.openai_tools()
            )
            with model_completion_span(self.config.system_prompt) as model_span:
                try:
                    completion: ChatCompletion = await self.completion_factory(
                        [_to_openai_message(message) for message in state["messages"]],
                        available_tools,
                        "required" if require_mcp or require_chart else None,
                    )
                except Exception as error:
                    mark_span_error(model_span, error)
                    raise
                mark_span_success(model_span)
            response = completion.choices[0].message
            usage = (
                completion.usage.model_dump(exclude_none=True)
                if completion.usage is not None
                else None
            )
            model_call = []
            if usage:
                completion_details = usage.get("completion_tokens_details")
                prompt_details = usage.get("prompt_tokens_details")
                reasoning_tokens = (
                    completion_details.get("reasoning_tokens", 0)
                    if isinstance(completion_details, dict)
                    else 0
                )
                cached_input_tokens = (
                    prompt_details.get("cached_tokens", 0)
                    if isinstance(prompt_details, dict)
                    else 0
                )
                model_call = [{
                    "title": f"Model iteration {state.get('iterations', 0) + 1}",
                    "model": str(completion.model or ""),
                    "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                    "cached_input_tokens": int(cached_input_tokens or 0),
                    "completion_tokens": int(usage.get("completion_tokens") or 0),
                    "reasoning_tokens": int(reasoning_tokens or 0),
                    "total_tokens": int(usage.get("total_tokens") or 0),
                }]
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
                        "tool_choice": (
                            "required_mcp"
                            if require_mcp
                            else "required_chart"
                            if require_chart
                            else "auto"
                        ),
                        "usage": usage,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                )
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            return {
                "messages": [
                    AIMessage(content=response.content or "", tool_calls=calls)
                ],
                "iterations": state.get("iterations", 0) + 1,
                "model_calls": model_call,
                "execution_trace": [
                    {
                        "kind": "llm",
                        "label": f"LLM iteration {state.get('iterations', 0) + 1}",
                        "status": "success",
                        "iteration": state.get("iterations", 0) + 1,
                        "duration_ms": duration_ms,
                        "model": str(completion.model or ""),
                        "requested_tools": [call["name"] for call in calls],
                        "decision": (
                            f"Requested {len(calls)} tool call(s)"
                            if calls
                            else "Produced an answer"
                        ),
                        "token_usage": usage or {},
                    }
                ],
            }

        async def execute_tools(state: AgentState) -> dict[str, Any]:
            message = state["messages"][-1]
            if not isinstance(message, AIMessage):
                return {"messages": []}
            outputs = []
            executed_events: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for call in message.tool_calls:
                log_index = len(self.tools.execution_log)
                content = await self.tools.execute(call["name"], call["args"])
                event = (
                    self.tools.execution_log[log_index]
                    if len(self.tools.execution_log) > log_index
                    else {}
                )
                executed_events.append((call, event))
                outputs.append(
                    ToolMessage(
                        content=content, tool_call_id=call["id"], name=call["name"]
                    )
                )
            trace = []
            for call, event in executed_events:
                source = str(event.get("source") or "builtin")
                source_type = source.split(":", 1)[0]
                trace.append(
                    {
                        "kind": (
                            "knowledge"
                            if source_type == "rag"
                            else "mcp"
                            if source_type == "mcp"
                            else "subagent"
                            if source_type == "subagent"
                            else "integration"
                            if source_type not in {"builtin", "chart"}
                            else "tool"
                        ),
                        "label": str(event.get("name") or call.get("name") or "Tool"),
                        "status": (
                            "blocked"
                            if event.get("policy_denied")
                            else "error"
                            if event.get("is_error")
                            else "success"
                        ),
                        "iteration": state.get("iterations", 0),
                        "duration_ms": float(event.get("duration_ms") or 0),
                        "source": source,
                        "risk_level": str(event.get("risk_level") or "read"),
                        "argument_keys": sorted(str(key) for key in call.get("args", {})),
                    }
                )
            return {"messages": outputs, "execution_trace": trace}

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
        with agent_run_span(self.tools.audit, len(messages)) as span:
            try:
                result = await self._run(messages)
            except Exception as error:
                mark_span_error(span, error)
                raise
            mark_span_success(
                span,
                **{
                    "gen_ai.response.iterations": int(result.get("iterations") or 0),
                    "gen_ai.tool.call.count": len(result.get("tool_trace") or []),
                },
            )
            return result

    async def _run(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
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
                automatic_log_index = len(self.tools.execution_log)
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
                automatic_event = self.tools.execution_log[automatic_log_index]
                automatic_trace = [{
                    "kind": "knowledge",
                    "label": "search_knowledge",
                    "status": "error" if automatic_event.get("is_error") else "success",
                    "iteration": 0,
                    "duration_ms": float(automatic_event.get("duration_ms") or 0),
                    "source": "rag",
                    "risk_level": str(automatic_event.get("risk_level") or "read"),
                    "argument_keys": ["query"],
                    "automatic": True,
                }]
            else:
                automatic_trace = []
        else:
            automatic_trace = []
        try:
            state = await self.graph.ainvoke(
                {
                    "messages": graph_messages,
                    "iterations": 0,
                    "model_calls": [],
                    "execution_trace": automatic_trace,
                }
            )
            last = state["messages"][-1]
            result = {
                "content": str(last.content),
                "role": "assistant",
                "iterations": state.get("iterations", 0),
                "model_calls": list(state.get("model_calls") or []),
                "tool_trace": list(self.tools.execution_log),
                "execution_trace": list(state.get("execution_trace") or []),
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
