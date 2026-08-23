import pytest

import app as app_module
import decorators

from core.effective_access import (
    AccessControlError,
    DATA_GROUP_ACCESS_SELECTED_USERS,
    DATA_GROUP_ACCESS_TEAM,
    resolve_effective_access,
)


def _user(user_id="user-1", **updates):
    return {"_id": user_id, "active": True, "is_sys_admin": False, **updates}


def _team(**updates):
    return {
        "_id": "team-1",
        "name": "DIG",
        "user_id": ["user-1"],
        "agent_id": ["agent-1"],
        "data_group_id": ["default", "datadog", "private"],
        **updates,
    }


def _groups():
    return [
        {"_id": "default", "name": "default", "user_id": []},
        {"_id": "datadog", "name": "DataDog", "user_id": ["user-1"]},
        {"_id": "private", "name": "Private", "user_id": ["user-2"]},
    ]


def test_effective_access_exposes_team_and_selected_user_groups():
    access = resolve_effective_access(
        user=_user(),
        team=_team(),
        data_groups=_groups(),
        requested_data_group_ids=["datadog"],
        requested_scopes=["personal"],
        agent_id="agent-1",
    )

    assert [item.id for item in access.data_groups] == ["default", "datadog"]
    assert access.data_groups[0].access_mode == DATA_GROUP_ACCESS_TEAM
    assert access.data_groups[1].access_mode == DATA_GROUP_ACCESS_SELECTED_USERS
    assert access.selected_data_group_ids == ("datadog",)


def test_effective_access_rejects_cross_team_group_and_agent_spoofing():
    with pytest.raises(AccessControlError, match="data groups are not available"):
        resolve_effective_access(
            user=_user(),
            team=_team(),
            data_groups=_groups(),
            requested_data_group_ids=["private"],
        )

    with pytest.raises(AccessControlError, match="agent does not belong"):
        resolve_effective_access(
            user=_user(),
            team=_team(),
            data_groups=_groups(),
            agent_id="agent-from-another-team",
        )


def test_effective_access_rejects_non_member_and_unknown_scope():
    with pytest.raises(AccessControlError, match="not a member"):
        resolve_effective_access(user=_user("outsider"), team=_team(), data_groups=_groups())

    with pytest.raises(AccessControlError, match="unsupported scope"):
        resolve_effective_access(
            user=_user(),
            team=_team(),
            data_groups=_groups(),
            requested_scopes=["all_tenants"],
        )


def test_system_admin_can_resolve_every_team_group_but_selection_remains_explicit():
    access = resolve_effective_access(
        user=_user("admin", is_sys_admin=True),
        team=_team(user_id=[]),
        data_groups=_groups(),
        requested_data_group_ids=[],
    )

    assert [item.id for item in access.data_groups] == ["default", "datadog", "private"]
    assert access.selected_data_group_ids == ()


def test_request_claims_are_rebuilt_from_server_side_access(monkeypatch):
    monkeypatch.setattr(app_module, "get_user_by_ad_email", lambda _email: _user())
    monkeypatch.setattr(app_module, "get_team_by_id", lambda _team_id: _team())
    groups = {item["_id"]: item for item in _groups()}
    monkeypatch.setattr(app_module, "get_data_group_by_id", lambda group_id: groups.get(group_id))

    original_claims = {"preferred_username": "user@example.com", "data_groups_id": ["untrusted"]}
    claims = app_module._authorized_request_claims(
        {
            "team_id": "team-1",
            "data_groups_id": ["datadog"],
            "selected_scopes": ["personal"],
        },
        original_claims,
        agent_id="agent-1",
    )

    assert original_claims["data_groups_id"] == ["untrusted"]
    assert claims["team_id"] == "team-1"
    assert claims["data_groups_id"] == ["datadog"]
    assert claims["selected_scopes"] == ["personal"]
    assert claims["application_user_id"] == "user-1"


def test_request_claims_reject_group_from_another_access_boundary(monkeypatch):
    monkeypatch.setattr(app_module, "get_user_by_ad_email", lambda _email: _user())
    monkeypatch.setattr(app_module, "get_team_by_id", lambda _team_id: _team())
    groups = {item["_id"]: item for item in _groups()}
    monkeypatch.setattr(app_module, "get_data_group_by_id", lambda group_id: groups.get(group_id))

    with pytest.raises(AccessControlError, match="data groups are not available"):
        app_module._authorized_request_claims(
            {"team_id": "team-1", "data_groups_id": ["private"]},
            {"preferred_username": "user@example.com"},
            agent_id="agent-1",
        )


def test_data_group_access_requires_selected_users_to_be_team_members():
    with pytest.raises(AccessControlError, match="not a member"):
        app_module._normalize_data_group_access(
            access_mode="selected_users",
            users_id=["outsider"],
            team=_team(),
        )

    mode, users = app_module._normalize_data_group_access(
        access_mode="team",
        users_id=["user-1"],
        team=_team(),
    )
    assert mode == "team"
    assert users == []


