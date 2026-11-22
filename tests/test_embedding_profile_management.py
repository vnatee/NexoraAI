import pytest
from cryptography.fernet import Fernet

import app
from core.provider_secrets import decrypt_provider_secret


def test_embedding_profile_payload_encrypts_secret_and_validates_vector_space(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))

    result = app._normalize_embedding_profile_payload(
        {
            "name": "Local multilingual",
            "provider": "openai_compatible",
            "base_url": "http://ollama:11434/v1/",
            "model": "bge-m3",
            "dimensions": 1024,
            "collection_name": "knowledge-bge-m3-v2",
            "api_key": "local-secret",
        }
    )

    assert result["provider"] == "openai_compatible"
    assert result["base_url"] == "http://ollama:11434/v1"
    assert result["dimensions"] == 1024
    assert result["collection_name"] == "knowledge-bge-m3-v2"
    assert decrypt_provider_secret(result["api_key_ciphertext"]) == "local-secret"


def test_gateway_embedding_profile_reuses_gateway_policy_without_copying_secret(monkeypatch):
    monkeypatch.setattr(
        app,
        "get_ai_gateway_settings",
        lambda: {
            "mode": "external",
            "base_url": "https://gateway.example.com",
        },
    )

    result = app._normalize_embedding_profile_payload(
        {
            "name": "Governed embeddings",
            "provider": "ai_gateway",
            "gateway_proxy_path": "/embedding/v1/",
            "model": "text-embedding-3-small",
            "dimensions": 1536,
            "collection_name": "knowledge-gateway-v1",
            "api_key": "must-not-be-copied",
        }
    )

    assert result["provider"] == "ai_gateway"
    assert result["gateway_proxy_path"] == "embedding/v1"
    assert result["base_url"] is None
    assert result["api_key_ciphertext"] is None


def test_gateway_embedding_profile_requires_external_gateway_mode(monkeypatch):
    monkeypatch.setattr(
        app,
        "get_ai_gateway_settings",
        lambda: {"mode": "built_in"},
    )

    with pytest.raises(ValueError, match="External AI Gateway mode"):
        app._normalize_embedding_profile_payload(
            {
                "name": "Governed embeddings",
                "provider": "ai_gateway",
                "gateway_proxy_path": "embedding/v1",
                "model": "text-embedding-3-small",
                "dimensions": 1536,
                "collection_name": "knowledge-gateway-v1",
            }
        )


def test_gateway_embedding_service_uses_governed_gateway_client(monkeypatch):
    gateway = {
        "mode": "external",
        "base_url": "https://gateway.example.com",
    }
    sentinel_client = object()
    captured = {}
    monkeypatch.setattr(app, "get_ai_gateway_settings", lambda: gateway)
    monkeypatch.setattr(
        app,
        "create_external_gateway_client",
        lambda settings, route: captured.update(settings=settings, route=route)
        or sentinel_client,
    )
    profile = {
        "_id": "embedding-1",
        "provider": "ai_gateway",
        "gateway_proxy_path": "embedding/v1",
        "model": "text-embedding-3-small",
        "dimensions": 1536,
    }

    settings = app._settings_for_embedding_profile(profile)
    service = app._embedding_service_for_profile(profile, settings, object())

    assert settings.base_url == "https://gateway.example.com/embedding/v1"
    assert service.client is sentinel_client
    assert captured["settings"] is gateway
    assert captured["route"]["proxy_path"] == "embedding/v1"


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"dimensions": 0}, "dimensions"),
        ({"collection_name": "invalid collection"}, "Qdrant collection"),
        ({"base_url": "ollama:11434/v1"}, "base URL"),
    ],
)
def test_embedding_profile_payload_rejects_invalid_configuration(updates, message):
    payload = {
        "name": "Local multilingual",
        "provider": "openai_compatible",
        "base_url": "http://ollama:11434/v1",
        "model": "bge-m3",
        "dimensions": 1024,
        "collection_name": "knowledge-bge-m3-v2",
        "enabled": False,
    }
    payload.update(updates)

    with pytest.raises(ValueError, match=message):
        app._normalize_embedding_profile_payload(payload)


