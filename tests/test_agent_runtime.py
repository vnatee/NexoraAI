import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai.types.chat import ChatCompletion

from agent_runtime.adapters.mcp import load_mcp_servers
from agent_runtime.adapters.rag import register_rag_tool
from agent_runtime.adapters.subagent import SubagentSpec, register_subagent_tools
from agent_runtime.factory import _effective_mcp_allowed_tools
from agent_runtime.runtime import AgentRuntime, AgentRuntimeConfig
from agent_runtime.tools import ToolRegistry, ToolRuntimeContext, ToolSpec
from approaches.approach import Document
from core.attachment_index import AttachmentSearchResult


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


def test_agent_mcp_allowlist_cannot_expand_admin_allowlist():
    assert _effective_mcp_allowed_tools(
        ("search_logs", "search_monitors"),
        ("search_logs", "delete_monitor"),
    ) == ("search_logs",)
    assert _effective_mcp_allowed_tools(
        ("search_logs",), ("delete_monitor",)
    ) is None
    assert _effective_mcp_allowed_tools((), ("search_logs",)) == ("search_logs",)
    assert _effective_mcp_allowed_tools(("search_logs",), ()) == ("search_logs",)


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
async def test_explicit_mcp_request_requires_mcp_tool_on_first_iteration():
    registry = ToolRegistry(
        ToolRuntimeContext(agent_id="agent-1", auth_claims={"oid": "user-1"})
    )
    mcp_handler = AsyncMock(return_value={"monitors": []})
    registry.register(
        ToolSpec(
            name="mcp_datadog_search_datadog_monitors",
            description="Search Datadog monitors",
            input_schema={"type": "object", "properties": {}},
            handler=mcp_handler,
            source="mcp:server-1:Datadog",
        )
    )
    registry.register(
        ToolSpec(
            name="unrelated_tool",
            description="An unrelated tool",
            input_schema={"type": "object", "properties": {}},
            handler=AsyncMock(return_value={}),
            source="builtin",
        )
    )
    model = AsyncMock(
        side_effect=[
            completion(
                tool_calls=[
                    {
                        "id": "call-datadog",
                        "type": "function",
                        "function": {
                            "name": "mcp_datadog_search_datadog_monitors",
                            "arguments": "{}",
                        },
                    }
                ]
            ),
            completion(content="No alerting monitors were returned."),
        ]
    )

    result = await AgentRuntime(model, registry).run(
        [{"role": "user", "content": "Check Datadog monitor alerts"}]
    )

    assert result["content"] == "No alerting monitors were returned."
    assert model.await_args_list[0].args[2] == "required"
    first_tool_names = {
        item["function"]["name"] for item in model.await_args_list[0].args[1]
    }
    assert first_tool_names == {"mcp_datadog_search_datadog_monitors"}
    assert model.await_args_list[1].args[2] is None
    mcp_handler.assert_awaited_once()


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


@pytest.mark.asyncio
async def test_evidence_matrix_rag_exposes_only_source_basename_for_display():
    approach = MagicMock()
    approach.build_filter.return_value = None
    approach.search = AsyncMock(
        return_value=[
            Document(
                id="1",
                content="Evidence",
                sourcefile="team-uuid/ProductBrief.pdf",
                sourcepage="team-uuid/ProductBrief.pdf#page=2",
            )
        ]
    )
    approach.get_sources_content.return_value = [
        "team-uuid/ProductBrief.pdf#page=2: Display filename: ProductBrief.pdf. Content: Evidence"
    ]
    registry = ToolRegistry(
        ToolRuntimeContext(agent_id="agent-1", auth_claims={"oid": "user-1"})
    )
    overrides = {
        "retrieval_mode": "text",
        "top": 3,
        "_requirements_evidence_matrix": True,
    }
    register_rag_tool(registry, approach, overrides)

    output = json.loads(await registry.execute("search_knowledge", {"query": "requirement"}))

    assert output["results"][0]["sourcefile"] == "ProductBrief.pdf"
    assert output["results"][0]["sourcepage"] == "team-uuid/ProductBrief.pdf#page=2"
    approach.get_sources_content.assert_called_once_with(
        approach.search.return_value,
        use_semantic_captions=False,
        use_image_citation=False,
        include_display_filename=True,
    )


