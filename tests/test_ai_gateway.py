from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from quart import Quart

import app
from core.ai_gateway import (
    MuleSoftClientIdEnforcementAuth,
    build_external_gateway_profiles,
)
from core.model_profiles import DEFAULT_LLM_PROFILE_ID, LLMProfile
from core.provider_secrets import decrypt_secret
from core.runtime_settings import LLMProviderSettings, ModelProvider
from mongo_table_connecters.ai_gateway_settings import (
    default_ai_gateway_settings,
    normalize_ai_gateway_settings,
    serialize_ai_gateway_settings,
)


def _payload(**updates):
    value = {
        "mode": "external",
        "name": "Enterprise Gateway",
        "base_url": "https://gateway.example.test/v1",
        "auth_type": "api_key",
        "api_key": "top-secret",
        "models": [
            {
                "id": "general",
                "label": "General",
                "model": "enterprise/general",
                "supports_tools": True,
                "supports_vision": False,
            }
        ],
        "default_model_id": "general",
        "timeout_seconds": 45,
    }
    value.update(updates)
    return value


def _system_profile():
    settings = LLMProviderSettings(
        provider=ModelProvider.OPENAI,
        model="direct-model",
        deployment=None,
        api_version="",
        endpoint=None,
        base_url=None,
        api_key="direct-secret",
        organization=None,
    )
    return LLMProfile(DEFAULT_LLM_PROFILE_ID, "Direct", settings)


def test_external_gateway_settings_encrypt_and_redact_credentials(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())

    normalized = normalize_ai_gateway_settings(_payload())
    public = serialize_ai_gateway_settings(normalized)

    assert decrypt_secret(normalized["api_key_ciphertext"]) == "top-secret"
    assert public["has_api_key"] is True
    assert public["direct_provider_access_blocked"] is True
    assert "api_key" not in public
    assert "api_key_ciphertext" not in public


def test_external_gateway_rejects_http_and_missing_default(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())

    with pytest.raises(ValueError, match="HTTPS"):
        normalize_ai_gateway_settings(_payload(base_url="http://gateway.local/v1"))
    with pytest.raises(ValueError, match="default model"):
        normalize_ai_gateway_settings(_payload(default_model_id="missing"))


def test_external_gateway_oauth_and_mtls_require_complete_credentials(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())

    with pytest.raises(ValueError, match="client id and client secret"):
        normalize_ai_gateway_settings(
            _payload(
                auth_type="oauth2_client_credentials",
                api_key="",
                token_url="https://idp.test/token",
            )
        )
    with pytest.raises(ValueError, match="mTLS"):
        normalize_ai_gateway_settings(_payload(mtls_enabled=True))

    basic = normalize_ai_gateway_settings(
        _payload(
            auth_type="oauth2_client_credentials",
            api_key="",
            token_url="https://idp.test/token",
            client_id="client-1",
            client_secret="oauth-secret",
            oauth_client_auth_method="client_secret_basic",
        )
    )
    assert basic["oauth_client_auth_method"] == "client_secret_basic"


def test_external_gateway_mulesoft_credentials_are_encrypted_and_required(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())

    with pytest.raises(ValueError, match="MuleSoft client id and client secret"):
        normalize_ai_gateway_settings(
            _payload(
                auth_type="mulesoft_client_id_enforcement",
                api_key="",
            )
        )

    normalized = normalize_ai_gateway_settings(
        _payload(
            auth_type="mulesoft_client_id_enforcement",
            api_key="",
            client_id="client-1",
            client_secret="mulesoft-secret",
        )
    )
    public = serialize_ai_gateway_settings(normalized)

    assert decrypt_secret(normalized["client_secret_ciphertext"]) == "mulesoft-secret"
    assert public["client_id"] == "client-1"
    assert public["has_client_secret"] is True
    assert "client_secret" not in public
    assert "client_secret_ciphertext" not in public


def test_mulesoft_auth_applies_expected_headers_without_bearer_placeholder():
    import httpx

    request = httpx.Request(
        "POST",
        "https://gateway.example.test/v1/chat/completions",
        headers={"Authorization": "Bearer gateway-managed-auth"},
    )
    auth = MuleSoftClientIdEnforcementAuth(
        client_id="client-1",
        client_secret="mulesoft-secret",
    )

    authenticated = list(auth.auth_flow(request))[0]

    assert "Authorization" not in authenticated.headers
    assert authenticated.headers["client_id"] == "client-1"
    assert authenticated.headers["client_secret"] == "mulesoft-secret"
    assert authenticated.headers["ClientId"] == "client-1"


def test_direct_development_mode_requires_explicit_deployment_flag():
    with pytest.raises(ValueError, match="disabled"):
        normalize_ai_gateway_settings({"mode": "direct_development"})
    result = normalize_ai_gateway_settings(
        {"mode": "direct_development"}, allow_direct_development=True
    )
    assert result["mode"] == "direct_development"


