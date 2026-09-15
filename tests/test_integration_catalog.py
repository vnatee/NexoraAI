import pytest

import app as backend_app
from core.effective_access import AccessControlError
from mongo_table_connecters import integration_catalog


class _UpdateResult:
    def __init__(self, modified_count: int):
        self.modified_count = modified_count


class _Collection:
    def __init__(self, documents=None):
        self.documents = {item["_id"]: dict(item) for item in (documents or [])}

    def find_one(self, query):
        document = self.documents.get(query.get("_id"))
        if not document or document.get("delete_at") is not None:
            return None
        return dict(document)

    @staticmethod
    def _value_at_path(document, path):
        value = document
        for part in path.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    @classmethod
    def _matches(cls, document, query):
        for key, expected in query.items():
            actual = cls._value_at_path(document, key)
            if isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
            elif isinstance(actual, list):
                if expected not in actual:
                    return False
            elif actual != expected:
                return False
        return True

    def find(self, query):
        return [
            dict(document)
            for document in self.documents.values()
            if self._matches(document, query)
        ]

    def distinct(self, field, query):
        return list(
            {
                self._value_at_path(document, field)
                for document in self.documents.values()
                if self._matches(document, query)
                and self._value_at_path(document, field) is not None
            }
        )

    def count_documents(self, query):
        return sum(
            1
            for document in self.documents.values()
            if self._matches(document, query)
        )

    def update_one(self, query, update):
        document = self.documents.get(query.get("_id"))
        allowed_team_ids = query.get("team_id", {}).get("$in", [])
        if not document or document.get("team_id") not in allowed_team_ids:
            return _UpdateResult(0)
        document.update(update["$set"])
        return _UpdateResult(1)


class _Database:
    def __init__(self, collections):
        self.collections = collections

    def __getitem__(self, name):
        return self.collections.setdefault(name, _Collection())


def test_assign_unassigned_integration_to_team(monkeypatch):
    database = _Database(
        {
            "external_apis": _Collection(
                [{"_id": "rest-1", "team_id": "", "delete_at": None}]
            ),
            "agent_bindings": _Collection(),
        }
    )
    monkeypatch.setattr(integration_catalog, "get_database", lambda: database)

    result = integration_catalog.assign_unassigned_integration(
        "rest_api", "rest-1", "team-1"
    )

    assert result == {
        "integration_id": "rest-1",
        "integration_type": "rest_api",
        "team_id": "team-1",
    }
    assert database["external_apis"].documents["rest-1"]["team_id"] == "team-1"


def test_assignment_rejects_an_already_assigned_integration(monkeypatch):
    database = _Database(
        {
            "mail_connections": _Collection(
                [{"_id": "mail-1", "team_id": "team-1", "delete_at": None}]
            )
        }
    )
    monkeypatch.setattr(integration_catalog, "get_database", lambda: database)

    with pytest.raises(
        integration_catalog.IntegrationAssignmentError, match="already assigned"
    ):
        integration_catalog.assign_unassigned_integration(
            "mail", "mail-1", "team-2"
        )


def test_assignment_rejects_integration_with_agent_binding(monkeypatch):
    database = _Database(
        {
            "external_databases": _Collection(
                [{"_id": "db-1", "team_id": None, "delete_at": None}]
            ),
            "database_bindings": _Collection(
                [
                    {
                        "_id": "binding-1",
                        "integration_id": "db-1",
                        "delete_at": None,
                    }
                ]
            ),
        }
    )
    monkeypatch.setattr(integration_catalog, "get_database", lambda: database)

    with pytest.raises(
        integration_catalog.IntegrationAssignmentError, match="Remove Agent bindings"
    ):
        integration_catalog.assign_unassigned_integration(
            "database", "db-1", "team-1"
        )


def test_assign_unassigned_mcp_connection_to_team(monkeypatch):
    database = _Database(
        {
            "mcp_servers": _Collection(
                [{"_id": "mcp-1", "team_id": "", "delete_at": None}]
            ),
            "agents": _Collection(),
        }
    )
    monkeypatch.setattr(integration_catalog, "get_database", lambda: database)

    result = integration_catalog.assign_unassigned_integration(
        "mcp", "mcp-1", "team-1"
    )

    assert result["team_id"] == "team-1"
    assert database["mcp_servers"].documents["mcp-1"]["team_id"] == "team-1"
    assert "update_at" in database["mcp_servers"].documents["mcp-1"]


def test_assign_unassigned_business_document_connection_to_team(monkeypatch):
    database = _Database(
        {
            "business_document_connections": _Collection(
                [{"_id": "documents-1", "team_id": "", "delete_at": None}]
            ),
            "business_document_bindings": _Collection(),
        }
    )
    monkeypatch.setattr(integration_catalog, "get_database", lambda: database)

    result = integration_catalog.assign_unassigned_integration(
        "business_documents", "documents-1", "team-1"
    )

    assert result["team_id"] == "team-1"
    assert database["business_document_connections"].documents["documents-1"]["team_id"] == "team-1"


