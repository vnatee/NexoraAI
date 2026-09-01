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

    def count_documents(self, query):
        return sum(
            1
            for document in self.documents.values()
            if all(document.get(key) == value for key, value in query.items())
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
