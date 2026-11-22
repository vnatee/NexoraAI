import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app as backend_app


@pytest.mark.asyncio
async def test_create_agent_requires_manage_agents_for_target_team(client, monkeypatch):
    calls = []

    def require_access(claims, team_id, *, permission=None):
        calls.append((team_id, permission))
        return {"_id": "user-1"}, {"_id": team_id, "agent_id": []}

    monkeypatch.setattr(backend_app, "_require_team_access", require_access)
    monkeypatch.setattr(backend_app, "_validate_agent_model_config", lambda value: value)
    monkeypatch.setattr(
        backend_app,
        "insert_agent",
        lambda *args: (SimpleNamespace(inserted_id="agent-1"), "agent-1"),
    )
    monkeypatch.setattr(backend_app, "update_team", lambda **kwargs: True)

    response = await client.post(
        "/create_agent",
        json={
            "team_id": "team-1",
            "agent_name": "Secure Agent",
            "config": {},
            "prompt": {},
        },
    )

    assert response.status_code == 200
    assert calls == [("team-1", "Manage agents")]


@pytest.mark.asyncio
async def test_create_agent_rejects_cross_team_mcp_connection(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *args, **kwargs: (
            {"_id": "user-1"},
            {"_id": "team-1", "agent_id": []},
        ),
    )
    monkeypatch.setattr(
        backend_app,
        "_validate_agent_model_config",
        lambda value: value,
    )
    monkeypatch.setattr(
        backend_app,
        "get_mcp_server",
        lambda _server_id: {"_id": "mcp-2", "team_id": "team-2"},
    )

    response = await client.post(
        "/create_agent",
        json={
            "team_id": "team-1",
            "agent_name": "Unsafe Agent",
            "config": {"tool_settings": {"mcp_server_ids": ["mcp-2"]}},
            "prompt": {},
        },
    )

    assert response.status_code == 403
    assert (await response.get_json())["error"] == (
        "MCP connection is not assigned to the Agent's team"
    )


@pytest.mark.asyncio
async def test_create_agent_rejects_cross_team_web_search_connection(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *args, **kwargs: (
            {"_id": "user-1"},
            {"_id": "team-1", "agent_id": []},
        ),
    )
    monkeypatch.setattr(backend_app, "_validate_agent_model_config", lambda value: value)
    monkeypatch.setattr(
        backend_app,
        "get_web_search_connection",
        lambda _connection_id: {
            "_id": "search-2",
            "team_id": "team-2",
            "enabled": True,
        },
    )

    response = await client.post(
        "/create_agent",
        json={
            "team_id": "team-1",
            "agent_name": "Unsafe Search Agent",
            "config": {
                "tool_settings": {
                    "mcp_server_ids": [],
                    "web_search": True,
                    "web_search_connection_id": "search-2",
                }
            },
            "prompt": {},
        },
    )

    assert response.status_code == 403
    assert (await response.get_json())["error"] == (
        "Web Search connection is not assigned to the Agent's team"
    )


@pytest.mark.asyncio
async def test_edit_agent_rejects_agent_from_another_team(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *args, **kwargs: ({"_id": "user-1"}, {"_id": "team-1", "agent_id": ["agent-1"]}),
    )

    response = await client.post(
        "/edit_agent",
        json={
            "team_id": "team-1",
            "agent_id": "agent-from-other-team",
            "agent_name": "Unsafe edit",
            "config": {},
            "prompt": {},
        },
    )

    assert response.status_code == 404
    assert (await response.get_json())["error"] == "Agent does not belong to this team"


@pytest.mark.asyncio
async def test_edit_agent_requires_private_revision_for_active_agent(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *args, **kwargs: ({"_id": "manager-1"}, {"_id": "team-1", "agent_id": ["active-1"]}),
    )
    monkeypatch.setattr(
        backend_app,
        "get_agent_by_id",
        lambda _agent_id: {"_id": "active-1", "lifecycle_status": "active"},
    )

    response = await client.post(
        "/edit_agent",
        json={
            "team_id": "team-1",
            "agent_id": "active-1",
            "agent_name": "Unsafe direct edit",
            "config": {},
            "prompt": {},
        },
    )

    assert response.status_code == 409
    assert "private revision" in (await response.get_json())["error"]


