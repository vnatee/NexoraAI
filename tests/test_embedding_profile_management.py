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

    def reject(_profile_id):
        raise ValueError("The selected embedding profile must be running")

    monkeypatch.setattr(app, "mark_embedding_reindex_complete", reject)

    response = await client.post("/admin/embedding-profiles/embedding-1/reindex-complete")

    assert response.status_code == 409
    assert "must be running" in (await response.get_json())["error"]
