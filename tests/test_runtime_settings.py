import pytest

from core.runtime_settings import ModelProvider, RuntimeMode, RuntimeSettings


def test_runtime_settings_preserve_legacy_azure_configuration():
    settings = RuntimeSettings.from_env(
        {
            "OPENAI_HOST": "azure",
            "AZURE_OPENAI_SERVICE": "example-openai",
            "AZURE_OPENAI_CHATGPT_MODEL": "gpt-4.1-mini",
            "AZURE_OPENAI_CHATGPT_DEPLOYMENT": "chat-deployment",
            "AZURE_OPENAI_EMB_MODEL_NAME": "text-embedding-3-large",
            "AZURE_OPENAI_EMB_DEPLOYMENT": "embedding-deployment",
            "AZURE_OPENAI_EMB_DIMENSIONS": "3072",
        }
    )

    assert settings.mode == RuntimeMode.AZURE
    assert settings.llm.provider == ModelProvider.AZURE_OPENAI
    assert settings.llm.endpoint == "https://example-openai.openai.azure.com"
    assert settings.llm.deployment == "chat-deployment"
    assert settings.embedding.provider == ModelProvider.AZURE_OPENAI
    assert settings.embedding.deployment == "embedding-deployment"
    assert settings.embedding.dimensions == 3072


def test_runtime_settings_preserve_legacy_local_chat_with_azure_embeddings():
    settings = RuntimeSettings.from_env(
        {
            "OPENAI_HOST": "local",
            "OPENAI_BASE_URL": "http://ollama:11434/v1",
            "AZURE_OPENAI_API_KEY_OVERRIDE": "azure-only-secret",
            "AZURE_OPENAI_SERVICE": "example-openai",
            "AZURE_OPENAI_CHATGPT_MODEL": "local-model",
        }
    )

    assert settings.llm.provider == ModelProvider.OPENAI_COMPATIBLE
    assert settings.llm.base_url == "http://ollama:11434/v1"
    assert settings.llm.api_key is None
    assert settings.llm.deployment is None
    assert settings.embedding.provider == ModelProvider.AZURE_OPENAI


def test_runtime_settings_support_independent_local_providers():
    settings = RuntimeSettings.from_env(
        {
            "APP_RUNTIME_MODE": "local",
            "LLM_PROVIDER": "openai_compatible",
            "LLM_BASE_URL": "http://vllm:8000/v1",
            "LLM_MODEL": "qwen-chat",
            "EMBEDDING_PROVIDER": "openai_compatible",
            "EMBEDDING_BASE_URL": "http://embedding:8001/v1",
            "EMBEDDING_MODEL": "qwen-embedding",
            "EMBEDDING_DIMENSIONS": "1024",
        }
    )

    assert settings.mode == RuntimeMode.LOCAL
    assert settings.llm.provider == ModelProvider.OPENAI_COMPATIBLE
    assert settings.llm.model == "qwen-chat"
    assert settings.embedding.provider == ModelProvider.OPENAI_COMPATIBLE
    assert settings.embedding.model == "qwen-embedding"
    assert settings.embedding.base_url == "http://embedding:8001/v1"
    assert settings.embedding.dimensions == 1024


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"APP_RUNTIME_MODE": "desktop"}, "APP_RUNTIME_MODE"),
        ({"LLM_PROVIDER": "unknown"}, "Unsupported model provider"),
        ({"EMBEDDING_DIMENSIONS": "zero"}, "must be an integer"),
        ({"EMBEDDING_DIMENSIONS": "0"}, "greater than zero"),
    ],
)
def test_runtime_settings_reject_invalid_values(env, message):
    with pytest.raises(ValueError, match=message):
        RuntimeSettings.from_env(env)
