import json
import os
from unittest import mock

import pytest
import quart

import app


@pytest.fixture
def minimal_env(monkeypatch):
    with mock.patch.dict(os.environ, clear=True):
        monkeypatch.setenv("AZURE_STORAGE_ACCOUNT", "test-storage-account")
        monkeypatch.setenv("AZURE_STORAGE_CONTAINER", "test-storage-container")
        monkeypatch.setenv("AZURE_WEB_STORAGE_CONTAINER", "test-web-storage-container")
        monkeypatch.setenv("AZURE_WEB_GROUP_STORAGE_CONTAINER", "test-web-group-storage-container")
        monkeypatch.setenv("AZURE_GROUP_STORAGE_CONTAINER", "test-group-storage-container")
        monkeypatch.setenv("AZURE_SEARCH_INDEX", "test-search-index")
        monkeypatch.setenv("AZURE_SEARCH_SERVICE", "test-search-service")
        monkeypatch.setenv("AZURE_OPENAI_SERVICE", "test-openai-service")
        monkeypatch.setenv("AZURE_OPENAI_CHATGPT_MODEL", "gpt-4.1-mini")
        monkeypatch.setenv("AZURE_OPENAI_EMB_MODEL_NAME", "text-embedding-3-large")
        monkeypatch.setenv("AZURE_OPENAI_EMB_DIMENSIONS", "3072")
        monkeypatch.setenv("SKIP_STARTUP_BOOTSTRAP", "true")
        monkeypatch.setenv("SKIP_MANAGED_LLM_PROVIDER_LOAD", "true")
        monkeypatch.setenv("DISABLE_USAGE_PERSISTENCE", "true")
        monkeypatch.setenv("DISABLE_INGESTION_JOB_RECOVERY", "true")
        yield


@pytest.mark.asyncio
async def test_app_local_openai(monkeypatch, minimal_env):
    monkeypatch.setenv("OPENAI_HOST", "local")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:5000")

    quart_app = app.create_app()
    async with quart_app.test_app():
        assert quart_app.config[app.CONFIG_OPENAI_CLIENT].api_key == "no-key-required"
        assert quart_app.config[app.CONFIG_OPENAI_CLIENT].base_url == "http://localhost:5000"


@pytest.mark.asyncio
async def test_app_independent_local_model_providers(monkeypatch, minimal_env):
    monkeypatch.setenv("APP_RUNTIME_MODE", "local")
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://llm:8000/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen-chat")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai_compatible")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "http://embedding:8001/v1")
    monkeypatch.setenv("EMBEDDING_MODEL", "qwen-embedding")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "1024")

    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        response = await test_app.test_client().get("/config")
        result = await response.get_json()

        assert result["runtimeMode"] == "local"
        assert result["llmProvider"] == "openai_compatible"
        assert result["embeddingProvider"] == "openai_compatible"
        assert quart_app.config[app.CONFIG_OPENAI_CLIENT].base_url == "http://llm:8000/v1/"
        assert quart_app.config[app.CONFIG_ASK_APPROACH].embedding_service.base_url == "http://embedding:8001/v1"


@pytest.mark.asyncio
async def test_app_exposes_safe_agent_llm_profiles(monkeypatch, minimal_env):
    monkeypatch.setenv(
        "LLM_PROFILES_JSON",
        json.dumps(
            [
                {
                    "id": "local-qwen",
                    "label": "Local Qwen",
                    "provider": "openai_compatible",
                    "model": "qwen3",
                    "base_url": "http://ollama:11434/v1",
                }
            ]
        ),
    )

    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        response = await test_app.test_client().get("/config")
        result = await response.get_json()

        assert result["llmProfiles"] == [
            {
                "id": "system",
                "label": "System default",
                    "provider": "azure_openai",
                    "quotaProviderId": "configured:azure_openai",
                    "model": "gpt-4.1-mini",
                    "supportsTools": True,
                    "supportsVision": False,
            },
            {
                "id": "local-qwen",
                "label": "Local Qwen",
                    "provider": "openai_compatible",
                    "quotaProviderId": "configured:openai_compatible",
                    "model": "qwen3",
                    "supportsTools": True,
                    "supportsVision": False,
            },
        ]
        assert quart_app.config[app.CONFIG_LLM_PROFILE_CLIENTS]["local-qwen"].base_url == "http://ollama:11434/v1/"