def test_unified_connection_projection_reads_legacy_collections_without_secrets(
    monkeypatch,
):
    database = _Database(
        {
            "mcp_servers": _Collection(
                [
                    {
                        "_id": "mcp-1",
                        "team_id": "team-1",
                        "name": "Jira",
                        "vendor": "atlassian",
                        "url": "https://mcp.atlassian.com/v1/mcp/authv2",
                        "headers_ciphertext": "secret",
                        "enabled": True,
                        "provisioning_status": "external",
                        "delete_at": None,
                    }
                ]
            ),
            "business_document_connections": _Collection(
                [
                    {
                        "_id": "docs-1",
                        "team_id": "team-1",
                        "name": "Sales SharePoint",
                        "provider": "microsoft365",
                        "public_config": {"drive_id": "drive-1"},
                        "secrets_ciphertext": "secret",
                        "enabled": True,
                        "delete_at": None,
                    }
                ]
            ),
            "agents": _Collection(
                [
                    {
                        "_id": "agent-1",
                        "delete_at": None,
                        "config": {"tool_settings": {"mcp_server_ids": ["mcp-1"]}},
                    }
                ]
            ),
            "business_document_bindings": _Collection(
                [
                    {
                        "_id": "binding-1",
                        "agent_id": "agent-1",
                        "connection_id": "docs-1",
                        "delete_at": None,
                    }
                ]
            ),
        }
    )
    monkeypatch.setattr(integration_catalog, "get_database", lambda: database)

    connections = integration_catalog.list_integration_connections("team-1")

    assert [(item["id"], item["connection_type"]) for item in connections] == [
        ("mcp-1", "mcp"),
        ("docs-1", "native"),
    ]
    assert connections[0]["agent_usage_count"] == 1
    assert connections[1]["agent_usage_count"] == 1
    assert "ciphertext" not in str(connections)


def test_unified_binding_projection_includes_legacy_mcp_and_native_bindings(
    monkeypatch,
):
    database = _Database(
        {
            "mail_bindings": _Collection(
                [
                    {
                        "_id": "mail-binding-1",
                        "agent_id": "agent-1",
                        "email_id": "mail-1",
                        "enabled": True,
                        "delete_at": None,
                    }
                ]
            )
        }
    )
    monkeypatch.setattr(integration_catalog, "get_database", lambda: database)

    bindings = integration_catalog.list_agent_integration_bindings(
        "agent-1",
        agent_document={
            "_id": "agent-1",
            "config": {"tool_settings": {"mcp_server_ids": ["mcp-1"]}},
        },
    )

    assert {(item["kind"], item["connection_id"]) for item in bindings} == {
        ("mail", "mail-1"),
        ("mcp", "mcp-1"),
    }


def test_mcp_assignment_rejects_connection_used_by_legacy_agent(monkeypatch):
    database = _Database(
        {
            "mcp_servers": _Collection(
                [{"_id": "mcp-1", "team_id": "", "delete_at": None}]
            ),
            "agents": _Collection(
                [
                    {
                        "_id": "agent-1",
                        "delete_at": None,
                        "config": {"tool_settings": {"mcp_server_ids": ["mcp-1"]}},
                    }
                ]
            ),
        }
    )
    monkeypatch.setattr(integration_catalog, "get_database", lambda: database)

    with pytest.raises(
        integration_catalog.IntegrationAssignmentError, match="Remove Agent bindings"
    ):
        integration_catalog.assign_unassigned_integration(
            "mcp", "mcp-1", "team-1"
        )


def test_unassigned_catalog_requires_system_admin(monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_application_user_for_claims",
        lambda _claims: {"_id": "user-1", "active": True, "is_sys_admin": False},
    )

    with pytest.raises(AccessControlError, match="system administrator"):
        backend_app._require_integration_catalog_access({}, "")


def test_team_catalog_delegates_to_team_permission_check(monkeypatch):
    calls = []
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda claims, team_id, permission=None: calls.append(
            (claims, team_id, permission)
        )
        or ({"_id": "user-1"}, {"_id": team_id}),
    )

    backend_app._require_integration_catalog_access({"sub": "user-1"}, "team-1")

    assert calls == [({"sub": "user-1"}, "team-1", "Manage integrations")]


@pytest.mark.asyncio
async def test_unified_connection_endpoint_is_team_scoped(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        backend_app,
        "_require_integration_catalog_access",
        lambda claims, team_id, **_kwargs: calls.append((claims, team_id)),
    )
    monkeypatch.setattr(
        backend_app,
        "list_integration_connections",
        lambda team_id: [
            {
                "id": "mcp-1",
                "kind": "mcp",
                "connection_type": "mcp",
                "provider": "atlassian",
                "name": "Jira",
                "team_id": team_id,
                "enabled": True,
                "status": "enabled",
                "detail": "https://mcp.atlassian.com/v1/mcp/authv2",
                "agent_usage_count": 1,
            }
        ],
    )

    response = await client.get("/admin/integration-connections?team_id=team-1")

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload["connections"][0]["team_id"] == "team-1"
    assert calls[0][1] == "team-1"


def test_safe_binding_catalog_allows_agent_manager(monkeypatch):
    calls = []

    def require_team_access(claims, team_id, permission=None):
        calls.append(permission)
        if permission == "Manage integrations":
            raise AccessControlError("Manage integrations permission is required")
        return {"_id": "user-1"}, {"_id": team_id}

    monkeypatch.setattr(backend_app, "_require_team_access", require_team_access)

    backend_app._require_integration_catalog_access(
        {"sub": "user-1"}, "team-1", allow_agent_management=True
    )

    assert calls == ["Manage integrations", "Manage agents"]


@pytest.mark.parametrize(
    ("integration_team_id", "expected_message"),
    [("", "not assigned"), ("team-2", "not assigned")],
)
def test_agent_binding_rejects_unassigned_or_cross_team_integration(
    monkeypatch, integration_team_id, expected_message
):
    monkeypatch.setattr(
        backend_app,
        "get_team_by_agent_id",
        lambda _agent_id: {"_id": "team-1"},
    )

    with pytest.raises(AccessControlError, match=expected_message):
        backend_app._require_agent_integration_team(
            "agent-1", {"_id": "integration-1", "team_id": integration_team_id}
        )
