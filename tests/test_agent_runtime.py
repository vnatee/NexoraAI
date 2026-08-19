import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai.types.chat import ChatCompletion

from agent_runtime.adapters.mcp import load_mcp_servers
from agent_runtime.adapters.rag import register_rag_tool
from agent_runtime.runtime import AgentRuntime, AgentRuntimeConfig
from agent_runtime.tools import ToolRegistry, ToolRuntimeContext, ToolSpec
from approaches.approach import Document


def completion(*, content="", tool_calls=None):
    return ChatCompletion.model_validate(
        {
            "id": "test",
            "created": 0,
            "model": "test-model",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls" if tool_calls else "stop",
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls,
                    },
                }
            ],
        }
    )


@pytest.mark.asyncio
async def test_langgraph_runtime_executes_registered_tool():
    registry = ToolRegistry(
        ToolRuntimeContext(agent_id="agent-1", auth_claims={"oid": "user-1"})
    )
    handler = AsyncMock(return_value={"answer": 42})
    registry.register(
        ToolSpec(
            name="Calculator",
            description="Calculate a value",
            input_schema={
                "type": "object",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
            },
            handler=handler,
        )
    )
    model = AsyncMock(
        side_effect=[
            completion(
                tool_calls=[
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "calculator",
                            "arguments": '{"value": 41}',
                        },
                    }
                ]
            ),
            completion(content="The answer is 42"),
        ]
    )

    result = await AgentRuntime(model, registry).run(
        [{"role": "user", "content": "calculate"}]
    )

    assert result["content"] == "The answer is 42"
    assert result["iterations"] == 2
    handler.assert_awaited_once()
    assert handler.await_args.args[0] == {"value": 41}
    assert "search_knowledge" in model.await_args_list[0].args[0][0]["content"]
    second_messages = model.await_args_list[1].args[0]
    assert any(
        message.get("role") == "tool" and "42" in message.get("content", "")
        for message in second_messages
    )
    assert result["artifacts"] == {}


@pytest.mark.asyncio
async def test_registry_exposes_langchain_tools_without_losing_arguments():
    registry = ToolRegistry(ToolRuntimeContext(agent_id="agent-1", auth_claims={}))

    async def echo(arguments, context):
        return arguments

    registry.register(
        ToolSpec(
            name="echo",
            description="Echo input",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            handler=echo,
        )
    )

    assert json.loads(
        await registry.langchain_tools()[0].ainvoke({"text": "hello"})
    ) == {"text": "hello"}


@pytest.mark.asyncio
async def test_always_mode_searches_knowledge_before_first_model_call():
    registry = ToolRegistry(ToolRuntimeContext(agent_id="agent-1", auth_claims={}))
    search = AsyncMock(
        return_value={
            "results": [{"content": "Found"}],
            "citations": ["doc.pdf: Found"],
        }
    )
    registry.register(
        ToolSpec(
            name="search_knowledge",
            description="Search knowledge",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            handler=search,
            source="rag",
        )
    )
    model = AsyncMock(return_value=completion(content="Answer [doc.pdf]"))

    result = await AgentRuntime(
        model,
        registry,
        AgentRuntimeConfig(knowledge_search_mode="always"),
    ).run([{"role": "user", "content": "What is the policy?"}])

    assert result["content"] == "Answer [doc.pdf]"
    search.assert_awaited_once()
    assert search.await_args.args[0] == {"query": "What is the policy?"}
    first_model_messages = model.await_args.args[0]
    assert any(
        message.get("role") == "tool" and "Found" in message.get("content", "")
        for message in first_model_messages
    )


@pytest.mark.asyncio
async def test_rag_is_an_on_demand_permission_aware_tool():
    approach = MagicMock()
    approach.build_filter.return_value = "oids/any(o: o eq 'user-1')"
    approach.compute_text_embedding = AsyncMock(return_value="vector-query")
    approach.search = AsyncMock(
        return_value=[
            Document(
                id="1",
                content="Policy text",
                sourcefile="policy.pdf",
                sourcepage="policy.pdf",
            )
        ]
    )
    approach.get_sources_content.return_value = ["policy.pdf: Policy text"]
    registry = ToolRegistry(
        ToolRuntimeContext(agent_id="agent-1", auth_claims={"oid": "user-1"})
    )
    register_rag_tool(registry, approach, {"retrieval_mode": "hybrid", "top": 3})

    output = json.loads(await registry.execute("search_knowledge", {"query": "policy"}))

    assert output["citations"] == ["policy.pdf: Policy text"]
    approach.build_filter.assert_called_once_with(
        {"retrieval_mode": "hybrid", "top": 3}, {"oid": "user-1"}
    )
    assert approach.search.await_args.kwargs["filter"] == "oids/any(o: o eq 'user-1')"


def test_load_mcp_servers_applies_allowlist_and_disabled_filter():
    servers = load_mcp_servers(
        json.dumps(
            [
                {
                    "name": "drawio",
                    "url": "https://example.test/mcp",
                    "allowed_tools": ["draw"],
                    "headers": {"X-Key": "x"},
                },
                {"name": "off", "url": "https://off.test/mcp", "enabled": False},
            ]
        )
    )

    assert len(servers) == 1
    assert servers[0].name == "drawio"
    assert servers[0].allowed_tools == ("draw",)