def test_embedding_profile_serialization_never_returns_secret():
    result = app._serialize_embedding_profile(
        {
            "_id": "embedding-1",
            "name": "Embedding",
            "provider": "openai",
            "model": "text-embedding-3-small",
            "dimensions": 1536,
            "collection_name": "knowledge-openai-small",
            "api_key_ciphertext": "encrypted",
        }
    )

    assert result["has_api_key"] is True
    assert "api_key" not in result
    assert "api_key_ciphertext" not in result


@pytest.mark.asyncio
async def test_embedding_profile_activation_requires_system_admin_and_marks_restart(client, monkeypatch):
    authorization_calls = []
    monkeypatch.setenv("KNOWLEDGE_SEARCH_PROVIDER", "qdrant")
    monkeypatch.setattr(
        app,
        "_require_system_admin",
        lambda claims: authorization_calls.append(claims) or {"_id": "admin-1"},
    )
    monkeypatch.setattr(
        app,
        "get_embedding_profile",
        lambda profile_id: {"_id": profile_id, "enabled": True},
    )
    monkeypatch.setattr(
        app,
        "activate_embedding_profile",
        lambda profile_id: {
            "active_profile_id": profile_id,
            "runtime_profile_id": "environment",
            "restart_required": True,
            "reindex_required": True,
            "activated_at": None,
            "runtime_started_at": None,
        },
    )
    async def successful_probe(_profile_id):
        return object(), 1024

    monkeypatch.setattr(app, "_probe_embedding_profile", successful_probe)

    response = await client.post("/admin/embedding-profiles/embedding-1/activate")
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload["settings"]["active_profile_id"] == "embedding-1"
    assert payload["settings"]["restart_required"] is True
    assert payload["settings"]["reindex_required"] is True
    assert len(authorization_calls) == 1


@pytest.mark.asyncio
async def test_embedding_profile_test_rejects_dimension_mismatch(client, monkeypatch):
    monkeypatch.setattr(app, "_require_system_admin", lambda _claims: {"_id": "admin-1"})
    monkeypatch.setattr(
        app,
        "get_embedding_profile",
        lambda _profile_id: {
            "_id": "embedding-1",
            "provider": "openai_compatible",
            "model": "bge-m3",
            "dimensions": 1024,
            "base_url": "http://ollama:11434/v1",
        },
    )

    class Service:
        async def create_embeddings(self, _texts):
            return [[0.0, 1.0]]

    monkeypatch.setattr(app, "create_embedding_service", lambda *_args, **_kwargs: Service())
    response = await client.post("/admin/embedding-profiles/embedding-1/test")

    assert response.status_code == 400
    assert "returned 2 dimensions" in (await response.get_json())["error"]


@pytest.mark.asyncio
async def test_embedding_reindex_completion_requires_running_profile(client, monkeypatch):
    monkeypatch.setattr(app, "_require_system_admin", lambda _claims: {"_id": "admin-1"})
    monkeypatch.setattr(
        app,
        "latest_embedding_reindex_run",
        lambda _profile_id: {
            "_id": "run-1",
            "status": "completed",
        },
    )
    monkeypatch.setattr(
        app,
        "embedding_reindex_progress",
        lambda _run_id: {"total": 1, "succeeded": 1, "failed": 0},
    )

    def reject(_profile_id):
        raise ValueError("The selected embedding profile must be running")

    monkeypatch.setattr(app, "mark_embedding_reindex_complete", reject)

    response = await client.post("/admin/embedding-profiles/embedding-1/reindex-complete")

    assert response.status_code == 409
    assert "must be running" in (await response.get_json())["error"]