@pytest.mark.asyncio
async def test_begin_agent_revision_adds_private_revision_to_team(client, monkeypatch):
    updates = []
    audits = []
    active = {
        "_id": "active-1",
        "agent_name": "Active",
        "lifecycle_status": "active",
        "update_at": datetime.now(timezone.utc),
    }
    revision = {
        "_id": "revision-1",
        "agent_name": "Active",
        "lifecycle_status": "draft",
        "draft_kind": "revision",
        "revision_of": "active-1",
        "draft_expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *args, **kwargs: ({"_id": "manager-1"}, {"_id": "team-1", "agent_id": ["active-1"]}),
    )
    monkeypatch.setattr(backend_app, "get_agent_by_id", lambda _agent_id: active)
    monkeypatch.setattr(
        backend_app,
        "create_or_resume_agent_revision",
        lambda *_args, **_kwargs: (revision, True),
    )
    monkeypatch.setattr(backend_app, "update_team", lambda **kwargs: updates.append(kwargs))

    class AuditCollection:
        def insert_one(self, document):
            audits.append(document)

    class Database:
        def __getitem__(self, _name):
            return AuditCollection()

    monkeypatch.setattr(backend_app, "get_database", lambda: Database())

    response = await client.post("/teams/team-1/agents/active-1/revision")

    payload = await response.get_json()
    assert response.status_code == 201
    assert payload["revision"]["_id"] == "revision-1"
    assert updates == [{"team_id": "team-1", "agent_id": ["active-1", "revision-1"]}]
    assert audits[0]["event_type"] == "agent_revision_created"


@pytest.mark.asyncio
async def test_agent_list_requires_team_membership(client, monkeypatch):
    calls = []

    def require_access(claims, team_id, *, permission=None):
        calls.append((team_id, permission))
        return {"_id": "user-1"}, {"_id": team_id, "agent_id": []}

    monkeypatch.setattr(backend_app, "_require_team_access", require_access)

    response = await client.post("/get_agent_by_team", json={"team_id": "team-1"})

    assert response.status_code == 200
    assert calls == [("team-1", None)]


@pytest.mark.asyncio
async def test_agent_list_normalizes_legacy_null_prompt_and_config(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *_args, **_kwargs: (
            {"_id": "manager-1"},
            {"_id": "team-1", "agent_id": ["legacy-default"]},
        ),
    )
    monkeypatch.setattr(
        backend_app,
        "get_agent_by_id",
        lambda _agent_id: {
            "_id": "legacy-default",
            "agent_name": "default",
            "prompt": None,
            "config": None,
            "lifecycle_status": "active",
        },
    )
    monkeypatch.setattr(backend_app, "is_expired_agent_draft", lambda _agent: False)

    response = await client.post(
        "/get_agent_by_team",
        json={"team_id": "team-1", "include_drafts": True},
    )

    assert response.status_code == 200
    agent = (await response.get_json())["result"][0]
    assert agent["prompt"] == {
        "role": "",
        "task": "",
        "detail_context": "",
        "output_format": "",
        "constraints": "",
    }
    assert agent["config"] == {}


