import pytest
from cryptography.fernet import Fernet
from types import SimpleNamespace

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
            "tool_capability_status": "unknown",
            "supports_vision": False,
            "vision_capability_status": "unknown",
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


def test_provider_payload_preserves_or_resets_detected_tool_capability(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
    existing = {
        "provider": "openai_compatible",
        "vendor": "ollama",
        "base_url": "http://localhost:11434/v1",
        "api_key_ciphertext": None,
        "models": [
            {
                "id": "qwen",
                "label": "Qwen",
                "model": "qwen3",
                "deployment": None,
                "supports_tools": False,
                "tool_capability_status": "unsupported",
                "tool_capability_checked_at": "2026-08-20T00:00:00+00:00",
                "tool_capability_detail": "no_tool_call_returned",
                "supports_vision": True,
                "vision_capability_status": "supported",
                "vision_capability_checked_at": "2026-08-20T00:00:00+00:00",
                "vision_capability_detail": "image_request_accepted",
            }
        ],
    }
    payload = {
        "name": "Ollama",
        "vendor": "ollama",
        "enabled": True,
        "models": [
            {
                "id": "qwen",
                "label": "Renamed",
                "model": "qwen3",
                "supports_tools": True,
                "supports_vision": True,
            }
        ],
    }
    preserved = app._normalize_llm_provider_payload(payload, existing=existing)["models"][0]
    assert preserved["supports_tools"] is False
    assert preserved["tool_capability_status"] == "unsupported"
    assert preserved["tool_capability_checked_at"] == "2026-08-20T00:00:00+00:00"
    assert preserved["supports_vision"] is True
    assert preserved["vision_capability_status"] == "supported"
    assert preserved["vision_capability_checked_at"] == "2026-08-20T00:00:00+00:00"

    payload["models"][0]["model"] = "qwen4"
    reset = app._normalize_llm_provider_payload(payload, existing=existing)["models"][0]
    assert reset["supports_tools"] is True
    assert reset["tool_capability_status"] == "unknown"
    assert reset["vision_capability_status"] == "unknown"
    assert "tool_capability_checked_at" not in reset
    assert "vision_capability_checked_at" not in reset


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _fake_client(*responses):
    completions = FakeCompletions(responses)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def _tool_response(tool_name="report_tool_support"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    tool_calls=[SimpleNamespace(function=SimpleNamespace(name=tool_name))]
                )
            )
        ]
    )


@pytest.mark.asyncio
async def test_tool_capability_probe_detects_supported_model():
    client, completions = _fake_client(_tool_response())
    status, detail = await app._probe_model_tool_capability(
        client,
        _system_profile().settings,
        {"vendor": "azure_openai", "provider": "azure_openai"},
    )
    assert (status, detail) == ("supported", "tool_call_returned")
    assert completions.requests[0]["tool_choice"] == "required"


@pytest.mark.asyncio
async def test_tool_capability_probe_detects_provider_rejection():
    client, _ = _fake_client(ValueError("This model does not support tools"))
    status, detail = await app._probe_model_tool_capability(
        client,
        _system_profile().settings,
        {"vendor": "azure_openai", "provider": "azure_openai"},
    )
    assert (status, detail) == ("unsupported", "provider_rejected_tool_calling")


@pytest.mark.asyncio
async def test_tool_capability_probe_keeps_ambiguous_failure_unknown():
    client, _ = _fake_client(RuntimeError("rate limit exceeded"))
    status, detail = await app._probe_model_tool_capability(
        client,
        _system_profile().settings,
        {"vendor": "azure_openai", "provider": "azure_openai"},
    )
    assert (status, detail) == ("unknown", "probe_inconclusive")


def test_tool_capability_result_is_persisted_for_only_tested_model(monkeypatch):
    provider = {
        "_id": "provider-1",
        "models": [
            {"id": "model-a", "supports_tools": True},
            {"id": "model-b", "supports_tools": True},
        ],
    }

    def fake_update(provider_id, updates):
        assert provider_id == "provider-1"
        return {**provider, **updates}

    monkeypatch.setattr(app, "update_llm_provider", fake_update)
    updated = app._store_model_tool_capability(
        provider, "model-a", "unsupported", "provider_rejected_tool_calling"
    )
    assert updated["models"][0]["supports_tools"] is False
    assert updated["models"][0]["tool_capability_status"] == "unsupported"
    assert updated["models"][0]["tool_capability_checked_at"]
    assert updated["models"][1] == {"id": "model-b", "supports_tools": True}


@pytest.mark.asyncio
async def test_vision_capability_probe_detects_supported_model():
    client, completions = _fake_client(SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))]))

    status, detail = await app._probe_model_vision_capability(
        client,
        _system_profile().settings,
        {"vendor": "azure_openai", "provider": "azure_openai"},
    )

    assert (status, detail) == ("supported", "image_request_accepted")
    content = completions.requests[0]["messages"][0]["content"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_vision_capability_probe_detects_provider_rejection():
    client, _ = _fake_client(ValueError("This model does not support image input"))

    status, detail = await app._probe_model_vision_capability(
        client,
        _system_profile().settings,
        {"vendor": "azure_openai", "provider": "azure_openai"},
    )

    assert (status, detail) == ("unsupported", "provider_rejected_image_input")


@pytest.mark.asyncio
async def test_vision_capability_probe_keeps_ambiguous_failure_unknown():
    client, _ = _fake_client(RuntimeError("rate limit exceeded"))

    status, detail = await app._probe_model_vision_capability(
        client,
        _system_profile().settings,
        {"vendor": "azure_openai", "provider": "azure_openai"},
    )

    assert (status, detail) == ("unknown", "probe_inconclusive")


def test_vision_capability_result_is_persisted_for_only_tested_model(monkeypatch):
    provider = {
        "_id": "provider-1",
        "models": [
            {"id": "model-a", "supports_vision": False},
            {"id": "model-b", "supports_vision": True},
        ],
    }

    monkeypatch.setattr(app, "update_llm_provider", lambda _provider_id, updates: {**provider, **updates})
    updated = app._store_model_vision_capability(
        provider, "model-a", "supported", "image_request_accepted"
    )

    assert updated["models"][0]["supports_vision"] is True
    assert updated["models"][0]["vision_capability_status"] == "supported"
    assert updated["models"][0]["vision_capability_checked_at"]
    assert updated["models"][1] == {"id": "model-b", "supports_vision": True}