@pytest.mark.asyncio
async def test_embedding_reindex_plan_requires_running_selected_profile(client, monkeypatch):
    monkeypatch.setattr(app, "_require_system_admin", lambda _claims: {"_id": "admin-1"})
    monkeypatch.setattr(
        app,
        "get_embedding_profile",
        lambda profile_id: {"_id": profile_id, "name": "BGE", "model": "bge-m3", "dimensions": 1024, "collection_name": "new"},
    )
    monkeypatch.setattr(
        app,
        "get_embedding_settings",
        lambda: {"active_profile_id": "embedding-1", "runtime_profile_id": "environment"},
    )

    response = await client.get("/admin/embedding-profiles/embedding-1/reindex-plan")

    assert response.status_code == 409
    assert "must be running" in (await response.get_json())["error"]


@pytest.mark.asyncio
async def test_embedding_reindex_start_requires_typed_confirmation(client, monkeypatch):
    monkeypatch.setattr(app, "_require_system_admin", lambda _claims: {"_id": "admin-1"})
    monkeypatch.setattr(
        app,
        "get_embedding_profile",
        lambda profile_id: {"_id": profile_id, "name": "BGE", "model": "bge-m3", "dimensions": 1024, "collection_name": "new"},
    )
    monkeypatch.setattr(
        app,
        "get_embedding_settings",
        lambda: {"active_profile_id": "embedding-1", "runtime_profile_id": "embedding-1", "reindex_required": True},
    )

    response = await client.post(
        "/admin/embedding-profiles/embedding-1/reindex",
        json={"confirmation": "REINDEX"},
    )

    assert response.status_code == 409
    assert "confirmation" in (await response.get_json())["error"]


@pytest.mark.asyncio
async def test_embedding_collection_adoption_retests_and_records_compatible_collection(client, monkeypatch):
    profile = {
        "_id": "embedding-1",
        "name": "BGE",
        "provider": "openai_compatible",
        "model": "bge-m3",
        "dimensions": 1024,
        "collection_name": "new",
    }
    updates = []
    monkeypatch.setattr(app, "_require_system_admin", lambda _claims: {"_id": "admin-1"})
    monkeypatch.setattr(app, "get_embedding_profile", lambda _profile_id: profile)
    monkeypatch.setattr(
        app,
        "get_embedding_settings",
        lambda: {"active_profile_id": "embedding-1", "runtime_profile_id": "embedding-1"},
    )
    monkeypatch.setattr(
        app,
        "_embedding_collection_compatibility",
        lambda *_args: None,
    )

    async def compatible(*_args):
        return {
            "compatible": True,
            "sample_count": 12,
            "minimum_cosine_similarity": 0.9999,
            "mean_cosine_similarity": 0.99995,
            "threshold": 0.999,
            "dimensions": 1024,
            "collection_name": "existing",
        }

    monkeypatch.setattr(app, "_embedding_collection_compatibility", compatible)
    monkeypatch.setattr(app, "update_embedding_profile", lambda profile_id, data: updates.append((profile_id, data)) or profile)
    monkeypatch.setattr(
        app,
        "mark_embedding_collection_adopted",
        lambda *_args, **_kwargs: {
            "active_profile_id": "embedding-1",
            "runtime_profile_id": "embedding-1",
            "restart_required": True,
            "reindex_required": False,
            "activated_at": None,
            "runtime_started_at": None,
        },
    )

    class AuditCollection:
        def insert_one(self, document):
            self.document = document

    audit = AuditCollection()
    monkeypatch.setattr(app, "get_database", lambda: {"embedding_profile_audit": audit})

    response = await client.post(
        "/admin/embedding-profiles/embedding-1/adopt-collection",
        json={"collection_name": "existing", "confirmation": "ADOPT existing"},
    )

    assert response.status_code == 200
    assert updates == [("embedding-1", {"collection_name": "existing"})]
    assert (await response.get_json())["settings"]["reindex_required"] is False