@pytest.mark.asyncio
async def test_create_agent_draft_is_private_and_has_expiry(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *args, **kwargs: (
            {"_id": "manager-1"},
            {"_id": "team-1", "agent_id": []},
        ),
    )
    monkeypatch.setattr(backend_app, "_validate_agent_model_config", lambda value: value)
    monkeypatch.setattr(backend_app, "_validate_agent_mcp_connections", lambda *args, **kwargs: None)

    def insert(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(inserted_id="draft-1"), "draft-1"

    monkeypatch.setattr(backend_app, "insert_agent", insert)
    monkeypatch.setattr(backend_app, "update_team", lambda **kwargs: True)

    response = await client.post(
        "/create_agent",
        json={
            "team_id": "team-1",
            "agent_name": "Draft Agent",
            "config": {},
            "prompt": {},
            "draft": True,
        },
    )

    payload = await response.get_json()
    assert response.status_code == 201
    assert payload["agent"]["lifecycle_status"] == "draft"
    assert payload["agent"]["draft_expires_at"]
    assert captured["lifecycle_status"] == "draft"
    assert captured["created_by"] == "manager-1"


@pytest.mark.asyncio
async def test_agent_list_hides_drafts_unless_manager_requests_them(client, monkeypatch):
    calls = []

    def require_access(claims, team_id, *, permission=None):
        calls.append(permission)
        return {"_id": "manager-1"}, {"_id": team_id, "agent_id": ["active-1", "draft-1"]}

    monkeypatch.setattr(backend_app, "_require_team_access", require_access)
    monkeypatch.setattr(
        backend_app,
        "get_agent_by_id",
        lambda agent_id: {
            "_id": agent_id,
            "lifecycle_status": "draft" if agent_id == "draft-1" else "active",
        },
    )
    monkeypatch.setattr(backend_app, "is_expired_agent_draft", lambda _agent: False)

    response = await client.post("/get_agent_by_team", json={"team_id": "team-1"})
    assert [item["_id"] for item in (await response.get_json())["result"]] == ["active-1"]

    response = await client.post(
        "/get_agent_by_team",
        json={"team_id": "team-1", "include_drafts": True},
    )
    assert [item["_id"] for item in (await response.get_json())["result"]] == ["active-1", "draft-1"]
    assert calls == [None, "Manage agents"]


@pytest.mark.asyncio
async def test_finish_agent_setup_activates_team_draft(client, monkeypatch):
    activated = []
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *args, **kwargs: (
            {"_id": "manager-1"},
            {"_id": "team-1", "agent_id": ["draft-1"]},
        ),
    )
    monkeypatch.setattr(
        backend_app,
        "get_agent_by_id",
        lambda _agent_id: {
            "_id": "draft-1",
            "agent_name": "Draft Agent",
            "config": {},
            "lifecycle_status": "draft",
        },
    )
    monkeypatch.setattr(backend_app, "_validate_agent_model_config", lambda value: value)
    monkeypatch.setattr(backend_app, "_validate_agent_mcp_connections", lambda *args, **kwargs: None)
    monkeypatch.setattr(backend_app, "is_expired_agent_draft", lambda _agent: False)
    monkeypatch.setattr(backend_app, "activate_agent_by_id", lambda agent_id: activated.append(agent_id) or True)

    class AuditCollection:
        def insert_one(self, _document):
            return None

    class Database:
        def __getitem__(self, _name):
            return AuditCollection()

    monkeypatch.setattr(backend_app, "get_database", lambda: Database())

    response = await client.post(
        "/activate_agent_draft",
        json={"team_id": "team-1", "agent_id": "draft-1"},
    )

    assert response.status_code == 200
    assert activated == ["draft-1"]


def test_draft_agent_is_rejected_before_chat_authorization(monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "get_agent_by_id",
        lambda _agent_id: {"_id": "draft-1", "lifecycle_status": "draft"},
    )

    with pytest.raises(backend_app.AccessControlError, match="still a draft"):
        backend_app._authorized_request_claims(
            {"team_id": "team-1"},
            {"oid": "user-1"},
            agent_id="draft-1",
        )


@pytest.mark.asyncio
async def test_playground_rejects_active_agent_without_running_model(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *_args, **_kwargs: (
            {"_id": "manager-1"},
            {"_id": "team-1", "agent_id": ["agent-1"]},
        ),
    )
    monkeypatch.setattr(
        backend_app,
        "get_agent_by_id",
        lambda _agent_id: {"_id": "agent-1", "lifecycle_status": "active"},
    )

    response = await client.post(
        "/teams/team-1/agents/agent-1/playground",
        json={"messages": [{"role": "user", "content": "test"}]},
    )

    assert response.status_code == 409
    assert "private Agent drafts only" in (await response.get_json())["error"]