@pytest.mark.asyncio
async def test_app_azure_custom_key(monkeypatch, minimal_env):
    monkeypatch.setenv("OPENAI_HOST", "azure_custom")
    monkeypatch.setenv("AZURE_OPENAI_CUSTOM_URL", "http://azureapi.com/api/v1")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY_OVERRIDE", "azure-api-key")

    quart_app = app.create_app()
    async with quart_app.test_app():
        assert quart_app.config[app.CONFIG_OPENAI_CLIENT].api_key == "azure-api-key"
        assert quart_app.config[app.CONFIG_OPENAI_CLIENT].base_url == "http://azureapi.com/api/v1/openai/"


@pytest.mark.asyncio
async def test_app_azure_custom_identity(monkeypatch, minimal_env):
    monkeypatch.setenv("OPENAI_HOST", "azure_custom")
    monkeypatch.setenv("AZURE_OPENAI_CUSTOM_URL", "http://azureapi.com/api/v1")

    quart_app = app.create_app()
    async with quart_app.test_app():
        assert quart_app.config[app.CONFIG_OPENAI_CLIENT].api_key == "<missing API key>"
        assert quart_app.config[app.CONFIG_OPENAI_CLIENT].base_url == "http://azureapi.com/api/v1/openai/"


@pytest.mark.asyncio
async def test_app_user_upload_processors(monkeypatch, minimal_env):
    monkeypatch.setenv("AZURE_USERSTORAGE_ACCOUNT", "test-user-storage-account")
    monkeypatch.setenv("AZURE_USERSTORAGE_CONTAINER", "test-user-storage-container")
    monkeypatch.setenv("USE_USER_UPLOAD", "true")

    quart_app = app.create_app()
    async with quart_app.test_app():
        ingester = quart_app.config[app.CONFIG_INGESTER]
        assert ingester is not None
        # Managed processing profiles can route office/image formats to a
        # local Docling service even when Azure Document Intelligence is off.
        assert len(ingester.file_processors.keys()) == 15
        assert {".pdf", ".docx", ".png"}.issubset(ingester.file_processors)


@pytest.mark.asyncio
async def test_app_user_upload_processors_docint(monkeypatch, minimal_env):
    monkeypatch.setenv("AZURE_USERSTORAGE_ACCOUNT", "test-user-storage-account")
    monkeypatch.setenv("AZURE_USERSTORAGE_CONTAINER", "test-user-storage-container")
    monkeypatch.setenv("USE_USER_UPLOAD", "true")
    monkeypatch.setenv("AZURE_DOCUMENTINTELLIGENCE_SERVICE", "test-docint-service")

    quart_app = app.create_app()
    async with quart_app.test_app():
        ingester = quart_app.config[app.CONFIG_INGESTER]
        assert ingester is not None
        assert len(ingester.file_processors.keys()) == 15


@pytest.mark.asyncio
async def test_app_user_upload_processors_docint_localpdf(monkeypatch, minimal_env):
    monkeypatch.setenv("AZURE_USERSTORAGE_ACCOUNT", "test-user-storage-account")
    monkeypatch.setenv("AZURE_USERSTORAGE_CONTAINER", "test-user-storage-container")
    monkeypatch.setenv("USE_USER_UPLOAD", "true")
    monkeypatch.setenv("AZURE_DOCUMENTINTELLIGENCE_SERVICE", "test-docint-service")
    monkeypatch.setenv("USE_LOCAL_PDF_PARSER", "true")

    quart_app = app.create_app()
    async with quart_app.test_app():
        ingester = quart_app.config[app.CONFIG_INGESTER]
        assert ingester is not None
        assert len(ingester.file_processors.keys()) == 15
        assert ingester.file_processors[".pdf"] is not ingester.file_processors[".pptx"]


