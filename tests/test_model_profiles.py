import json

import pytest

from core.model_profiles import DEFAULT_LLM_PROFILE_ID, load_llm_profiles
from core.runtime_settings import LLMProviderSettings, ModelProvider


@pytest.fixture
def default_llm_settings():
    return LLMProviderSettings(
        provider=ModelProvider.AZURE_OPENAI,
        model="gpt-4.1-mini",
        deployment="chat-default",
        api_version="2024-10-21",
        endpoint="https://example.openai.azure.com",
        base_url=None,
        api_key=None,
        organization=None,
    )


def test_load_llm_profiles_always_includes_system_default(default_llm_settings):
    profiles = load_llm_profiles({}, default_llm_settings)

    assert list(profiles) == [DEFAULT_LLM_PROFILE_ID]
    assert profiles[DEFAULT_LLM_PROFILE_ID].settings is default_llm_settings


def test_load_llm_profiles_supports_multiple_safe_profiles(default_llm_settings):
    profile_json = json.dumps(
        [
            {
                "id": "local-qwen",
                "label": "Local Qwen",
                "provider": "openai_compatible",
                "model": "qwen3",
                "base_url": "http://ollama:11434/v1",
            },
            {
                "id": "openai-fast",
                "label": "OpenAI Fast",
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "api_key_env": "OPENAI_FAST_KEY",
            },
        ]
    )

    profiles = load_llm_profiles(
        {"LLM_PROFILES_JSON": profile_json, "OPENAI_FAST_KEY": "secret"},
        default_llm_settings,
    )

    assert profiles["local-qwen"].settings.base_url == "http://ollama:11434/v1"
    assert profiles["openai-fast"].settings.api_key == "secret"
    assert "api_key" not in profiles["openai-fast"].public_dict()


@pytest.mark.parametrize(
    ("profiles", "message"),
    [
        ("{}", "JSON array"),
        ('[{"id":"system","label":"Bad","provider":"openai_compatible","model":"x","base_url":"http://x"}]', "reserved"),
        ('[{"id":"local","label":"Local","provider":"openai_compatible","model":"x"}]', "requires base_url"),
        ('[{"id":"cloud","label":"Cloud","provider":"openai","model":"x"}]', "requires api_key_env"),
    ],
)
def test_load_llm_profiles_rejects_invalid_profiles(default_llm_settings, profiles, message):
    with pytest.raises(ValueError, match=message):
        load_llm_profiles({"LLM_PROFILES_JSON": profiles}, default_llm_settings)
