from types import SimpleNamespace

import pytest

import app as backend_app
from mongo_table_connecters.agent_catalog import sanitized_agent_snapshot


def test_catalog_snapshot_removes_team_bound_agent_references():
    original = {
        "agent_name": "Operations Assistant",
        "prompt": {"role": "helpful"},
        "config": {
            "llm_profile_id": "system",
            "tool_settings": {
                "mcp": True,
                "mcp_server_ids": ["secret-team-connection"],
                "mcp_tool_allowlists": {"secret-team-connection": ["read"]},
                "subagents": True,
                "subagent_ids": ["private-agent"],
            },
        },
    }

    snapshot = sanitized_agent_snapshot(original)

    assert snapshot["config"]["tool_settings"]["mcp_server_ids"] == []
    assert snapshot["config"]["tool_settings"]["mcp_tool_allowlists"] == {}
    assert snapshot["config"]["tool_settings"]["subagent_ids"] == []
    assert original["config"]["tool_settings"]["mcp_server_ids"] == ["secret-team-connection"]


@pytest.mark.asyncio
async def test_team_catalog_list_never_returns_prompt_or_config(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *args, **kwargs: ({"_id": "user-1"}, {"_id": "team-1"}),
    )
    monkeypatch.setattr(
        backend_app,
        "list_catalog_items",
        lambda **kwargs: [{
            "_id": "catalog-1",
            "name": "Safe Agent",
            "summary": "Reusable workflow",
            "category": "Operations",
            "publisher_team_id": "team-1",
            "visibility": "team",
            "status": "published",
            "latest_version": 1,
        }],
    )
    monkeypatch.setattr(backend_app, "get_team_by_id", lambda _id: {"_id": "team-1", "name": "Alpha"})
    monkeypatch.setattr(backend_app, "get_user_by_id", lambda _id: {"_id": "user-1", "first_name": "Ada", "last_name": "Admin"})
    monkeypatch.setattr(
        backend_app,
        "get_catalog_version",
        lambda *_args: {
            "requirements": {"runtime": "legacy"},
            "snapshot": {"prompt": {"role": "private"}, "config": {"secret": "private"}},
        },
    )
    monkeypatch.setattr(backend_app, "get_active_installation", lambda *_args: None)

    response = await client.get("/agent-catalog?team_id=team-1")

    assert response.status_code == 200
    item = (await response.get_json())["result"][0]
    assert item["publisher_team"]["name"] == "Alpha"
    assert item["created_by"]["name"] == "Ada Admin"
    assert "prompt" not in item
    assert "config" not in item
    assert "snapshot" not in item