@pytest.mark.asyncio
async def test_app_user_upload_processors_docint_localhtml(monkeypatch, minimal_env):
    monkeypatch.setenv("AZURE_USERSTORAGE_ACCOUNT", "test-user-storage-account")
    monkeypatch.setenv("AZURE_USERSTORAGE_CONTAINER", "test-user-storage-container")
    monkeypatch.setenv("USE_USER_UPLOAD", "true")
    monkeypatch.setenv("AZURE_DOCUMENTINTELLIGENCE_SERVICE", "test-docint-service")
    monkeypatch.setenv("USE_LOCAL_HTML_PARSER", "true")

    quart_app = app.create_app()
    async with quart_app.test_app():
        ingester = quart_app.config[app.CONFIG_INGESTER]
        assert ingester is not None
        assert len(ingester.file_processors.keys()) == 15
        assert ingester.file_processors[".html"] is not ingester.file_processors[".pptx"]


@pytest.mark.asyncio
async def test_app_config_default(monkeypatch, minimal_env):
    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        client = test_app.test_client()
        response = await client.get("/config")
        assert response.status_code == 200
        result = await response.get_json()
        assert result["knowledgeStorageProvider"] == "azure"
        assert result["knowledgeSearchProvider"] == "azure"
        assert result["agentRuntimeMode"] == "per_agent"
        assert result["showGPT4VOptions"] is False
        assert result["showSemanticRankerOption"] is True
        assert result["showVectorOption"] is True
        assert result["chatDocumentAttachmentsEnabled"] is False
        assert result["maxUploadSizeBytes"] == 100 * 1024 * 1024


@pytest.mark.asyncio
async def test_app_uses_minio_knowledge_storage_provider(monkeypatch, minimal_env):
    knowledge_store = mock.AsyncMock()
    monkeypatch.setenv("KNOWLEDGE_STORAGE_PROVIDER", "minio")
    for name in (
        "AZURE_STORAGE_ACCOUNT",
        "AZURE_STORAGE_CONTAINER",
        "AZURE_WEB_STORAGE_CONTAINER",
        "AZURE_WEB_GROUP_STORAGE_CONTAINER",
        "AZURE_GROUP_STORAGE_CONTAINER",
    ):
        monkeypatch.delenv(name)
    monkeypatch.setattr(app, "create_minio_knowledge_store", lambda environ: knowledge_store)

    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        response = await test_app.test_client().get("/config")

        assert response.status_code == 200
        assert (await response.get_json())["knowledgeStorageProvider"] == "minio"
        assert quart_app.config[app.CONFIG_KNOWLEDGE_STORE] is knowledge_store
        knowledge_store.ensure_ready.assert_awaited_once()


@pytest.mark.asyncio
async def test_app_reports_missing_azure_knowledge_storage_settings(monkeypatch, minimal_env):
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT")

    quart_app = app.create_app()
    with pytest.raises(quart.testing.app.LifespanError, match="AZURE_STORAGE_ACCOUNT"):
        async with quart_app.test_app():
            pass


@pytest.mark.asyncio
async def test_app_uses_qdrant_and_disables_azure_search_only_features(monkeypatch, minimal_env):
    search_client = mock.AsyncMock()
    monkeypatch.setenv("KNOWLEDGE_SEARCH_PROVIDER", "qdrant")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setenv("QDRANT_COLLECTION", "knowledge")
    monkeypatch.setenv("USE_AGENTIC_RETRIEVAL", "true")
    monkeypatch.setattr(app, "QdrantKnowledgeSearchClient", lambda **_kwargs: search_client)

    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        response = await test_app.test_client().get("/config")
        result = await response.get_json()

        assert result["knowledgeSearchProvider"] == "qdrant"
        assert result["showSemanticRankerOption"] is False
        assert result["showQueryRewritingOption"] is False
        assert result["showAgenticRetrievalOption"] is False
        assert quart_app.config[app.CONFIG_SEARCH_CLIENT] is search_client
        search_client.ensure_ready.assert_awaited_once()


@pytest.mark.asyncio
async def test_app_config_custom_upload_request_limit(monkeypatch, minimal_env):
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "33554432")

    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        response = await test_app.test_client().get("/config")

        assert response.status_code == 200
        assert quart_app.config["MAX_CONTENT_LENGTH"] == 33554432
        assert (await response.get_json())["maxUploadSizeBytes"] == 33554432


def test_app_rejects_invalid_upload_request_limit(monkeypatch, minimal_env):
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "0")

    with pytest.raises(ValueError, match="MAX_UPLOAD_SIZE_BYTES must be a positive integer"):
        app.create_app()