def test_external_mode_exposes_only_gateway_profiles(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    settings = normalize_ai_gateway_settings(_payload())
    monkeypatch.setattr(
        app,
        "list_llm_providers",
        lambda: [{"_id": "provider-1", "enabled": True, "models": []}],
    )

    profiles, effective = app._load_effective_llm_profiles(
        {DEFAULT_LLM_PROFILE_ID: _system_profile()}, settings
    )

    assert effective is settings
    assert set(profiles) == {DEFAULT_LLM_PROFILE_ID, "gateway:general"}
    assert profiles[DEFAULT_LLM_PROFILE_ID].settings.api_key == "top-secret"
    assert all(
        profile.managed_provider_id == "ai_gateway" for profile in profiles.values()
    )


@pytest.mark.asyncio
async def test_external_gateway_blocks_azure_agentic_retrieval(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    profiles = build_external_gateway_profiles(
        normalize_ai_gateway_settings(_payload())
    )
    quart_app = Quart(__name__)
    quart_app.config[app.CONFIG_LLM_PROFILES] = profiles
    quart_app.config[app.CONFIG_LLM_PROFILE_CLIENTS] = {
        profile_id: object() for profile_id in profiles
    }
    context = {"overrides": {"use_agentic_retrieval": True}}

    async with quart_app.app_context():
        with pytest.raises(app.AccessControlError, match="unavailable"):
            app._apply_agent_llm_profile(context, None)


@pytest.mark.asyncio
async def test_gateway_admin_update_returns_redacted_settings(client, monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    existing = default_ai_gateway_settings()
    saved_documents = []
    audit_events = []
    monkeypatch.setattr(
        app, "_require_system_admin", lambda _claims: {"_id": "admin-1"}
    )
    monkeypatch.setattr(app, "get_ai_gateway_settings", lambda: existing)
    monkeypatch.setattr(
        app,
        "save_ai_gateway_settings",
        lambda data, actor_id: (
            saved_documents.append({"_id": "system", **data}) or saved_documents[-1]
        ),
    )
    monkeypatch.setattr(app, "_refresh_llm_profile_registry", lambda: None)
    monkeypatch.setattr(
        app,
        "insert_integration_lifecycle_event",
        lambda **event: audit_events.append(event),
    )

    class GatewayClient:
        async def close(self):
            return None

    monkeypatch.setattr(
        app, "create_external_gateway_client", lambda _settings: GatewayClient()
    )

    response = await client.put("/admin/ai-gateway", json=_payload())
    body = await response.get_json()

    assert response.status_code == 200
    assert body["mode"] == "external"
    assert body["has_api_key"] is True
    assert "api_key" not in body
    assert "api_key_ciphertext" not in body
    assert decrypt_secret(saved_documents[0]["api_key_ciphertext"]) == "top-secret"
    assert audit_events[0]["action"] == "ai_gateway_updated"


@pytest.mark.asyncio
async def test_gateway_connection_failure_is_generic_and_audited(client, monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    settings = normalize_ai_gateway_settings(_payload())
    events = []
    monkeypatch.setattr(
        app, "_require_system_admin", lambda _claims: {"_id": "admin-1"}
    )
    monkeypatch.setattr(app, "get_ai_gateway_settings", lambda: settings)
    monkeypatch.setattr(
        app, "insert_integration_lifecycle_event", lambda **event: events.append(event)
    )

    class FailingCompletions:
        async def create(self, **_kwargs):
            raise RuntimeError("secret upstream detail")

    class GatewayClient:
        chat = SimpleNamespace(completions=FailingCompletions())

        async def close(self):
            return None

    monkeypatch.setattr(
        app, "create_external_gateway_client", lambda _settings: GatewayClient()
    )

    response = await client.post("/admin/ai-gateway/test")
    body = await response.get_json()

    assert response.status_code == 400
    assert body == {"error": "AI Gateway connection test failed"}
    assert "secret upstream detail" not in str(body)
    assert events[0]["error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_external_mode_blocks_direct_managed_provider_test(client, monkeypatch):
    monkeypatch.setattr(
        app, "_require_system_admin", lambda _claims: {"_id": "admin-1"}
    )
    monkeypatch.setattr(app, "get_ai_gateway_settings", lambda: {"mode": "external"})
    monkeypatch.setattr(
        app,
        "get_llm_provider",
        lambda _provider_id: pytest.fail("Direct provider record must not be used"),
    )

    response = await client.post("/admin/llm-providers/provider-1/test")

    assert response.status_code == 409
    assert "blocked" in (await response.get_json())["error"]


def test_profile_builder_maps_default_and_alias_without_direct_provider(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    settings = normalize_ai_gateway_settings(
        _payload(
            models=[
                {"id": "general", "model": "gateway/general"},
                {"id": "vision", "model": "gateway/vision", "supports_vision": True},
            ]
        )
    )

    profiles = build_external_gateway_profiles(settings)

    assert profiles[DEFAULT_LLM_PROFILE_ID].settings.model == "gateway/general"
    assert profiles["gateway:vision"].supports_vision is True
