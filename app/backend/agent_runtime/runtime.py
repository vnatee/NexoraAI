import json
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
If a relevant tool returns no results or an error, explain that clearly instead of inventing information."""
    max_iterations: int = 8
    knowledge_search_mode: Literal["auto", "always", "disabled"] = "auto"


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
            "content": message.content or None,
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
            completion: ChatCompletion = await self.completion_factory(
                [_to_openai_message(message) for message in state["messages"]],
                self.tools.openai_tools(),
            )
            response = completion.choices[0].message
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
            if latest_query:
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
                                "args": {"query": latest_query},
                                "id": tool_call_id,
                                "type": "tool_call",
                            }
                        ],
                    )
                )
                graph_messages.append(
                    ToolMessage(
                        content=await self.tools.execute(
                            "search_knowledge", {"query": latest_query}
                        ),
                        tool_call_id=tool_call_id,
                        name="search_knowledge",
                    )
                )
        state = await self.graph.ainvoke({"messages": graph_messages, "iterations": 0})
        last = state["messages"][-1]
        return {
            "content": str(last.content),
            "role": "assistant",
            "iterations": state.get("iterations", 0),
            "tool_trace": list(self.tools.execution_log),
            "artifacts": dict(self.tools.context.metadata),
        }