@pytest.mark.asyncio
async def test_app_returns_json_for_oversized_request(monkeypatch, minimal_env):
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "64")
    quart_app = app.create_app()

    async def consume_body():
        await quart.request.get_data()
        return "ok"

    quart_app.add_url_rule("/test-upload-limit", "test_upload_limit", consume_body, methods=["POST"])
    async with quart_app.test_app() as test_app:
        response = await test_app.test_client().post("/test-upload-limit", data=b"x" * 65)

        assert response.status_code == 413
        assert "Upload request exceeds" in (await response.get_json())["error"]


@pytest.mark.asyncio
async def test_app_config_exposes_private_chat_document_availability(client):
    client.app.config[app.CONFIG_CHAT_ATTACHMENT_STORE] = mock.MagicMock()

    response = await client.get("/config")

    assert response.status_code == 200
    assert (await response.get_json())["chatDocumentAttachmentsEnabled"] is True


@pytest.mark.asyncio
async def test_app_config_exposes_global_agent_runtime(monkeypatch, minimal_env):
    monkeypatch.setenv("AGENT_RUNTIME_MODE", "langgraph")
    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        response = await test_app.test_client().get("/config")

        assert response.status_code == 200
        assert (await response.get_json())["agentRuntimeMode"] == "langgraph"


@pytest.mark.asyncio
async def test_app_config_use_vectors_true(monkeypatch, minimal_env):
    monkeypatch.setenv("USE_VECTORS", "true")
    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        client = test_app.test_client()
        response = await client.get("/config")
        assert response.status_code == 200
        result = await response.get_json()
        assert result["showGPT4VOptions"] is False
        assert result["showSemanticRankerOption"] is True
        assert result["showVectorOption"] is True


@pytest.mark.asyncio
async def test_app_config_use_vectors_false(monkeypatch, minimal_env):
    monkeypatch.setenv("USE_VECTORS", "false")
    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        client = test_app.test_client()
        response = await client.get("/config")
        assert response.status_code == 200
        result = await response.get_json()
        assert result["showGPT4VOptions"] is False
        assert result["showSemanticRankerOption"] is True
        assert result["showVectorOption"] is False


@pytest.mark.asyncio
async def test_app_config_semanticranker_free(monkeypatch, minimal_env):
    monkeypatch.setenv("AZURE_SEARCH_SEMANTIC_RANKER", "free")
    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        client = test_app.test_client()
        response = await client.get("/config")
        assert response.status_code == 200
        result = await response.get_json()
        assert result["showGPT4VOptions"] is False
        assert result["showSemanticRankerOption"] is True
        assert result["showVectorOption"] is True
        assert result["showUserUpload"] is False


@pytest.mark.asyncio
async def test_app_config_semanticranker_disabled(monkeypatch, minimal_env):
    monkeypatch.setenv("AZURE_SEARCH_SEMANTIC_RANKER", "disabled")
    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        client = test_app.test_client()
        response = await client.get("/config")
        assert response.status_code == 200
        result = await response.get_json()
        assert result["showGPT4VOptions"] is False
        assert result["showSemanticRankerOption"] is False
        assert result["showVectorOption"] is True
        assert result["showUserUpload"] is False


@pytest.mark.asyncio
async def test_app_config_user_upload(monkeypatch, minimal_env):
    monkeypatch.setenv("AZURE_USERSTORAGE_ACCOUNT", "test-user-storage-account")
    monkeypatch.setenv("AZURE_USERSTORAGE_CONTAINER", "test-user-storage-container")
    monkeypatch.setenv("USE_USER_UPLOAD", "true")
    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        client = test_app.test_client()
        response = await client.get("/config")
        assert response.status_code == 200
        result = await response.get_json()
        assert result["showGPT4VOptions"] is False
        assert result["showSemanticRankerOption"] is True
        assert result["showVectorOption"] is True
        assert result["showUserUpload"] is True


@pytest.mark.asyncio
async def test_app_config_user_upload_novectors(monkeypatch, minimal_env):
    """Check that this combo works correctly with prepdocs.py embedding service."""
    monkeypatch.setenv("AZURE_USERSTORAGE_ACCOUNT", "test-user-storage-account")
    monkeypatch.setenv("AZURE_USERSTORAGE_CONTAINER", "test-user-storage-container")
    monkeypatch.setenv("USE_USER_UPLOAD", "true")
    monkeypatch.setenv("USE_VECTORS", "false")
    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        client = test_app.test_client()
        response = await client.get("/config")
        assert response.status_code == 200
        result = await response.get_json()
        assert result["showGPT4VOptions"] is False
        assert result["showSemanticRankerOption"] is True
        assert result["showVectorOption"] is False
        assert result["showUserUpload"] is True


