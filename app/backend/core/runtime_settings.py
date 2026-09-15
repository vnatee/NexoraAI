from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RuntimeMode(str, Enum):
    AZURE = "azure"
    LOCAL = "local"


class ModelProvider(str, Enum):
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"


def _optional(env: Mapping[str, str], name: str) -> Optional[str]:
    value = env.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def parse_model_provider(value: str) -> ModelProvider:
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "azure": ModelProvider.AZURE_OPENAI,
        "azure_custom": ModelProvider.AZURE_OPENAI,
        "azure_openai": ModelProvider.AZURE_OPENAI,
        "openai": ModelProvider.OPENAI,
        "local": ModelProvider.OPENAI_COMPATIBLE,
        "compatible": ModelProvider.OPENAI_COMPATIBLE,
        "openai_compatible": ModelProvider.OPENAI_COMPATIBLE,
    }
    try:
        return aliases[normalized]
    except KeyError as error:
        allowed = ", ".join(provider.value for provider in ModelProvider)
        raise ValueError(f"Unsupported model provider '{value}'. Expected one of: {allowed}") from error


@dataclass(frozen=True)
class LLMProviderSettings:
    provider: ModelProvider
    model: str
    deployment: Optional[str]
    api_version: str
    endpoint: Optional[str]
    base_url: Optional[str]
    api_key: Optional[str]
    organization: Optional[str]


@dataclass(frozen=True)
class EmbeddingProviderSettings:
    provider: ModelProvider
    model: str
    deployment: Optional[str]
    dimensions: int
    api_version: str
    endpoint: Optional[str]
    base_url: Optional[str]
    api_key: Optional[str]
    organization: Optional[str]


@dataclass(frozen=True)
class RuntimeSettings:
    mode: RuntimeMode
    llm: LLMProviderSettings
    embedding: EmbeddingProviderSettings

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "RuntimeSettings":
        mode_value = env.get("APP_RUNTIME_MODE", RuntimeMode.AZURE.value).strip().lower()
        try:
            mode = RuntimeMode(mode_value)
        except ValueError as error:
            raise ValueError("APP_RUNTIME_MODE must be either 'azure' or 'local'") from error

        legacy_host = env.get("OPENAI_HOST", "azure").strip().lower()
        llm_provider_value = env.get("LLM_PROVIDER", legacy_host)
        llm_provider = parse_model_provider(llm_provider_value)

        # Historically every host except `openai` used Azure embeddings, even
        # when the chat endpoint was a local OpenAI-compatible server.
        legacy_embedding_provider = (
            ModelProvider.OPENAI if legacy_host == "openai" else ModelProvider.AZURE_OPENAI
        )
        embedding_provider_value = env.get("EMBEDDING_PROVIDER")
        embedding_provider = (
            parse_model_provider(embedding_provider_value)
            if embedding_provider_value
            else legacy_embedding_provider
        )

        azure_service = _optional(env, "AZURE_OPENAI_SERVICE")
        azure_endpoint = _optional(env, "AZURE_OPENAI_CUSTOM_URL") or _optional(env, "AZURE_OPENAI_ENDPOINT")
        if azure_endpoint is None and azure_service:
            azure_endpoint = f"https://{azure_service}.openai.azure.com"

        api_version = _optional(env, "AZURE_OPENAI_API_VERSION") or "2024-10-21"
        llm_model = env.get("LLM_MODEL") or env.get("AZURE_OPENAI_CHATGPT_MODEL", "")
        embedding_model = env.get("EMBEDDING_MODEL") or env.get(
            "AZURE_OPENAI_EMB_MODEL_NAME", "text-embedding-ada-002"
        )
        dimensions_value = env.get("EMBEDDING_DIMENSIONS") or env.get("AZURE_OPENAI_EMB_DIMENSIONS") or "1536"
        try:
            embedding_dimensions = int(dimensions_value)
        except ValueError as error:
            raise ValueError("EMBEDDING_DIMENSIONS must be an integer") from error
        if embedding_dimensions <= 0:
            raise ValueError("EMBEDDING_DIMENSIONS must be greater than zero")

        llm = LLMProviderSettings(
            provider=llm_provider,
            model=llm_model,
            deployment=(
                _optional(env, "LLM_DEPLOYMENT")
                or (_optional(env, "AZURE_OPENAI_CHATGPT_DEPLOYMENT") if llm_provider == ModelProvider.AZURE_OPENAI else None)
            ),
            api_version=_optional(env, "LLM_API_VERSION") or api_version,
            endpoint=_optional(env, "LLM_AZURE_ENDPOINT") or azure_endpoint,
            base_url=_optional(env, "LLM_BASE_URL") or _optional(env, "OPENAI_BASE_URL"),
            api_key=(
                _optional(env, "LLM_API_KEY")
                or (
                    _optional(env, "AZURE_OPENAI_API_KEY_OVERRIDE")
                    if llm_provider == ModelProvider.AZURE_OPENAI
                    else _optional(env, "OPENAI_API_KEY")
                )
            ),
            organization=_optional(env, "LLM_ORGANIZATION") or _optional(env, "OPENAI_ORGANIZATION"),
        )
        embedding = EmbeddingProviderSettings(
            provider=embedding_provider,
            model=embedding_model,
            deployment=(
                _optional(env, "EMBEDDING_DEPLOYMENT")
                or (
                    _optional(env, "AZURE_OPENAI_EMB_DEPLOYMENT")
                    if embedding_provider == ModelProvider.AZURE_OPENAI
                    else None
                )
            ),
            dimensions=embedding_dimensions,
            api_version=_optional(env, "EMBEDDING_API_VERSION") or api_version,
            endpoint=_optional(env, "EMBEDDING_AZURE_ENDPOINT") or azure_endpoint,
            base_url=(
                _optional(env, "EMBEDDING_BASE_URL")
                or (_optional(env, "LLM_BASE_URL") or _optional(env, "OPENAI_BASE_URL"))
                if embedding_provider == ModelProvider.OPENAI_COMPATIBLE
                else None
            ),
            api_key=(
                _optional(env, "EMBEDDING_API_KEY")
                or (_optional(env, "LLM_API_KEY") if embedding_provider == ModelProvider.OPENAI_COMPATIBLE else None)
                or _optional(env, "OPENAI_API_KEY")
            ),
            organization=_optional(env, "EMBEDDING_ORGANIZATION") or _optional(env, "OPENAI_ORGANIZATION"),
        )
        return cls(mode=mode, llm=llm, embedding=embedding)