def test_team_role_cannot_receive_system_permissions(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "get_all_permissions",
        lambda: [
            {"_id": "team-permission", "type": "Team Permissions"},
            {"_id": "system-permission", "type": "System Permissions"},
        ],
    )

    assert app_module._validate_permission_ids(
        ["team-permission"], permission_type="team"
    ) == ["team-permission"]
    with pytest.raises(AccessControlError, match="Only team permissions"):
        app_module._validate_permission_ids(
            ["system-permission"], permission_type="team"
        )


def test_system_permission_uses_application_permissions_not_token_claims(monkeypatch):
    monkeypatch.setattr(app_module, "get_user_by_ad_email", lambda _email: _user())
    monkeypatch.setattr(
        app_module,
        "get_user_permission_by_user_team_id",
        lambda user_id, team_id: [
            {"user_id": user_id, "team_id": team_id, "permission_id": ["manage-users"]}
        ],
    )
    monkeypatch.setattr(
        app_module,
        "get_all_permissions",
        lambda: [{"_id": "manage-users", "name": "Manage users"}],
    )

    assert app_module._require_system_permission(
        {"preferred_username": "user@example.com", "roles": ["untrusted-admin"]},
        "Manage users",
    )["_id"] == "user-1"

    with pytest.raises(AccessControlError, match="Manage teams"):
        app_module._require_system_permission(
            {"preferred_username": "user@example.com"}, "Manage teams"
        )


@pytest.mark.asyncio
async def test_create_team_returns_new_team_and_adds_creator(client, monkeypatch):
    class InsertResult:
        inserted_id = "team-new"

    monkeypatch.setattr(
        app_module,
        "_require_system_permission",
        lambda _claims, _permission: _user("creator", is_sys_admin=True),
    )
    monkeypatch.setattr(app_module, "insert_agent", lambda *_args: (object(), "agent-new"))
    monkeypatch.setattr(app_module, "insert_data_group", lambda *_args: (object(), "group-new"))

    captured = {}

    def insert_team(name, data_group_ids, agent_ids, user_ids, waiting):
        captured.update(
            {
                "name": name,
                "data_group_ids": data_group_ids,
                "agent_ids": agent_ids,
                "user_ids": user_ids,
                "waiting": waiting,
            }
        )
        return InsertResult()

    monkeypatch.setattr(app_module, "insert_team", insert_team)

    response = await client.post("/create_team", json={"team_name": " New Team "})

    assert response.status_code == 200
    assert await response.get_json() == {
        "success": "Create team New Team success",
        "team": {"_id": "team-new", "name": "New Team", "permissions": []},
    }
    assert captured == {
        "name": "New Team",
        "data_group_ids": ["group-new"],
        "agent_ids": ["agent-new"],
        "user_ids": ["creator"],
        "waiting": [],
    }


def test_delegated_user_manager_can_view_but_not_manage_system_admin(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "_require_system_permission",
        lambda _claims, _permission: _user("manager"),
    )
    monkeypatch.setattr(
        app_module,
        "get_user_by_id",
        lambda _user_id: _user("admin", is_sys_admin=True),
    )

    with pytest.raises(AccessControlError, match="Only a system administrator"):
        app_module._require_user_management_target({}, "admin")


def test_system_admin_cannot_remove_self_or_last_admin(monkeypatch):
    actor = _user("admin", is_sys_admin=True)
    monkeypatch.setattr(
        app_module,
        "_require_system_permission",
        lambda _claims, _permission: actor,
    )
    monkeypatch.setattr(app_module, "get_user_by_id", lambda _user_id: actor)

    with pytest.raises(AccessControlError, match="their own account"):
        app_module._require_user_management_target({}, "admin", destructive=True)

    other = _user("other-admin", is_sys_admin=True)
    monkeypatch.setattr(app_module, "get_user_by_id", lambda _user_id: other)
    monkeypatch.setattr(app_module, "get_all_user_by_is_sys_admin", lambda _value: [other])
    with pytest.raises(AccessControlError, match="last active"):
        app_module._require_user_management_target({}, "other-admin", destructive=True)


def test_team_content_path_uses_effective_application_data_groups(monkeypatch):
    team_id = "9e2fa6ed-769b-4809-84e8-8c1636c08f2b"
    monkeypatch.setattr(
        decorators, "get_team_by_id", lambda _team_id: _team(_id=team_id)
    )
    monkeypatch.setattr(decorators, "get_user_by_ad_email", lambda _email: _user())
    groups = {item["_id"]: item for item in _groups()}
    monkeypatch.setattr(decorators, "get_data_group_by_id", lambda group_id: groups.get(group_id))

    claims = decorators._content_access_claims(
        f"{team_id}|ProductBrief.pdf#page=1",
        {"preferred_username": "user@example.com", "groups": ["entra-group"]},
    )

    assert claims["team_id"] == team_id
    assert claims["data_groups_id"] == ["default", "datadog"]
    assert claims["selected_scopes"] == []
    assert claims["groups"] == ["entra-group"]


def test_non_team_content_path_keeps_standard_auth_claims(monkeypatch):
    monkeypatch.setattr(decorators, "get_team_by_id", lambda _team_id: None)
    original = {"preferred_username": "user@example.com", "oid": "oid-1"}

    assert decorators._content_access_claims("public.pdf", original) is original
