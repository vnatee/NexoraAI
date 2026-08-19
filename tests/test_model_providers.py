import pytest

from approaches.approach import Approach
from core.model_providers import create_embedding_service, create_llm_client
from core.runtime_settings import (
    EmbeddingProviderSettings,
    LLMProviderSettings,
    ModelProvider,
)
from prepdocslib.embeddings import AzureOpenAIEmbeddingService, OpenAIEmbeddingService

from .mocks import MockAzureCredential


def test_create_openai_compatible_llm_client():
    settings = LLMProviderSettings(
        provider=ModelProvider.OPENAI_COMPATIBLE,
        model="qwen-chat",
        deployment=None,
        api_version="unused",
        endpoint=None,
        base_url="http://ollama:11434/v1",
        api_key=None,
        organization=None,
    )

    client = create_llm_client(settings, MockAzureCredential())

    assert client.api_key == "no-key-required"
    assert str(client.base_url) == "http://ollama:11434/v1/"


def test_create_azure_embedding_service():
    settings = EmbeddingProviderSettings(
        provider=ModelProvider.AZURE_OPENAI,
        model="text-embedding-3-large",
        deployment="embedding-deployment",
        dimensions=3072,
        api_version="2024-10-21",
        endpoint="https://example.openai.azure.com",
        base_url=None,
        api_key=None,
        organization=None,
    )

    service = create_embedding_service(settings, MockAzureCredential())

    assert isinstance(service, AzureOpenAIEmbeddingService)
    assert service.open_ai_endpoint == "https://example.openai.azure.com"
    assert service.open_ai_deployment == "embedding-deployment"


@pytest.mark.asyncio
async def test_create_openai_compatible_embedding_service():
    settings = EmbeddingProviderSettings(
        provider=ModelProvider.OPENAI_COMPATIBLE,
        model="qwen-embedding",
        deployment=None,
        dimensions=1024,
        api_version="unused",
        endpoint=None,
        base_url="http://embedding:8001/v1",
        api_key=None,
        organization=None,
    )

    service = create_embedding_service(settings, MockAzureCredential())

    assert isinstance(service, OpenAIEmbeddingService)
    client = await service.create_client()
    try:
        assert client.api_key == "no-key-required"
        assert str(client.base_url) == "http://embedding:8001/v1/"
    finally:
        await client.close()


def test_compatible_provider_requires_base_url():
    settings = LLMProviderSettings(
        provider=ModelProvider.OPENAI_COMPATIBLE,
        model="qwen-chat",
        deployment=None,
        api_version="unused",
        endpoint=None,
        base_url=None,
        api_key=None,
        organization=None,
    )

    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        create_llm_client(settings, MockAzureCredential())


@pytest.mark.asyncio
async def test_rag_query_uses_independent_embedding_service():
    class StubEmbeddingService:
        async def create_embeddings(self, texts):
            assert texts == ["hello"]
            return [[0.1, 0.2, 0.3]]

    approach = object.__new__(Approach)
    approach.embedding_service = StubEmbeddingService()
    approach.embedding_field = "embedding"

    query = await approach.compute_text_embedding("hello")

    assert query.vector == [0.1, 0.2, 0.3]
