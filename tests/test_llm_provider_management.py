import pytest
from cryptography.fernet import Fernet

import app
from core.model_profiles import DEFAULT_LLM_PROFILE_ID, LLMProfile
from core.provider_secrets import decrypt_provider_secret
from core.runtime_settings import LLMProviderSettings, ModelProvider


def _system_profile():
    settings = LLMProviderSettings(
        provider=ModelProvider.AZURE_OPENAI,
        model="gpt-4.1-mini",
        deployment="chat-default",
        api_version="2024-10-21",
        endpoint="https://example.openai.azure.com",
        base_url=None,
        api_key=None,
        organization=None,
    )
    return LLMProfile(DEFAULT_LLM_PROFILE_ID, "System default", settings)


def test_provider_payload_encrypts_secret_and_normalizes_models(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))

    result = app._normalize_llm_provider_payload(
        {
            "name": "Local gateway",
            "provider": "openai_compatible",
            "base_url": "http://gateway:8000/v1",
            "api_key": "secret",
            "models": [{"id": "qwen", "model": "qwen3"}],
        }
    )

    assert result["provider"] == "openai_compatible"
    assert result["vendor"] == "other_openai_compatible"
    assert result["api_version"] is None
    assert decrypt_provider_secret(result["api_key_ciphertext"]) == "secret"
    assert result["models"] == [
        {
            "id": "qwen",
            "label": "qwen3",
            "model": "qwen3",
            "deployment": None,
            "supports_tools": True,
        }
    ]


def test_provider_serialization_never_returns_secret():
    result = app._serialize_llm_provider(
        {
            "_id": "provider-1",
            "name": "Provider",
            "provider": "openai",
            "models": [],
            "api_key_ciphertext": "encrypted-value",
        }
    )

    assert result["has_api_key"] is True
    assert "api_key" not in result
    assert "api_key_ciphertext" not in result
    assert result["vendor"] == "openai"
    assert result["vendor_label"] == "OpenAI"


def test_vendor_selection_derives_adapter_and_default_base_url():
    result = app._normalize_llm_provider_payload(
        {
            "name": "Gemini",
            "vendor": "google_gemini",
            "enabled": False,
            "models": [{"id": "flash", "model": "gemini-3.6-flash"}],
        }
    )

    assert result["vendor"] == "google_gemini"
    assert result["provider"] == "openai_compatible"
    assert result["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai/"


def test_enabled_cloud_vendor_requires_api_key():
    with pytest.raises(ValueError, match="Google Gemini provider requires an API key"):
        app._normalize_llm_provider_payload(
            {
                "name": "Gemini",
                "vendor": "google_gemini",
                "enabled": True,
                "models": [{"id": "flash", "model": "gemini-3.6-flash"}],
            }
        )


def test_existing_compatible_provider_vendor_is_inferred():
    result = app._serialize_llm_provider(
        {
            "_id": "provider-1",
            "name": "Local Ollama",
            "provider": "openai_compatible",
            "base_url": "http://localhost:11434/v1",
            "models": [],
        }
    )

    assert result["vendor"] == "ollama"
    assert result["vendor_label"] == "Ollama (Local)"


def test_enabled_managed_models_become_agent_profiles(monkeypatch):
    monkeypatch.setattr(
        app,
        "list_llm_providers",
        lambda: [
            {
                "_id": "provider-1",
                "name": "Local gateway",
                "provider": "openai_compatible",
                "base_url": "http://gateway:8000/v1",
                "enabled": True,
                "models": [
                    {
                        "id": "qwen",
                        "label": "Qwen",
                        "model": "qwen3",
                        "deployment": None,
                        "supports_tools": False,
                    }
                ],
            },
            {
                "_id": "provider-disabled",
                "name": "Disabled",
                "provider": "openai_compatible",
                "base_url": "http://disabled:8000/v1",
                "enabled": False,
                "models": [{"id": "hidden", "label": "Hidden", "model": "hidden"}],
            },
        ],
    )

    profiles = app._load_managed_profiles({DEFAULT_LLM_PROFILE_ID: _system_profile()})

    assert "managed:provider-1:qwen" in profiles
    assert profiles["managed:provider-1:qwen"].label == "Local gateway — Qwen"
    assert profiles["managed:provider-1:qwen"].supports_tools is False
    assert "managed:provider-disabled:hidden" not in profiles
