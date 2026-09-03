from datetime import datetime, timezone

import pytest

import app as app_module
from core.effective_access import AccessControlError


def _result():
    return {
        "overview": {},
        "timeline": [],
        "breakdowns": {},
        "document_providers": [],
        "filter_options": {},
    }


@pytest.mark.asyncio
async def test_usage_analytics_system_scope_requires_permission_and_applies_filters(client, monkeypatch):
    monkeypatch.setattr(app_module, "_application_user_for_claims", lambda _claims: {"_id": "admin", "active": True})
    checked = []
    monkeypatch.setattr(app_module, "_require_system_permission", lambda _claims, permission: checked.append(permission))
    captured = {}

    def get_analytics(query, **kwargs):
        captured["query"] = query
        captured.update(kwargs)
        return _result()

    monkeypatch.setattr(app_module, "get_usage_analytics", get_analytics)
    response = await client.get(
        "/usage-analytics?scope=system&team_id=team-1&user_id=user-1&bucket=week&from=2026-08-01&to=2026-08-31"
    )

    assert response.status_code == 200
    assert checked == ["View system dashboard"]
    assert captured["query"]["group._id"] == "team-1"
    assert captured["query"]["user._id"] == "user-1"
    assert captured["bucket"] == "week"
    assert captured["query"]["create_at"]["$gte"] == datetime(2026, 8, 1, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_usage_analytics_forwards_document_filters(client, monkeypatch):
    monkeypatch.setattr(app_module, "_application_user_for_claims", lambda _claims: {"_id": "admin", "active": True})
    monkeypatch.setattr(app_module, "_require_system_permission", lambda *_args, **_kwargs: None)
    captured = {}

    def get_analytics(_query, **kwargs):
        captured.update(kwargs)
        return _result()

    monkeypatch.setattr(app_module, "get_usage_analytics", get_analytics)
    response = await client.get(
        "/usage-analytics?scope=system&profile_id=profile-1&file_type=.pdf&document_scope=team"
    )

    assert response.status_code == 200
    assert captured["profile_id"] == "profile-1"
    assert captured["file_type"] == ".pdf"
    assert captured["document_scope"] == "team"


@pytest.mark.asyncio
async def test_usage_analytics_team_scope_does_not_fall_back_to_system_access(client, monkeypatch):
    monkeypatch.setattr(app_module, "_application_user_for_claims", lambda _claims: {"_id": "user-1", "active": True})
    monkeypatch.setattr(
        app_module,
        "_require_team_access",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AccessControlError("View team dashboard permission is required")),
    )

    response = await client.get("/usage-analytics?scope=team&team_id=team-1")

    assert response.status_code == 403
    assert (await response.get_json())["error"] == "View team dashboard permission is required"


@pytest.mark.asyncio
async def test_usage_analytics_personal_scope_forces_signed_in_user(client, monkeypatch):
    monkeypatch.setattr(app_module, "_application_user_for_claims", lambda _claims: {"_id": "user-1", "active": True})
    captured = {}

    def get_analytics(query, **kwargs):
        captured.update(query)
        return _result()

    monkeypatch.setattr(app_module, "get_usage_analytics", get_analytics)
    response = await client.get("/usage-analytics?scope=personal&user_id=another-user")

    assert response.status_code == 200
    assert captured["user._id"] == "user-1"
