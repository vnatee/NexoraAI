from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

import app as backend_app
from mongo_table_connecters import mcp_servers
from mongo_table_connecters.mcp_servers import (
    azure_mcp_runtime_config,
    decrypt_mcp_headers,
    normalize_mcp_server_payload,
    serialize_mcp_server,
)


def test_mcp_server_headers_are_encrypted_and_never_serialized(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    normalized = normalize_mcp_server_payload(
        {
            "name": "Datadog",
            "url": "https://mcp.example.test/mcp",
            "headers": {"Authorization": "Bearer secret"},
            "allowed_tools": ["query", "query"],
        }
    )
    document = {"_id": "mcp-1", **normalized}

    assert "secret" not in normalized["headers_ciphertext"]
    assert decrypt_mcp_headers(document) == {"Authorization": "Bearer secret"}
    serialized = serialize_mcp_server(document)
    assert serialized["has_headers"] is True
    assert "headers" not in serialized
    assert "headers_ciphertext" not in serialized
    assert serialized["allowed_tools"] == ["query"]
    assert serialized["category"] == "custom"


def test_mcp_server_normalizes_and_serializes_team_ownership(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    normalized = normalize_mcp_server_payload(
        {
            "team_id": " team-1 ",
            "name": "Team Datadog",
            "url": "https://mcp.datadoghq.com/v1/mcp",
            "vendor": "datadog",
            "headers": {"Authorization": "Bearer secret"},
        }
    )

    assert normalized["team_id"] == "team-1"
    assert serialize_mcp_server({"_id": "mcp-1", **normalized})["team_id"] == "team-1"


def test_azure_template_is_forced_to_read_only_inventory(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())

    normalized = normalize_mcp_server_payload(
        {
            "team_id": "team-1",
            "name": "Azure inventory",
            "url": "https://azure-mcp.example.test/mcp",
            "vendor": "azure",
            "category": "custom",
            "operation_mode": "read_write",
        }
    )

    assert normalized["category"] == "cloud_platform"
    assert normalized["operation_mode"] == "read_only"


def test_managed_azure_connection_encrypts_secrets_and_allows_controller_url(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    normalized = normalize_mcp_server_payload(
        {
            "name": "Azure tenant A",
            "vendor": "azure",
            "deployment_mode": "managed",
            "azure_tenant_id": "11111111-1111-4111-8111-111111111111",
            "azure_client_id": "44444444-4444-4444-8444-444444444444",
            "azure_client_secret": "azure-secret",
            "azure_subscription_ids": ["55555555-5555-4555-8555-555555555555"],
        }
    )

    assert normalized["url"] == ""
    assert normalized["operation_mode"] == "read_only"
    assert normalized["auth_type"] == "headers"
    runtime = azure_mcp_runtime_config(normalized)
    assert runtime["azure_client_secret"] == "azure-secret"
    serialized = serialize_mcp_server({"_id": "mcp-1", **normalized})
    assert serialized["has_entra_client_secret"] is False
    assert serialized["has_azure_client_secret"] is True
    assert "entra_client_secret_ciphertext" not in serialized
    assert "azure_client_secret_ciphertext" not in serialized
    assert "azure-secret" not in str(serialized)


def test_drawio_template_uses_diagram_category(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())

    normalized = normalize_mcp_server_payload(
        {
            "team_id": "team-1",
            "name": "Draw.io",
            "url": "https://drawio-mcp.example.test/mcp",
            "vendor": "drawio",
        }
    )

    assert normalized["category"] == "diagram_collaboration"
    assert normalized["operation_mode"] == "read_write"


def test_azure_connection_cannot_change_vendor_to_bypass_read_only(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    existing = normalize_mcp_server_payload(
        {
            "name": "Azure inventory",
            "url": "https://azure-mcp.example.test/mcp",
            "vendor": "azure",
        }
    )

    with pytest.raises(ValueError, match="vendor cannot be changed"):
        normalize_mcp_server_payload(
            {
                "vendor": "generic",
                "operation_mode": "read_write",
            },
            existing=existing,
        )


def test_mcp_server_list_filters_by_exact_team_and_keeps_legacy_unassigned(
    monkeypatch,
):
    documents = [
        {"_id": "team-1", "team_id": "team-1", "delete_at": None},
        {"_id": "team-2", "team_id": "team-2", "delete_at": None},
        {"_id": "unassigned", "team_id": "", "delete_at": None},
        {"_id": "legacy", "delete_at": None},
    ]

    class Cursor(list):
        def sort(self, *_args):
            return self

    class Collection:
        def find(self, query):
            team_filter = query["team_id"]
            allowed = (
                set(team_filter["$in"])
                if isinstance(team_filter, dict)
                else {team_filter}
            )
            return Cursor(
                item
                for item in documents
                if item.get("team_id") in allowed and item.get("delete_at") is None
            )

    monkeypatch.setattr(mcp_servers, "collection", Collection())

    assert [item["_id"] for item in mcp_servers.list_mcp_servers("team-1")] == [
        "team-1"
    ]
    assert [item["_id"] for item in mcp_servers.list_mcp_servers("")] == [
        "unassigned",
        "legacy",
    ]


def test_available_mcp_list_excludes_managed_instances_until_ready(monkeypatch):
    documents = [
        {
            "_id": "pending",
            "team_id": "team-1",
            "enabled": True,
            "deployment_mode": "managed",
            "provisioning_status": "pending",
            "delete_at": None,
        },
        {
            "_id": "ready",
            "team_id": "team-1",
            "enabled": True,
            "deployment_mode": "managed",
            "provisioning_status": "ready",
            "delete_at": None,
        },
    ]

    class Cursor(list):
        def sort(self, *_args):
            return self

    class Collection:
        def find(self, _query):
            return Cursor(documents)

    monkeypatch.setattr(mcp_servers, "collection", Collection())

    assert [
        item["_id"]
        for item in mcp_servers.list_mcp_servers("team-1", enabled_only=True)
    ] == ["ready"]


def test_agent_mcp_connections_must_belong_to_the_agent_team(monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "get_mcp_server",
        lambda server_id: {"_id": server_id, "team_id": "team-2"},
    )

    with pytest.raises(ValueError, match="not assigned to the Agent's team"):
        backend_app._validate_agent_mcp_connections(
            {"tool_settings": {"mcp_server_ids": ["mcp-1"]}}, "team-1"
        )


def test_existing_legacy_mcp_connection_can_remain_but_cannot_be_newly_bound(
    monkeypatch,
):
    monkeypatch.setattr(
        backend_app,
        "get_mcp_server",
        lambda server_id: {"_id": server_id, "team_id": ""},
    )
    config = {"tool_settings": {"mcp_server_ids": ["mcp-legacy"]}}

    backend_app._validate_agent_mcp_connections(
        config, "team-1", existing_config=config
    )
    with pytest.raises(ValueError, match="not assigned to the Agent's team"):
        backend_app._validate_agent_mcp_connections(config, "team-1")


@pytest.mark.asyncio
async def test_mcp_management_list_is_scoped_to_requested_team(client, monkeypatch):
    access_calls = []
    list_calls = []
    monkeypatch.setattr(
        backend_app,
        "_require_integration_catalog_access",
        lambda claims, team_id, **kwargs: access_calls.append((team_id, kwargs)),
    )
    monkeypatch.setattr(
        backend_app,
        "list_mcp_servers",
        lambda team_id, enabled_only=False: list_calls.append(
            (team_id, enabled_only)
        )
        or [],
    )
    monkeypatch.setattr(
        backend_app,
        "get_database",
        lambda: SimpleNamespace(
            agents=SimpleNamespace(count_documents=lambda _query: 0)
        ),
    )

    response = await client.get("/admin/mcp-servers?team_id=team-1")

    assert response.status_code == 200
    assert access_calls == [("team-1", {})]
    assert list_calls == [("team-1", False)]


@pytest.mark.asyncio
async def test_available_mcp_connections_allow_agent_manager_for_team(
    client, monkeypatch
):
    access_calls = []
    monkeypatch.setattr(
        backend_app,
        "_require_integration_catalog_access",
        lambda claims, team_id, **kwargs: access_calls.append((team_id, kwargs)),
    )
    monkeypatch.setattr(
        backend_app,
        "list_mcp_servers",
        lambda team_id, enabled_only=False: [],
    )

    response = await client.get("/mcp-servers/available?team_id=team-1")

    assert response.status_code == 200
    assert access_calls == [("team-1", {"allow_agent_management": True})]


@pytest.mark.asyncio
async def test_available_mcp_connections_include_only_existing_legacy_binding(
    client, monkeypatch
):
    monkeypatch.setattr(
        backend_app, "_require_integration_catalog_access", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(backend_app, "list_mcp_servers", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        backend_app,
        "get_team_by_id",
        lambda _team_id: {"_id": "team-1", "agent_id": ["agent-1"]},
    )
    monkeypatch.setattr(
        backend_app,
        "get_agent_by_id",
        lambda _agent_id: {
            "_id": "agent-1",
            "config": {"tool_settings": {"mcp_server_ids": ["mcp-legacy"]}},
        },
    )
    monkeypatch.setattr(
        backend_app,
        "get_mcp_server",
        lambda _server_id: {
            "_id": "mcp-legacy",
            "name": "Legacy MCP",
            "url": "https://example.test/mcp",
            "enabled": True,
            "allowed_tools": [],
            "timeout_seconds": 60,
        },
    )

    response = await client.get(
        "/mcp-servers/available?team_id=team-1&agent_id=agent-1"
    )

    assert response.status_code == 200
    payload = await response.get_json()
    assert [item["_id"] for item in payload["servers"]] == ["mcp-legacy"]
    assert payload["servers"][0]["team_id"] == ""


@pytest.mark.asyncio
async def test_mcp_management_list_returns_authorization_status(client, monkeypatch):
    def deny(*_args, **_kwargs):
        raise backend_app.AccessControlError("Manage integrations permission is required")

    monkeypatch.setattr(backend_app, "_require_integration_catalog_access", deny)

    response = await client.get("/admin/mcp-servers?team_id=team-2")

    assert response.status_code == 403
    assert (await response.get_json())["error"] == (
        "Manage integrations permission is required"
    )


@pytest.mark.asyncio
async def test_azure_connection_test_reports_only_read_only_tools(client, monkeypatch):
    monkeypatch.setattr(
        backend_app, "_require_integration_catalog_access", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        backend_app,
        "get_mcp_server",
        lambda _server_id: {
            "_id": "azure-1",
            "team_id": "team-1",
            "name": "Azure inventory",
            "url": "https://azure-mcp.example.test/mcp",
            "vendor": "azure",
            "operation_mode": "read_only",
            "allowed_tools": [],
            "timeout_seconds": 60,
        },
    )
    monkeypatch.setattr(backend_app, "decrypt_mcp_headers", lambda _server: {})

    async def discover(_config):
        return [
            SimpleNamespace(name="list_resources", description="List resources"),
            SimpleNamespace(name="deploy_resource", description="Deploy resource"),
        ]

    monkeypatch.setattr(backend_app, "discover_mcp_tools", discover)

    response = await client.post("/admin/mcp-servers/azure-1/test")

    assert response.status_code == 200
    payload = await response.get_json()
    assert [item["name"] for item in payload["tools"]] == ["list_resources"]
    assert payload["blocked_tool_count"] == 1


@pytest.mark.asyncio
async def test_managed_azure_create_provisions_through_controller(client, monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(
        backend_app,
        "_require_integration_catalog_access",
        lambda *_args, **_kwargs: {"_id": "admin-1"},
    )
    monkeypatch.setattr(
        backend_app,
        "_require_system_admin",
        lambda *_args, **_kwargs: {"_id": "admin-1"},
    )
    created = {}
    stored = {}

    def insert(value):
        created.update(value)
        return {"_id": "e4948913-5c29-426f-a7a2-e3c688a24fd4", **value}

    monkeypatch.setattr(backend_app, "insert_mcp_server", insert)

    def update(_server_id, values):
        stored.update(values)
        return {
            "_id": "e4948913-5c29-426f-a7a2-e3c688a24fd4",
            "team_id": "team-1",
            "name": "Azure tenant A",
            "vendor": "azure",
            "category": "cloud_platform",
            "auth_type": "headers",
            "operation_mode": "read_only",
            "deployment_mode": "managed",
            "allowed_tools": [],
            "timeout_seconds": 60,
            **created,
            **stored,
        }

    monkeypatch.setattr(backend_app, "update_mcp_server", update)
    monkeypatch.setattr(
        backend_app,
        "insert_integration_lifecycle_event",
        lambda **_kwargs: None,
    )

    class Controller:
        async def provision_azure_mcp(self, request):
            assert request.azure_client_secret == "azure-secret"
            return {
                "status": "running",
                "url": "http://nexora-azure-mcp-e4948913-5c29-426f-a7a2-e3c688a24fd4:8080",
            }

    monkeypatch.setattr(backend_app, "IntegrationControllerClient", Controller)
    response = await client.post(
        "/admin/mcp-servers",
        json={
            "team_id": "team-1",
            "name": "Azure tenant A",
            "vendor": "azure",
            "deployment_mode": "managed",
            "azure_tenant_id": "11111111-1111-4111-8111-111111111111",
            "azure_client_id": "44444444-4444-4444-8444-444444444444",
            "azure_client_secret": "azure-secret",
            "azure_subscription_ids": ["55555555-5555-4555-8555-555555555555"],
            "enabled": True,
        },
    )

    assert response.status_code == 201
    payload = await response.get_json()
    assert payload["enabled"] is True
    assert payload["provisioning_status"] == "ready"
    assert payload["url"].startswith("http://nexora-azure-mcp-")
    assert payload["has_entra_client_secret"] is False
    assert payload["has_azure_client_secret"] is True
    assert "azure-secret" not in str(payload)


@pytest.mark.asyncio
async def test_managed_azure_rejects_unexpected_controller_target(monkeypatch):
    connection_id = "e4948913-5c29-426f-a7a2-e3c688a24fd4"
    monkeypatch.setattr(
        backend_app,
        "azure_mcp_runtime_config",
        lambda _server: {
            "azure_tenant_id": "tenant",
            "azure_client_id": "client",
            "azure_client_secret": "secret",
            "azure_subscription_ids": ("subscription",),
        },
    )

    class Controller:
        async def provision_azure_mcp(self, _request):
            return {"url": "http://169.254.169.254:8080/metadata"}

    monkeypatch.setattr(backend_app, "IntegrationControllerClient", Controller)

    with pytest.raises(
        backend_app.IntegrationControllerError,
        match="invalid Azure MCP URL",
    ):
        await backend_app._provision_managed_azure_mcp({"_id": connection_id})


@pytest.mark.asyncio
async def test_managed_azure_delete_is_accepted_when_controller_is_unavailable(
    client, monkeypatch
):
    connection_id = "e4948913-5c29-426f-a7a2-e3c688a24fd4"
    monkeypatch.setattr(
        backend_app,
        "get_mcp_server",
        lambda _server_id: {
            "_id": connection_id,
            "team_id": "team-1",
            "vendor": "azure",
            "deployment_mode": "managed",
        },
    )
    monkeypatch.setattr(
        backend_app,
        "_require_integration_catalog_access",
        lambda *_args, **_kwargs: {"_id": "admin-1"},
    )
    monkeypatch.setattr(
        backend_app,
        "_require_system_admin",
        lambda *_args, **_kwargs: {"_id": "admin-1"},
    )
    monkeypatch.setattr(
        backend_app,
        "get_database",
        lambda: SimpleNamespace(
            agents=SimpleNamespace(count_documents=lambda _query: 0)
        ),
    )

    class Controller:
        async def delete_azure_mcp(self, _server_id):
            raise backend_app.IntegrationControllerError("controller unavailable")

    deleted = []
    monkeypatch.setattr(backend_app, "IntegrationControllerClient", Controller)
    monkeypatch.setattr(
        backend_app,
        "soft_delete_mcp_server",
        lambda server_id, **kwargs: deleted.append((server_id, kwargs)) or True,
    )
    monkeypatch.setattr(
        backend_app,
        "insert_integration_lifecycle_event",
        lambda **_kwargs: None,
    )

    response = await client.delete(f"/admin/mcp-servers/{connection_id}")

    assert response.status_code == 202
    assert await response.get_json() == {"success": True, "cleanup_pending": True}
    assert deleted == [
        (
            connection_id,
            {
                "provisioning_status": "cleanup_pending",
                "provisioning_error": "controller unavailable",
            },
        )
    ]


@pytest.mark.asyncio
async def test_managed_azure_create_is_saved_for_retry_when_controller_is_unavailable(
    client, monkeypatch
):
    connection_id = "e4948913-5c29-426f-a7a2-e3c688a24fd4"
    normalized = {
        "team_id": "team-1",
        "name": "Azure tenant A",
        "vendor": "azure",
        "deployment_mode": "managed",
        "enabled": True,
        "provisioning_status": "pending",
    }
    monkeypatch.setattr(
        backend_app, "normalize_mcp_server_payload", lambda _body: dict(normalized)
    )
    monkeypatch.setattr(
        backend_app,
        "_require_integration_catalog_access",
        lambda *_args, **_kwargs: {"_id": "admin-1"},
    )
    monkeypatch.setattr(
        backend_app,
        "_require_system_admin",
        lambda *_args, **_kwargs: {"_id": "admin-1"},
    )
    monkeypatch.setattr(
        backend_app,
        "insert_mcp_server",
        lambda value: {"_id": connection_id, **value},
    )

    async def unavailable(_server):
        raise backend_app.IntegrationControllerError("controller unavailable")

    monkeypatch.setattr(backend_app, "_provision_managed_azure_mcp", unavailable)
    monkeypatch.setattr(
        backend_app,
        "update_mcp_server",
        lambda _server_id, values: {"_id": connection_id, **normalized, **values},
    )
    monkeypatch.setattr(
        backend_app,
        "insert_integration_lifecycle_event",
        lambda **_kwargs: None,
    )

    response = await client.post("/admin/mcp-servers", json={"ignored": True})

    assert response.status_code == 202
    payload = await response.get_json()
    assert payload["enabled"] is True
    assert payload["provisioning_status"] == "failed"
    assert payload["provisioning_error"] == "controller unavailable"


def test_mcp_server_update_keeps_existing_headers_when_blank(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    existing = normalize_mcp_server_payload(
        {
            "name": "DrawIO",
            "url": "https://mcp.example.test/mcp",
            "headers": {"X-Key": "secret"},
        }
    )

    updated = normalize_mcp_server_payload(
        {"name": "DrawIO 2", "url": "https://mcp.example.test/mcp"},
        existing=existing,
    )

    assert updated["headers_ciphertext"] == existing["headers_ciphertext"]


def test_datadog_preset_validates_endpoint_and_bearer_token(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    normalized = normalize_mcp_server_payload(
        {
            "name": "Datadog US1",
            "vendor": "datadog",
            "auth_type": "bearer",
            "url": "https://mcp.datadoghq.com/v1/mcp?toolsets=core,synthetics",
            "headers": {"Authorization": "Bearer datadog-secret"},
        }
    )

    assert normalized["vendor"] == "datadog"
    assert normalized["category"] == "observability"
    assert normalized["auth_type"] == "bearer"
    assert decrypt_mcp_headers(
        {"headers_ciphertext": normalized["headers_ciphertext"]}
    ) == {"Authorization": "Bearer datadog-secret"}


@pytest.mark.parametrize(
    ("url", "headers"),
    [
        ("https://example.com/v1/mcp", {"Authorization": "Bearer secret"}),
        ("https://mcp.datadoghq.com/old/mcp", {"Authorization": "Bearer secret"}),
        ("https://mcp.datadoghq.com/v1/mcp", {"Authorization": "secret"}),
    ],
)
def test_datadog_preset_rejects_unsafe_or_invalid_configuration(
    monkeypatch, url, headers
):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(ValueError):
        normalize_mcp_server_payload(
            {
                "name": "Datadog",
                "vendor": "datadog",
                "auth_type": "bearer",
                "url": url,
                "headers": headers,
            }
        )


@pytest.mark.parametrize(
    ("vendor", "url"),
    [
        ("atlassian", "https://mcp.atlassian.com/v1/mcp/authv2"),
        ("servicenow", "https://example.service-now.com/api/x_example/mcp"),
    ],
)
def test_hosted_business_mcp_presets_require_bearer_tokens(monkeypatch, vendor, url):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    normalized = normalize_mcp_server_payload(
        {
            "name": vendor,
            "vendor": vendor,
            "url": url,
            "auth_type": "bearer",
            "headers": {"Authorization": "Bearer oauth-secret"},
        }
    )

    assert normalized["category"] == "business_workflows"
    assert normalized["deployment_mode"] == "external"
    assert decrypt_mcp_headers(normalized) == {
        "Authorization": "Bearer oauth-secret"
    }


@pytest.mark.parametrize(
    ("vendor", "url"),
    [
        ("atlassian", "https://example.com/v1/mcp/authv2"),
        ("servicenow", "http://example.service-now.com/api/mcp"),
        ("servicenow", "https://example.com/api/mcp"),
    ],
)
def test_hosted_business_mcp_presets_reject_untrusted_endpoints(
    monkeypatch, vendor, url
):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(ValueError):
        normalize_mcp_server_payload(
            {
                "name": vendor,
                "vendor": vendor,
                "url": url,
                "auth_type": "bearer",
                "headers": {"Authorization": "Bearer oauth-secret"},
            }
        )
