from types import SimpleNamespace

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
