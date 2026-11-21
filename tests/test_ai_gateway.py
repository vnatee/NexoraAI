from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from quart import Quart

import app
import core.ai_gateway as ai_gateway
from core.ai_gateway import (
    MuleSoftClientIdEnforcementAuth,
    build_external_gateway_profiles,
    gateway_error_diagnostic,
    run_gateway_conformance,
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


async def _async_value(value):
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


def test_mulesoft_adapter_is_persisted_and_legacy_auth_is_inferred(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    normalized = normalize_ai_gateway_settings(
        _payload(
            gateway_adapter="mulesoft",
            auth_type="mulesoft_client_id_enforcement",
            api_key="",
            client_id="client-1",
            client_secret="mulesoft-secret",
        )
    )
    assert normalized["gateway_adapter"] == "mulesoft"
    assert serialize_ai_gateway_settings(normalized)["gateway_adapter"] == "mulesoft"

    legacy = dict(normalized)
    legacy.pop("gateway_adapter")
    assert serialize_ai_gateway_settings(legacy)["gateway_adapter"] == "mulesoft"


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


def test_gateway_diagnostic_exposes_only_safe_status_and_correlation_metadata():
    class UpstreamError(Exception):
        status_code = 401
        response = SimpleNamespace(
            status_code=401,
            headers={
                "x-correlation-id": "correlation-1",
                "apim-request-id": "apim-1",
                "authorization": "secret-value",
            },
            text="secret upstream detail",
        )

    diagnostic = gateway_error_diagnostic(UpstreamError("secret exception detail"))

    assert diagnostic == {
        "code": "authentication_failed",
        "http_status": 401,
        "correlation_ids": {
            "x-correlation-id": "correlation-1",
            "apim-request-id": "apim-1",
        },
        "error_type": "UpstreamError",
    }
    assert "secret" not in str(diagnostic)


@pytest.mark.asyncio
async def test_gateway_conformance_passes_chat_stream_and_declared_tools(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    settings = normalize_ai_gateway_settings(_payload())

    class Stream:
        def __init__(self):
            self.sent = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.sent:
                raise StopAsyncIteration
            self.sent = True
            return SimpleNamespace()

        async def close(self):
            return None

    class Completions:
        async def create(self, **kwargs):
            if kwargs.get("stream"):
                return Stream()
            if kwargs.get("tools"):
                tool_call = SimpleNamespace(
                    function=SimpleNamespace(name="gateway_probe")
                )
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(tool_calls=[tool_call])
                        )
                    ]
                )
            return SimpleNamespace(choices=[])

    class GatewayClient:
        chat = SimpleNamespace(completions=Completions())

        async def close(self):
            return None

    monkeypatch.setattr(
        ai_gateway, "create_external_gateway_client", lambda _settings: GatewayClient()
    )

    report = await run_gateway_conformance(settings)

    assert report["ready"] is True
    assert {item["name"]: item["status"] for item in report["checks"]} == {
        "gateway_authentication": "passed",
        "chat_completion": "passed",
        "streaming": "passed",
        "tool_calling": "passed",
        "vision": "skipped",
    }


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
    assert body["diagnostic"]["code"] == "openai_compatibility_failed"
    assert "openai_compatibility_failed" in body["error"]
    assert "secret upstream detail" not in str(body)
    assert events[0]["error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_gateway_conformance_route_returns_safe_report_and_audits(client, monkeypatch):
    report = {
        "ready": False,
        "adapter": "mulesoft",
        "model_id": "general",
        "model_alias": "enterprise/general",
        "checks": [
            {
                "name": "gateway_authentication",
                "status": "failed",
                "required": True,
                "code": "authentication_failed",
                "http_status": 401,
                "correlation_ids": {"x-correlation-id": "correlation-1"},
            }
        ],
    }
    events = []
    monkeypatch.setattr(
        app, "_require_system_admin", lambda _claims: {"_id": "admin-1"}
    )
    monkeypatch.setattr(
        app,
        "get_ai_gateway_settings",
        lambda: {"mode": "external", "gateway_adapter": "mulesoft"},
    )
    monkeypatch.setattr(app, "run_gateway_conformance", lambda _settings: _async_value(report))
    monkeypatch.setattr(
        app, "insert_integration_lifecycle_event", lambda **event: events.append(event)
    )

    response = await client.post("/admin/ai-gateway/conformance")

    assert response.status_code == 200
    assert await response.get_json() == report
    assert events[0]["action"] == "ai_gateway_conformance"
    assert events[0]["status"] == "failed"
    assert events[0]["error_type"] == "authentication_failed"


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
