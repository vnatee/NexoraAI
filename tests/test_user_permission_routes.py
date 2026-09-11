import pytest

import app as backend_app


def _user(user_id: str, *, is_sys_admin: bool = False):
    return {
        "_id": user_id,
        "active": True,
        "is_sys_admin": is_sys_admin,
    }


@pytest.mark.asyncio
async def test_system_admin_promotion_does_not_require_permission_ids(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_require_user_management_target",
        lambda _claims, _user_id, destructive=False: (
            _user("admin", is_sys_admin=True),
            _user("target"),
        ),
    )
    updated = {}
    monkeypatch.setattr(
        backend_app,
        "update_user",
        lambda user_id, **values: updated.update({"user_id": user_id, **values}),
    )

    response = await client.post(
        "/create_edit_user_permissions",
        json={
            "user_id": "target",
            "team_id": None,
            "permission_id": None,
            "is_sys_admin": True,
        },
    )

    assert response.status_code == 200
    assert updated == {"user_id": "target", "is_sys_admin": True}


@pytest.mark.asyncio
async def test_delegated_user_manager_cannot_promote_system_admin(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_require_user_management_target",
        lambda _claims, _user_id, destructive=False: (
            _user("manager"),
            _user("target"),
        ),
    )
    monkeypatch.setattr(
        backend_app,
        "update_user",
        lambda *_args, **_kwargs: pytest.fail("promotion must be rejected before update"),
    )

    response = await client.post(
        "/create_edit_user_permissions",
        json={
            "user_id": "target",
            "team_id": None,
            "permission_id": None,
            "is_sys_admin": True,
        },
    )
    payload = await response.get_json()

    assert response.status_code == 403
    assert payload["error"] == "Only a system administrator can change the System Admin role"
