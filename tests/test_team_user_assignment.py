import pytest

import app as backend_app


def _user(user_id: str, **updates):
    return {
        "_id": user_id,
        "active": True,
        "is_sys_admin": False,
        "ad_email": f"{user_id}@example.com",
        "email": f"{user_id}@example.com",
        "employee_id": user_id,
        "first_name": user_id.title(),
        "last_name": "User",
        "tel": "",
        **updates,
    }


@pytest.mark.asyncio
async def test_available_team_users_includes_local_users_and_excludes_members(client, monkeypatch):
    permissions = []
    team = {"_id": "team-1", "name": "Team 1", "user_id": ["member"]}
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda _claims, _team_id, permission=None: (
            permissions.append(permission) or _user("admin"),
            team,
        ),
    )
    monkeypatch.setattr(
        backend_app,
        "get_all_user_by_is_sys_admin",
        lambda _is_admin: [
            _user("member"),
            _user("local-user", created_by_auth_provider="local"),
            _user("disabled", active=False),
        ],
    )
    monkeypatch.setattr(
        backend_app,
        "list_local_identities_by_user_ids",
        lambda user_ids: {"local-user": {"username": "local.operator"}},
    )

    response = await client.get("/teams/team-1/available-users")
    payload = await response.get_json()

    assert response.status_code == 200
    assert permissions == ["Manage team users"]
    assert payload == {
        "users": [
            {
                "_id": "local-user",
                "active": True,
                "ad_email": "local-user@example.com",
                "email": "local-user@example.com",
                "employee_id": "local-user",
                "first_name": "Local-User",
                "last_name": "User",
                "tel": "",
                "local_username": "local.operator",
                "auth_providers": ["local"],
            }
        ]
    }


@pytest.mark.asyncio
async def test_insert_team_users_accepts_active_local_user(client, monkeypatch):
    team = {"_id": "team-1", "name": "Team 1", "user_id": ["member"]}
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda _claims, _team_id, permission=None: (_user("admin"), team),
    )
    monkeypatch.setattr(
        backend_app,
        "get_all_user_by_is_sys_admin",
        lambda _is_admin: [_user("local-user", created_by_auth_provider="local")],
    )
    saved = {}
    monkeypatch.setattr(
        backend_app,
        "update_team",
        lambda **values: saved.update(values),
    )

    response = await client.post(
        "/insert_team_users",
        json={"team_id": "team-1", "user_id": ["local-user"]},
    )

    assert response.status_code == 200
    assert saved == {"team_id": "team-1", "user_id": ["member", "local-user"]}
