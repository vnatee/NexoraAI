from __future__ import annotations

import asyncio

import pytest

import app as backend_app
from core import system_health


def _matches(document, query):
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif actual != expected:
            return False
    return True


class _Collection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def count_documents(self, query):
        return sum(1 for document in self.documents if _matches(document, query))


class _Database:
    def __init__(self):
        self.collections = {
            "mcp_servers": _Collection(
                [
                    {"delete_at": None, "enabled": True, "provisioning_status": "ready"},
                    {"delete_at": None, "enabled": True, "provisioning_status": "failed"},
                ]
            ),
            "external_apis": _Collection([{"delete_at": None, "enabled": False}]),
            "ingestion_jobs": _Collection(
                [{"status": "uploaded"}, {"status": "embedding"}, {"status": "failed"}]
            ),
            "chat_attachment_metadata": _Collection(
                [{"status": "stored", "delete_at": None}, {"status": "failed", "delete_at": None}]
            ),
        }

    def command(self, name):
        assert name == "ping"
        return {"ok": 1}

    def __getitem__(self, name):
        return self.collections.setdefault(name, _Collection())


class _Task:
    def __init__(self, done=False):
        self._done = done

    def done(self):
        return self._done


@pytest.mark.asyncio
async def test_health_snapshot_contains_safe_service_integration_and_job_counts(monkeypatch):
    async def successful_probe(*_args, **_kwargs):
        return 12

    monkeypatch.setattr(system_health, "_http_probe", successful_probe)
    monkeypatch.setattr(
        system_health,
        "_resource_snapshot",
        lambda: {"scope": "runtime_environment", "scope_label": "Runtime", "status": "healthy"},
    )
    snapshot = await system_health.build_system_health_snapshot(
        _Database(),
        {
            "llm_profiles": {"default": object()},
            "ingestion_recovery_task": _Task(),
            "chat_attachment_recovery_task": _Task(),
            "chat_attachment_cleanup_task": _Task(),
        },
        {
            "KNOWLEDGE_STORAGE_PROVIDER": "minio",
            "MINIO_ENDPOINT": "minio:9000",
            "KNOWLEDGE_SEARCH_PROVIDER": "qdrant",
            "QDRANT_URL": "http://qdrant:6333",
            "INTEGRATION_CONTROLLER_URL": "http://integration-controller:8080",
            "USE_USER_UPLOAD": "true",
            "CHAT_ATTACHMENT_STORE": "local",
            "SECRET_VALUE": "must-not-leak",
        },
    )

    assert snapshot["status"] == "healthy"
    assert snapshot["integrations"] == {
        "total": 3,
        "enabled": 2,
        "disabled": 1,
        "attention": 1,
        "by_kind": [
            {"kind": "rest_api", "total": 1, "enabled": 0, "attention": 0},
            {"kind": "database", "total": 0, "enabled": 0, "attention": 0},
            {"kind": "mail", "total": 0, "enabled": 0, "attention": 0},
            {"kind": "messaging", "total": 0, "enabled": 0, "attention": 0},
            {"kind": "business_documents", "total": 0, "enabled": 0, "attention": 0},
            {"kind": "mcp", "total": 2, "enabled": 2, "attention": 1},
        ],
    }
    assert snapshot["jobs"]["ingestion"]["processing"] == 1
    assert snapshot["jobs"]["attachments"]["failed"] == 1
    assert "must-not-leak" not in str(snapshot)


@pytest.mark.asyncio
async def test_health_snapshot_degrades_without_database_or_controller(monkeypatch):
    database = _Database()
    database.command = lambda _name: (_ for _ in ()).throw(RuntimeError("mongodb://user:secret@host"))
    async def failed_probe(*_args, **_kwargs):
        raise RuntimeError("Bearer secret")

    monkeypatch.setattr(system_health, "_http_probe", failed_probe)
    monkeypatch.setattr(
        system_health,
        "_resource_snapshot",
        lambda: {"scope": "runtime_environment", "scope_label": "Runtime", "status": "healthy"},
    )

    snapshot = await system_health.build_system_health_snapshot(
        database,
        {"llm_profiles": {}},
        {
            "KNOWLEDGE_STORAGE_PROVIDER": "azure",
            "KNOWLEDGE_SEARCH_PROVIDER": "azure",
            "INTEGRATION_CONTROLLER_URL": "http://controller:8080",
        },
    )

    assert snapshot["status"] == "degraded"
    assert next(item for item in snapshot["services"] if item["id"] == "mongodb")["status"] == "unavailable"
    assert "secret" not in str(snapshot).lower()


def test_resource_thresholds():
    assert system_health._resource_status(79.9) == "healthy"
    assert system_health._resource_status(80) == "warning"
    assert system_health._resource_status(90) == "critical"


@pytest.mark.asyncio
async def test_system_health_route_requires_system_admin(client, monkeypatch):
    calls = []
    monkeypatch.setattr(backend_app, "_require_system_admin", lambda claims: calls.append(claims))

    async def snapshot(*_args):
        await asyncio.sleep(0)
        return {"status": "healthy", "checked_at": "2026-09-08T00:00:00+00:00", "services": [], "integrations": {}, "jobs": {}}

    monkeypatch.setattr(backend_app, "build_system_health_snapshot", snapshot)
    response = await client.get("/admin/system-health")

    assert response.status_code == 200
    assert (await response.get_json())["status"] == "healthy"
    assert len(calls) == 1