@pytest.mark.asyncio
async def test_rag_can_search_only_scoped_temporary_attachments():
    attachment_id = "9aee2161-d67f-45a1-b4a5-7d2042dd1c26"
    conversation_id = "00ec4e94-1e98-4bc5-8a7a-982f33c6b7af"
    attachment_index = MagicMock()
    attachment_index.search = AsyncMock(
        return_value=[
            AttachmentSearchResult(
                attachment_id=attachment_id,
                filename="requirements.pdf",
                page_number=12,
                page_label="12",
                text="Requirement text",
                score=1.0,
            )
        ]
    )
    approach = MagicMock()
    approach.search = AsyncMock()
    approach.get_sources_content.return_value = []
    registry = ToolRegistry(
        ToolRuntimeContext(agent_id="agent-1", auth_claims={"oid": "user-1"})
    )
    register_rag_tool(
        registry,
        approach,
        {
            "_temporary_attachment_index": attachment_index,
            "_temporary_attachment_ids": [attachment_id],
            "_temporary_attachment_owner_id": "user-1",
            "_temporary_attachment_conversation_id": conversation_id,
        },
        include_enterprise=False,
    )

    output = json.loads(await registry.execute("search_knowledge", {"query": "requirement 12"}))

    approach.search.assert_not_awaited()
    attachment_index.search.assert_awaited_once_with(
        owner_id="user-1",
        conversation_id=conversation_id,
        query="requirement 12",
        attachment_ids=[attachment_id],
        limit=5,
    )
    assert output["temporary_attachment_results"] == [
        {
            "source": f"chat-attachment-{attachment_id}--requirements.pdf#page=12",
            "filename": "requirements.pdf",
            "page": 12,
            "section": "12",
            "content": "Requirement text",
            "untrusted": True,
        }
    ]
    assert output["citations"] == [
        f"chat-attachment-{attachment_id}--requirements.pdf#page=12: Requirement text"
    ]


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


@pytest.mark.asyncio
async def test_subagent_tool_delegates_with_bounded_context():
    registry = ToolRegistry(
        ToolRuntimeContext(
            agent_id="parent-agent",
            auth_claims={"oid": "user-1"},
            metadata={"subagent_depth": 0},
        )
    )
    runner = AsyncMock(return_value={"content": "specialist result"})

    register_subagent_tools(
        registry,
        [SubagentSpec("child-agent", "Risk Analyst", "Review purchasing risk")],
        runner,
        max_depth=2,
    )

    result = json.loads(
        await registry.execute(
            "delegate_risk_analyst_child_ag", {"task": "Review PO-1001"}
        )
    )

    assert result["content"] == "specialist result"
    runner.assert_awaited_once()
    child_metadata = runner.await_args.args[2]
    assert child_metadata["subagent_depth"] == 1
    assert child_metadata["parent_agent_id"] == "parent-agent"
    assert child_metadata["subagent_stack"] == ["parent-agent"]


def test_subagent_tools_prevent_cycles_and_stop_at_max_depth():
    cycle_registry = ToolRegistry(
        ToolRuntimeContext(
            agent_id="child-agent",
            auth_claims={},
            metadata={
                "subagent_depth": 1,
                "subagent_stack": ["parent-agent"],
            },
        )
    )
    runner = AsyncMock()
    register_subagent_tools(
        cycle_registry,
        [
            SubagentSpec("parent-agent", "Parent", "Parent agent"),
            SubagentSpec("child-agent", "Self", "Current agent"),
        ],
        runner,
        max_depth=2,
    )
    assert cycle_registry.specs() == []

    depth_registry = ToolRegistry(
        ToolRuntimeContext(
            agent_id="child-agent",
            auth_claims={},
            metadata={"subagent_depth": 2},
        )
    )
    register_subagent_tools(
        depth_registry,
        [SubagentSpec("other-agent", "Other", "Other agent")],
        runner,
        max_depth=2,
    )
    assert depth_registry.specs() == []