@pytest.mark.asyncio
async def test_app_config_user_upload_bad_openai_config(monkeypatch, minimal_env):
    """Check that this combo works correctly with prepdocs.py embedding service."""
    monkeypatch.setenv("AZURE_USERSTORAGE_ACCOUNT", "test-user-storage-account")
    monkeypatch.setenv("AZURE_USERSTORAGE_CONTAINER", "test-user-storage-container")
    monkeypatch.setenv("USE_USER_UPLOAD", "true")
    monkeypatch.setenv("OPENAI_HOST", "openai")
    quart_app = app.create_app()
    with pytest.raises(
        quart.testing.app.LifespanError, match="OpenAI key is required when using the non-Azure OpenAI API"
    ):
        async with quart_app.test_app() as test_app:
            test_app.test_client()


@pytest.mark.asyncio
async def test_app_config_user_upload_openaicom(monkeypatch, minimal_env):
    """Check that this combo works correctly with prepdocs.py embedding service."""
    monkeypatch.setenv("AZURE_USERSTORAGE_ACCOUNT", "test-user-storage-account")
    monkeypatch.setenv("AZURE_USERSTORAGE_CONTAINER", "test-user-storage-container")
    monkeypatch.setenv("USE_USER_UPLOAD", "true")
    monkeypatch.setenv("OPENAI_HOST", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "pretendkey")
    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        client = test_app.test_client()
        response = await client.get("/config")
        assert response.status_code == 200
        result = await response.get_json()
        assert result["showUserUpload"] is True


@pytest.mark.asyncio
async def test_app_config_for_client(client):
    response = await client.get("/config")
    assert response.status_code == 200
    result = await response.get_json()
    assert result["showGPT4VOptions"] == (os.getenv("USE_GPT4V") == "true")
    assert result["showSemanticRankerOption"] is True
    assert result["showVectorOption"] is True
    assert result["streamingEnabled"] is True
    assert result["showReasoningEffortOption"] is False


@pytest.mark.asyncio
async def test_app_config_for_reasoning(monkeypatch, minimal_env):
    monkeypatch.setenv("AZURE_OPENAI_CHATGPT_MODEL", "o3-mini")
    monkeypatch.setenv("AZURE_OPENAI_CHATGPT_DEPLOYMENT", "o3-mini")
    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        client = test_app.test_client()
        response = await client.get("/config")
        assert response.status_code == 200
        result = await response.get_json()
        assert result["streamingEnabled"] is True
        assert result["showReasoningEffortOption"] is True


@pytest.mark.asyncio
async def test_app_config_for_reasoning_without_streaming(monkeypatch, minimal_env):
    monkeypatch.setenv("AZURE_OPENAI_CHATGPT_MODEL", "o1")
    monkeypatch.setenv("AZURE_OPENAI_CHATGPT_DEPLOYMENT", "o1")
    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        client = test_app.test_client()
        response = await client.get("/config")
        assert response.status_code == 200
        result = await response.get_json()
        assert result["streamingEnabled"] is False
        assert result["showReasoningEffortOption"] is True


@pytest.mark.asyncio
async def test_app_config_for_reasoning_override_effort(monkeypatch, minimal_env):
    monkeypatch.setenv("AZURE_OPENAI_REASONING_EFFORT", "low")
    monkeypatch.setenv("AZURE_OPENAI_CHATGPT_MODEL", "o3-mini")
    monkeypatch.setenv("AZURE_OPENAI_CHATGPT_DEPLOYMENT", "o3-mini")
    quart_app = app.create_app()
    async with quart_app.test_app() as test_app:
        client = test_app.test_client()
        response = await client.get("/config")
        assert response.status_code == 200
        result = await response.get_json()
        assert result["streamingEnabled"] is True
        assert result["showReasoningEffortOption"] is True
        assert result["defaultReasoningEffort"] == "low"