@pytest.mark.asyncio
async def test_playground_runs_team_draft_with_server_safe_tool_policy(client, monkeypatch):
    captured = {}
    agent = {
        "_id": "draft-1",
        "agent_name": "Draft Agent",
        "lifecycle_status": "draft",
        "prompt": {"role": "Assistant", "task": "Answer safely"},
        "config": {"runtime": "langgraph", "llm_profile_id": "system"},
    }
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda _claims, team_id, *, permission=None: (
            {"_id": "manager-1"},
            {"_id": team_id, "agent_id": ["draft-1"]},
        ),
    )
    monkeypatch.setattr(backend_app, "get_agent_by_id", lambda _agent_id: agent)
    monkeypatch.setattr(backend_app, "is_expired_agent_draft", lambda _agent: False)
    monkeypatch.setattr(
        backend_app,
        "_effective_access_for_request",
        lambda *_args, **_kwargs: SimpleNamespace(
            team_id="team-1",
            selected_data_group_ids=(),
            selected_scopes=("global",),
            user_id="manager-1",
        ),
    )
    monkeypatch.setattr(
        backend_app,
        "_apply_agent_llm_profile",
        lambda context, *_args, **_kwargs: context["overrides"].update(
            {
                "_llm_model": "test-model",
                "_llm_profile_id": "system",
                "_llm_route_type": "built_in",
            }
        ),
    )
    monkeypatch.setattr(backend_app, "_enforce_llm_quota", AsyncMock())
    monkeypatch.setattr(
        backend_app,
        "_enforce_input_guardrails",
        AsyncMock(
            return_value=(
                backend_app.GuardrailPolicy(enabled=False),
                backend_app.AuditTrail(
                    agent_id="draft-1",
                    team_id="team-1",
                    auth_claims={"oid": "manager-1"},
                    execution_context="playground",
                ),
            )
        ),
    )
    monkeypatch.setattr(backend_app, "_persist_user_usage", AsyncMock())
    monkeypatch.setattr(
        backend_app, "_apply_guardrails_to_response", AsyncMock(side_effect=lambda response, *_args: response)
    )
    monkeypatch.setattr(backend_app, "_use_langgraph_runtime", lambda *_args, **_kwargs: True)

    class Runtime:
        async def run(self, runtime_messages):
            if runtime_messages[-1]["content"] == "fail":
                raise RuntimeError("private upstream detail")
            return {
                "content": "Safe answer",
                "iterations": 1,
                "model_calls": [],
                "tool_trace": [],
                "execution_trace": [
                    {
                        "kind": "mcp",
                        "label": "lookup_customer",
                        "status": "success",
                        "duration_ms": 12.5,
                        "source": "mcp:private-server",
                        "risk_level": "read",
                        "argument_keys": ["customer_id"],
                        "args": {"customer_id": "secret-value"},
                        "output": "secret-output",
                    }
                ],
            }

    async def create_runtime(**kwargs):
        captured.update(kwargs)
        return Runtime()

    monkeypatch.setattr(backend_app, "create_agent_runtime", create_runtime)

    response = await client.post(
        "/teams/team-1/agents/draft-1/playground",
        json={
            "messages": [{"role": "user", "content": "test"}],
            "selected_scopes": ["global"],
            "safe_mode": True,
        },
    )

    payload = await response.get_json()
    assert response.status_code == 200
    assert payload["answer"] == "Safe answer"
    assert payload["diagnostics"]["safe_mode"] is True
    assert [step["kind"] for step in payload["diagnostics"]["steps"]] == [
        "input",
        "guardrail",
        "mcp",
        "guardrail",
        "answer",
    ]
    serialized_trace = json.dumps(payload["diagnostics"]["steps"])
    assert "secret-value" not in serialized_trace
    assert "secret-output" not in serialized_trace
    assert payload["diagnostics"]["configuration"]["prompt_revision"]
    assert payload["diagnostics"]["configuration"]["model"] == "test-model"
    assert captured["agent_document"] is agent
    assert captured["allow_draft"] is True
    assert captured["allowed_risk_levels"] == frozenset({"read", "render"})

    failed_response = await client.post(
        "/teams/team-1/agents/draft-1/playground",
        json={
            "messages": [{"role": "user", "content": "fail"}],
            "selected_scopes": ["global"],
            "safe_mode": True,
        },
    )
    failed_payload = await failed_response.get_json()
    assert failed_response.status_code == 500
    assert failed_payload["diagnostics"]["steps"][-1]["label"] == "LLM request failed"
    assert failed_payload["diagnostics"]["steps"][-1]["summary"].endswith("RuntimeError")
    assert "private upstream detail" not in json.dumps(failed_payload)


