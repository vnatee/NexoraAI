import pytest

import app as backend_app


@pytest.mark.asyncio
async def test_permission_bootstrap_adds_missing_permissions_idempotently(monkeypatch):
    existing = {"Manage teams"}
    created: list[tuple[str, str]] = []

    monkeypatch.setattr(
        backend_app,
        "get_permission_by_name",
        lambda name: {"name": name} if name in existing else None,
    )

    def insert(name: str, permission_type: str):
        created.append((name, permission_type))
        existing.add(name)

    monkeypatch.setattr(backend_app, "insert_permission", insert)

    assert await backend_app.insert_permissions() is True
    assert ("Manage external channels", "System Permissions") in created
    assert all(name != "Manage teams" for name, _permission_type in created)

    first_run_count = len(created)
    assert await backend_app.insert_permissions() is True
    assert len(created) == first_run_count

    assert "Manage global uploads" in existing
