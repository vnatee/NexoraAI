from datetime import datetime, timezone

import pytest

import app as backend_app
from core.usage_quotas import UsageQuotaPolicy


def _mock_response_dependencies(monkeypatch):
    policy = UsageQuotaPolicy(enabled=True, monthly_llm_tokens=100)
    monkeypatch.setattr(backend_app, "get_quota_settings", lambda *_args: policy.serialize())
    monkeypatch.setattr(backend_app, "effective_quota_settings", lambda *_args: (policy, {}))
    monkeypatch.setattr(backend_app, "current_usage", lambda *_args: {
        "monthly_llm_tokens": 85,
        "monthly_document_pages": 0,
    })
    monkeypatch.setattr(backend_app, "current_llm_rule_usages", lambda *_args: [])
    monkeypatch.setattr(backend_app, "quota_status", lambda *_args: [{
        "kind": "llm_tokens", "label": "Overall LLM tokens", "used": 85,
        "reserved": 0, "limit": 100, "percentage": 85.0, "severity": "warning",
    }])
    monkeypatch.setattr(backend_app, "list_quota_audit_events", lambda *_args: [{
        "_id": "event-1", "event_type": "quota_threshold", "level": "system",
        "subject_id": "", "limit": 100, "projected": 85, "threshold": 80,
        "created_at": datetime(2026, 9, 3, tzinfo=timezone.utc),
    }])


@pytest.mark.asyncio
async def test_system_quota_response_exposes_safe_status_and_audit(client, monkeypatch):
    monkeypatch.setattr(backend_app, "_require_system_admin", lambda _claims: {"_id": "admin"})
    _mock_response_dependencies(monkeypatch)

    response = await client.get("/admin/quota-settings")

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload["status"][0]["severity"] == "warning"
    assert payload["audit_events"][0]["created_at"].startswith("2026-09-03")
    assert "prompt" not in str(payload).lower()


@pytest.mark.asyncio
async def test_team_quota_route_requires_manage_team_permissions(client, monkeypatch):
    observed = []
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda _claims, team_id, *, permission=None: observed.append((team_id, permission)),
    )
    _mock_response_dependencies(monkeypatch)

    response = await client.get("/teams/team-1/quota-settings")

    assert response.status_code == 200
    assert observed == [("team-1", "Manage team permissions")]


@pytest.mark.asyncio
async def test_team_member_quota_route_requires_membership_and_team_permission(client, monkeypatch):
    observed = []
    def require_team(_claims, team_id, *, permission=None):
        observed.append((team_id, permission))
        return {"_id": "admin"}, {"_id": team_id, "user_id": ["user-1"]}

    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        require_team,
    )
    monkeypatch.setattr(backend_app, "get_user_by_id", lambda user_id: {"_id": user_id})
    _mock_response_dependencies(monkeypatch)
    monkeypatch.setattr(
        backend_app,
        "team_member_quota_policy",
        lambda *_args: (UsageQuotaPolicy(enabled=True, monthly_llm_tokens=50), "team_default"),
    )

    response = await client.get("/teams/team-1/users/user-1/quota-settings")

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload["member_limit_source"] == "team_default"
    assert payload["effective_member_limit"] == 50
    assert observed == [("team-1", "Manage team permissions")]


@pytest.mark.asyncio
async def test_team_member_quota_route_rejects_non_member(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *_args, **_kwargs: ({"_id": "admin"}, {"_id": "team-1", "user_id": []}),
    )

    response = await client.get("/teams/team-1/users/user-1/quota-settings")

    assert response.status_code == 404
    payload = await response.get_json()
    assert "not a member" in str(payload).lower()
