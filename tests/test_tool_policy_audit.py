import json

import pytest

from agent_runtime.observability import AuditTrail
from agent_runtime.policy import ToolExecutionPolicy, normalize_tool_policy
from agent_runtime.tools import ToolRegistry, ToolRuntimeContext, ToolSpec


@pytest.mark.asyncio
async def test_tool_policy_limits_calls_and_emits_metadata_only_audit(monkeypatch):
    persisted = []
    monkeypatch.delenv("DISABLE_AGENT_AUDIT_PERSISTENCE", raising=False)
    monkeypatch.setattr(
        "agent_runtime.observability.insert_agent_audit_event", persisted.append
    )
    audit = AuditTrail(
        agent_id="agent-1",
        team_id="team-1",
        auth_claims={"oid": "user-1"},
        run_id="run-1",
    )
    registry = ToolRegistry(
        ToolRuntimeContext(
            agent_id="agent-1",
            team_id="team-1",
            auth_claims={"oid": "user-1"},
            run_id="run-1",
        ),
        policy=ToolExecutionPolicy(max_total_calls=1),
        audit=audit,
    )

    async def echo(arguments, context):
        return {"value": arguments["secret"]}

    registry.register(
        ToolSpec(
            name="echo",
            description="Echo",
            input_schema={"type": "object"},
            handler=echo,
        )
    )

    first = json.loads(await registry.execute("echo", {"secret": "do-not-audit"}))
    second = json.loads(await registry.execute("echo", {"secret": "again"}))

    assert first == {"value": "do-not-audit"}
    assert second["policy_denied"] is True
    assert [event["status"] for event in persisted] == ["ok", "policy_denied"]
    assert persisted[0]["details"]["argument_keys"] == ["secret"]
    assert "do-not-audit" not in json.dumps(persisted, default=str)


def test_tool_policy_normalization_is_bounded():
    normalized = normalize_tool_policy(
        {
            "max_total_calls": 999,
            "max_calls_per_tool": 0,
            "max_timeout_seconds": 999,
            "blocked_sources": ["MCP", "mcp", "external_api"],
        }
    )

    assert normalized["max_total_calls"] == 100
    assert normalized["max_calls_per_tool"] == 8
    assert normalized["max_timeout_seconds"] == 300
    assert normalized["blocked_sources"] == ["mcp", "external_api"]