@pytest.mark.asyncio
async def test_team_manager_publish_is_forced_to_own_team_visibility(client, monkeypatch):
    published = {}
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *args, **kwargs: (
            {"_id": "manager-1", "is_sys_admin": False},
            {"_id": "team-1", "agent_id": ["agent-1"]},
        ),
    )
    monkeypatch.setattr(
        backend_app,
        "get_agent_by_id",
        lambda _id: {"_id": "agent-1", "agent_name": "Agent", "prompt": {}, "config": {}},
    )

    def publish(**kwargs):
        published.update(kwargs)
        return {
            "_id": "catalog-1",
            "name": "Agent",
            "publisher_team_id": "team-1",
            "status": "published",
            "visibility": kwargs["visibility"],
            "allowed_team_ids": kwargs["allowed_team_ids"],
            "latest_version": 1,
        }, 1

    monkeypatch.setattr(backend_app, "publish_agent", publish)
    monkeypatch.setattr(backend_app, "insert_catalog_audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(backend_app, "get_catalog_version", lambda *_args: {"requirements": {}})
    monkeypatch.setattr(backend_app, "get_team_by_id", lambda _id: {"name": "Alpha"})
    monkeypatch.setattr(backend_app, "get_user_by_id", lambda _id: {"_id": "manager-1", "first_name": "Team", "last_name": "Manager"})
    monkeypatch.setattr(backend_app, "get_active_installation", lambda *_args: None)

    response = await client.post(
        "/agent-catalog/publish",
        json={
            "team_id": "team-1",
            "agent_id": "agent-1",
            "summary": "Safe summary",
            "usage_instructions": "Ask for an operations summary.",
            "tags": ["operations"],
            "category": "Operations",
            "visibility": "all_teams",
            "allowed_team_ids": ["team-2"],
        },
    )

    assert response.status_code == 200
    assert published["visibility"] == "team"
    assert published["allowed_team_ids"] == []


@pytest.mark.asyncio
async def test_system_admin_can_publish_team_agent_for_all_teams(client, monkeypatch):
    published = {}
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *args, **kwargs: (
            {"_id": "admin-1", "is_sys_admin": True},
            {"_id": "team-1", "agent_id": ["agent-1"]},
        ),
    )
    monkeypatch.setattr(
        backend_app,
        "get_agent_by_id",
        lambda _id: {"_id": "agent-1", "agent_name": "Agent", "prompt": {}, "config": {}},
    )

    def publish(**kwargs):
        published.update(kwargs)
        return {
            "_id": "catalog-1",
            "name": "Agent",
            "publisher_team_id": "team-1",
            "status": "published",
            "visibility": kwargs["visibility"],
            "allowed_team_ids": kwargs["allowed_team_ids"],
            "latest_version": 1,
        }, 1

    monkeypatch.setattr(backend_app, "publish_agent", publish)
    monkeypatch.setattr(backend_app, "insert_catalog_audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(backend_app, "get_catalog_version", lambda *_args: {"requirements": {}})
    monkeypatch.setattr(backend_app, "get_team_by_id", lambda _id: {"name": "Publisher"})
    monkeypatch.setattr(
        backend_app,
        "get_user_by_id",
        lambda _id: {"_id": "admin-1", "first_name": "System", "last_name": "Admin"},
    )
    monkeypatch.setattr(backend_app, "get_active_installation", lambda *_args: None)

    response = await client.post(
        "/agent-catalog/publish",
        json={
            "team_id": "team-1",
            "agent_id": "agent-1",
            "summary": "Shared Agent",
            "usage_instructions": "Install this Agent for the target team.",
            "category": "General",
            "visibility": "all_teams",
        },
    )

    assert response.status_code == 200
    assert published["visibility"] == "all_teams"
    assert published["allowed_team_ids"] == []


@pytest.mark.asyncio
async def test_team_manager_cannot_publish_agent_draft(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *args, **kwargs: (
            {"_id": "manager-1", "is_sys_admin": False},
            {"_id": "team-1", "agent_id": ["draft-1"]},
        ),
    )
    monkeypatch.setattr(
        backend_app,
        "get_agent_by_id",
        lambda _id: {
            "_id": "draft-1",
            "agent_name": "Draft Agent",
            "lifecycle_status": "draft",
            "prompt": {},
            "config": {},
        },
    )

    response = await client.post(
        "/agent-catalog/publish",
        json={
            "team_id": "team-1",
            "agent_id": "draft-1",
            "summary": "Not ready",
            "usage_instructions": "Do not publish yet.",
            "category": "General",
        },
    )

    assert response.status_code == 409
    assert (await response.get_json())["error"] == "Finish the Agent setup before publishing"


@pytest.mark.asyncio
async def test_system_admin_can_create_catalog_template_without_team_agent(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        backend_app,
        "_require_system_admin",
        lambda _claims: {"_id": "admin-1", "is_sys_admin": True},
    )
    monkeypatch.setattr(backend_app, "_validate_agent_model_config", lambda value: value)

    def publish(**kwargs):
        captured.update(kwargs)
        return {
            "_id": "catalog-system",
            "name": kwargs["agent"]["agent_name"],
            "summary": kwargs["summary"],
            "usage_instructions": kwargs["usage_instructions"],
            "tags": kwargs["tags"],
            "category": kwargs["category"],
            "publisher_type": "system",
            "publisher_team_id": "",
            "visibility": kwargs["visibility"],
            "allowed_team_ids": [],
            "status": "published",
            "latest_version": 1,
            "created_by": "admin-1",
        }, 1

    monkeypatch.setattr(backend_app, "publish_agent", publish)
    monkeypatch.setattr(backend_app, "insert_catalog_audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(backend_app, "get_catalog_version", lambda *_args: {"requirements": {}, "created_by": "admin-1"})
    monkeypatch.setattr(backend_app, "get_team_by_id", lambda _id: None)
    monkeypatch.setattr(backend_app, "get_user_by_id", lambda _id: {"_id": "admin-1", "first_name": "System", "last_name": "Admin"})

    response = await client.post(
        "/admin/agent-catalog",
        json={
            "agent_name": "Corporate Assistant",
            "config": {"llm_profile_id": "system"},
            "prompt": {"role": "Corporate assistant"},
            "summary": "Answers approved company questions.",
            "usage_instructions": "Ask a specific company-policy question.",
            "tags": ["company", "policy"],
            "category": "Corporate",
            "visibility": "all_teams",
        },
    )

    assert response.status_code == 201
    assert captured["publisher_type"] == "system"
    assert captured["publisher_team_id"] == ""
    assert captured["agent"]["_id"].startswith("system-catalog:")
    assert captured["usage_instructions"] == "Ask a specific company-policy question."


@pytest.mark.asyncio
async def test_system_catalog_template_cannot_use_empty_publisher_team_visibility(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "get_catalog_item",
        lambda _id: {
            "_id": "catalog-system",
            "publisher_type": "system",
            "publisher_team_id": "",
            "latest_version": 1,
        },
    )
    monkeypatch.setattr(
        backend_app,
        "_application_user_for_claims",
        lambda _claims: {"_id": "admin-1", "active": True, "is_sys_admin": True},
    )

    response = await client.patch(
        "/agent-catalog/catalog-system",
        json={"visibility": "team"},
    )

    assert response.status_code == 400
    assert (await response.get_json())["error"] == (
        "System templates must target selected teams or all teams"
    )


@pytest.mark.asyncio
async def test_install_creates_team_local_agent_without_shared_identity(client, monkeypatch):
    updated = {}
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *args, **kwargs: (
            {"_id": "manager-1"},
            {"_id": "team-2", "agent_id": ["existing-agent"]},
        ),
    )
    monkeypatch.setattr(
        backend_app,
        "get_catalog_item",
        lambda _id: {"_id": "catalog-1", "status": "published", "visibility": "all_teams", "latest_version": 1},
    )
    monkeypatch.setattr(backend_app, "is_visible_to_team", lambda *_args: True)
    monkeypatch.setattr(backend_app, "get_active_installation", lambda *_args: None)
    monkeypatch.setattr(
        backend_app,
        "get_catalog_version",
        lambda *_args: {"snapshot": {"agent_name": "Installed Agent", "prompt": {}, "config": {}}},
    )
    monkeypatch.setattr(backend_app, "_validate_agent_model_config", lambda value: value)
    monkeypatch.setattr(backend_app, "_validate_agent_mcp_connections", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        backend_app,
        "insert_agent",
        lambda *args: (SimpleNamespace(inserted_id="new-agent"), "new-agent"),
    )
    monkeypatch.setattr(backend_app, "update_team", lambda **kwargs: updated.update(kwargs))
    monkeypatch.setattr(backend_app, "record_installation", lambda **kwargs: kwargs)
    monkeypatch.setattr(backend_app, "insert_catalog_audit_event", lambda *args, **kwargs: None)

    response = await client.post("/agent-catalog/catalog-1/install", json={"team_id": "team-2"})

    assert response.status_code == 201
    assert (await response.get_json())["agent_id"] == "new-agent"
    assert updated == {"team_id": "team-2", "agent_id": ["existing-agent", "new-agent"]}


@pytest.mark.asyncio
async def test_install_creates_portable_chart_binding(client, monkeypatch):
    chart = {}
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *args, **kwargs: ({"_id": "manager-1"}, {"_id": "team-2", "agent_id": []}),
    )
    monkeypatch.setattr(
        backend_app,
        "get_catalog_item",
        lambda _id: {"_id": "catalog-1", "status": "published", "visibility": "all_teams", "latest_version": 1},
    )
    monkeypatch.setattr(backend_app, "is_visible_to_team", lambda *_args: True)
    monkeypatch.setattr(backend_app, "get_active_installation", lambda *_args: None)
    monkeypatch.setattr(
        backend_app,
        "get_catalog_version",
        lambda *_args: {
            "snapshot": {
                "agent_name": "Chart Agent",
                "prompt": {},
                "config": {
                    "tool_settings": {"chart": True},
                    "chart_settings": {
                        "auto_generate": True,
                        "chart_selection_mode": "auto",
                        "allowed_chart_types": ["line", "bar"],
                    },
                },
            }
        },
    )
    monkeypatch.setattr(backend_app, "_validate_agent_model_config", lambda value: value)
    monkeypatch.setattr(backend_app, "_validate_agent_mcp_connections", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        backend_app,
        "insert_agent",
        lambda *args: (SimpleNamespace(inserted_id="new-agent"), "new-agent"),
    )
    monkeypatch.setattr(backend_app, "insert_chart_binding", lambda **kwargs: chart.update(kwargs))
    monkeypatch.setattr(backend_app, "update_team", lambda **kwargs: None)
    monkeypatch.setattr(backend_app, "record_installation", lambda **kwargs: kwargs)
    monkeypatch.setattr(backend_app, "insert_catalog_audit_event", lambda *args, **kwargs: None)

    response = await client.post("/agent-catalog/catalog-1/install", json={"team_id": "team-2"})

    assert response.status_code == 201
    assert chart["agent_id"] == "new-agent"
    assert chart["auto_generate"] is True
    assert chart["allowed_chart_types"] == ["line", "bar"]
