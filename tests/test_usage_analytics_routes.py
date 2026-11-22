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


@pytest.mark.asyncio
async def test_usage_csv_export_reuses_personal_scope_and_filters(client, monkeypatch):
    monkeypatch.setattr(app_module, "_application_user_for_claims", lambda _claims: {"_id": "user-1", "active": True})
    captured = {}

    def export_csv(query, **kwargs):
        captured["query"] = query
        captured.update(kwargs)
        return "timestamp,estimated_cost_usd\n"

    monkeypatch.setattr(app_module, "usage_cost_csv", export_csv)
    response = await client.get(
        "/usage-analytics/export.csv?scope=personal&user_id=another-user&provider=openai&model=gpt-test"
    )

    assert response.status_code == 200
    assert captured["query"]["user._id"] == "user-1"
    assert captured["provider"] == "openai"
    assert captured["model"] == "gpt-test"
    assert response.headers["Cache-Control"] == "no-store"
    assert "attachment" in response.headers["Content-Disposition"]


@pytest.mark.asyncio
async def test_price_catalog_requires_system_admin(client, monkeypatch):
    monkeypatch.setattr(app_module, "_is_system_admin", lambda _claims: False)

    response = await client.get("/usage-price-catalog")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_system_admin_can_create_price_version(client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "_application_user_for_claims",
        lambda _claims: {"_id": "admin-1", "active": True, "is_sys_admin": True},
    )
    captured = {}

    def create_profile(payload, *, actor_id):
        captured.update(payload)
        captured["actor_id"] = actor_id
        return {"_id": "price-1", **payload, "enabled": True}

    monkeypatch.setattr(app_module, "create_price_profile", create_profile)
    response = await client.post("/usage-price-catalog", json={
        "name": "Contract v1", "pricing_type": "token", "provider": "openai",
        "effective_from": "2026-01-01", "input_usd_per_million": 1,
        "cached_input_usd_per_million": 0.25, "output_usd_per_million": 4,
    })

    assert response.status_code == 201
    assert captured["actor_id"] == "admin-1"
    assert captured["name"] == "Contract v1"
