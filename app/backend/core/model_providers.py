from typing import Union

from azure.core.credentials import AzureKeyCredential
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import get_bearer_token_provider
from openai import AsyncAzureOpenAI, AsyncOpenAI

from core.runtime_settings import (
    EmbeddingProviderSettings,
    LLMProviderSettings,
    ModelProvider,
)
from prepdocslib.embeddings import (
    AzureOpenAIEmbeddingService,
    OpenAIEmbeddings,
    OpenAIEmbeddingService,
)


def create_llm_client(
    settings: LLMProviderSettings,
    azure_credential: AsyncTokenCredential,
) -> AsyncOpenAI:
    if settings.provider == ModelProvider.AZURE_OPENAI:
        if not settings.endpoint:
            raise ValueError("An Azure OpenAI endpoint or service must be configured")
        if settings.api_key:
            return AsyncAzureOpenAI(
                api_version=settings.api_version,
                azure_endpoint=settings.endpoint,
                api_key=settings.api_key,
            )
        token_provider = get_bearer_token_provider(
            azure_credential, "https://cognitiveservices.azure.com/.default"
        )
        return AsyncAzureOpenAI(
            api_version=settings.api_version,
            azure_endpoint=settings.endpoint,
            azure_ad_token_provider=token_provider,
        )

    if settings.provider == ModelProvider.OPENAI:
        if not settings.api_key:
            raise ValueError("OpenAI key is required when using the non-Azure OpenAI API")
        return AsyncOpenAI(api_key=settings.api_key, organization=settings.organization)

    if not settings.base_url:
        raise ValueError("LLM_BASE_URL is required when using the OpenAI-compatible provider")
    return AsyncOpenAI(base_url=settings.base_url, api_key=settings.api_key or "no-key-required")


def create_embedding_service(
    settings: EmbeddingProviderSettings,
    azure_credential: AsyncTokenCredential,
    *,
    disable_vectors: bool = False,
    disable_batch: bool = False,
) -> Union[OpenAIEmbeddings, None]:
    if disable_vectors:
        return None

    if settings.provider == ModelProvider.AZURE_OPENAI:
        if not settings.endpoint:
            raise ValueError("An Azure OpenAI endpoint or service must be configured for embeddings")
        credential: Union[AsyncTokenCredential, AzureKeyCredential] = (
            AzureKeyCredential(settings.api_key) if settings.api_key else azure_credential
        )
        return AzureOpenAIEmbeddingService(
            open_ai_service=None,
            open_ai_custom_url=settings.endpoint,
            open_ai_deployment=settings.deployment,
            open_ai_model_name=settings.model,
            open_ai_dimensions=settings.dimensions,
            open_ai_api_version=settings.api_version,
            credential=credential,
            disable_batch=disable_batch,
        )

    if settings.provider == ModelProvider.OPENAI and not settings.api_key:
        raise ValueError("OpenAI key is required when using the non-Azure OpenAI API")
    if settings.provider == ModelProvider.OPENAI_COMPATIBLE and not settings.base_url:
        raise ValueError("EMBEDDING_BASE_URL is required when using the OpenAI-compatible embedding provider")

    return OpenAIEmbeddingService(
        open_ai_model_name=settings.model,
        open_ai_dimensions=settings.dimensions,
        credential=settings.api_key or "no-key-required",
        organization=settings.organization,
        base_url=settings.base_url,
        disable_batch=disable_batch,
    )