@pytest.mark.asyncio
async def test_team_guardrail_settings_require_manage_agents(client, monkeypatch):
    calls = []

    def require_access(claims, team_id, *, permission=None):
        calls.append((team_id, permission))
        return {"_id": "user-1"}, {"_id": team_id, "agent_id": []}

    monkeypatch.setattr(backend_app, "_require_team_access", require_access)
    monkeypatch.setattr(backend_app, "get_guardrail_settings", lambda team_id=None: None)

    response = await client.get("/teams/team-1/guardrail-settings")

    assert response.status_code == 200
    assert calls == [("team-1", "Manage agents")]


@pytest.mark.asyncio
async def test_team_guardrail_settings_are_normalized_before_save(client, monkeypatch):
    calls = []

    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda claims, team_id, *, permission=None: ({"_id": "user-1"}, {"_id": team_id}),
    )

    def save(policy, team_id=None):
        calls.append((policy, team_id))
        return backend_app.GuardrailPolicy.from_config(policy).serialize()

    monkeypatch.setattr(backend_app, "save_guardrail_settings", save)
    monkeypatch.setattr(backend_app, "get_guardrail_settings", lambda team_id=None: None)

    response = await client.put(
        "/teams/team-1/guardrail-settings",
        json={"enabled": True, "max_input_chars": 1234, "pii_output_action": "block"},
    )

    assert response.status_code == 200
    assert calls[0][1] == "team-1"
    payload = await response.get_json()
    assert payload["policy"]["max_input_chars"] == 1234
    assert payload["policy"]["pii_output_action"] == "block"


@pytest.mark.asyncio
async def test_team_chat_history_retention_requires_manage_agents(client, monkeypatch):
    calls = []

    def require_access(claims, team_id, *, permission=None):
        calls.append((team_id, permission))
        return {"_id": "user-1"}, {"_id": team_id}

    monkeypatch.setattr(backend_app, "_require_team_access", require_access)
    monkeypatch.setattr(
        backend_app,
        "configured_chat_history_retention_days",
        lambda team_id=None: 14 if team_id else 30,
    )
    monkeypatch.setattr(
        backend_app,
        "effective_chat_history_retention_days",
        lambda team_id=None: 14 if team_id else 30,
    )

    response = await client.get("/teams/team-1/chat-history-retention")

    assert response.status_code == 200
    assert calls == [("team-1", "Manage agents")]
    assert (await response.get_json())["effective_days"] == 14


@pytest.mark.asyncio
async def test_system_chat_history_retention_requires_system_admin(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        backend_app,
        "_require_system_admin",
        lambda claims: calls.append(claims) or {"_id": "admin"},
    )
    monkeypatch.setattr(backend_app, "save_chat_history_retention_days", lambda value: int(value))

    response = await client.put(
        "/admin/chat-history-retention",
        json={"retention_days": 90},
    )

    assert response.status_code == 200
    assert len(calls) == 1
    assert (await response.get_json()) == {"configured_days": 90, "effective_days": 90}
