"""Provider-neutral external AI Gateway client and effective model profiles."""

from __future__ import annotations

import asyncio
import json
import os
import ssl
import tempfile
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from openai import AsyncOpenAI

from core.model_profiles import DEFAULT_LLM_PROFILE_ID, LLMProfile
from core.provider_secrets import decrypt_secret
from core.runtime_settings import LLMProviderSettings, ModelProvider

_CORRELATION_HEADERS = (
    "x-correlation-id",
    "apim-request-id",
    "x-request-id",
    "x-amzn-requestid",
    "traceparent",
)
_VISION_PROBE_IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2"
    "nAAAAABJRU5ErkJggg=="
)


def _semantic_request(request: httpx.Request) -> httpx.Request:
    """Remove caller model selection for a MuleSoft semantic Model Proxy."""

    if not request.url.path.rstrip("/").endswith("/chat/completions"):
        return request
    try:
        payload = json.loads(request.content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return request
    if not isinstance(payload, dict) or "model" not in payload:
        return request
    payload.pop("model", None)
    headers = dict(request.headers)
    headers.pop("content-length", None)
    headers.pop("transfer-encoding", None)
    return httpx.Request(
        method=request.method,
        url=request.url,
        headers=headers,
        content=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        extensions=request.extensions,
    )


class SemanticRoutingTransport(httpx.AsyncBaseTransport):
    """HTTP transport that leaves model selection to MuleSoft Semantic Routing."""

    def __init__(self, transport: httpx.AsyncBaseTransport) -> None:
        self._transport = transport

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return await self._transport.handle_async_request(_semantic_request(request))

    async def aclose(self) -> None:
        await self._transport.aclose()


class OAuth2ClientCredentialsAuth(httpx.Auth):
    """Small async OAuth2 client-credentials cache for gateway requests."""

    def __init__(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str = "",
        audience: str = "",
        client_auth_method: str = "client_secret_post",
        timeout_seconds: int = 30,
        ssl_context: ssl.SSLContext | bool = True,
    ) -> None:
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.audience = audience
        self.client_auth_method = client_auth_method
        self.timeout_seconds = timeout_seconds
        self.ssl_context = ssl_context
        self._access_token = ""
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def _token(self) -> str:
        if self._access_token and time.monotonic() < self._expires_at:
            return self._access_token
        async with self._lock:
            if self._access_token and time.monotonic() < self._expires_at:
                return self._access_token
            form = {"grant_type": "client_credentials"}
            token_auth = None
            if self.client_auth_method == "client_secret_basic":
                token_auth = httpx.BasicAuth(self.client_id, self.client_secret)
            else:
                form["client_id"] = self.client_id
                form["client_secret"] = self.client_secret
            if self.scope:
                form["scope"] = self.scope
            if self.audience:
                form["audience"] = self.audience
            async with httpx.AsyncClient(
                verify=self.ssl_context,
                timeout=self.timeout_seconds,
            ) as client:
                response = await client.post(self.token_url, data=form, auth=token_auth)
                response.raise_for_status()
                payload = response.json()
            token = str(payload.get("access_token") or "").strip()
            if not token:
                raise ValueError("OAuth token response did not contain access_token")
            try:
                expires_in = max(60, int(payload.get("expires_in") or 300))
            except (TypeError, ValueError):
                expires_in = 300
            self._access_token = token
            self._expires_at = time.monotonic() + max(30, expires_in - 60)
            return token

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        request.headers["Authorization"] = f"Bearer {await self._token()}"
        yield request


class GatewayManagedAuth(httpx.Auth):
    """Remove the SDK placeholder credential when the gateway owns authentication."""

    def auth_flow(self, request: httpx.Request):
        request.headers.pop("Authorization", None)
        yield request


class MuleSoftClientIdEnforcementAuth(httpx.Auth):
    """Apply MuleSoft Client ID Enforcement credentials to gateway requests."""

    def __init__(self, *, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    def auth_flow(self, request: httpx.Request):
        # AsyncOpenAI always prepares a Bearer credential. MuleSoft Client ID
        # Enforcement authenticates with request headers instead, so do not
        # leak the SDK placeholder or imply that it is a usable bearer token.
        request.headers.pop("Authorization", None)
        request.headers["client_id"] = self.client_id
        request.headers["client_secret"] = self.client_secret
        request.headers["ClientId"] = self.client_id
        yield request


def gateway_error_diagnostic(error: Exception) -> dict[str, Any]:
    """Return bounded, credential-free metadata for an upstream failure."""

    response = getattr(error, "response", None)
    status_code = getattr(error, "status_code", None)
    if status_code is None and response is not None:
        status_code = getattr(response, "status_code", None)
    try:
        status_code = int(status_code) if status_code is not None else None
    except (TypeError, ValueError):
        status_code = None

    if status_code in {401, 403}:
        code = "authentication_failed"
    elif status_code == 404:
        code = "route_or_model_not_found"
    elif status_code == 408:
        code = "upstream_timeout"
    elif status_code == 429:
        code = "rate_limited"
    elif status_code is not None and status_code >= 500:
        code = "upstream_unavailable"
    elif isinstance(error, (httpx.TimeoutException, asyncio.TimeoutError)):
        code = "upstream_timeout"
    elif isinstance(error, httpx.TransportError):
        code = "transport_failed"
    else:
        code = "openai_compatibility_failed"

    headers = getattr(response, "headers", {}) if response is not None else {}
    correlation_ids: dict[str, str] = {}
    for name in _CORRELATION_HEADERS:
        value = str(headers.get(name) or "").strip()
        if value:
            correlation_ids[name] = value[:200]
    return {
        "code": code,
        "http_status": status_code,
        "correlation_ids": correlation_ids,
        "error_type": type(error).__name__,
    }


def gateway_diagnostic_message(diagnostic: dict[str, Any]) -> str:
    """Create a safe operator message without including an upstream body."""

    status = diagnostic.get("http_status")
    code = str(diagnostic.get("code") or "gateway_failed")
    message = f"AI Gateway check failed ({code})"
    if status is not None:
        message += f" with HTTP {status}"
    correlation_ids = diagnostic.get("correlation_ids") or {}
    if correlation_ids:
        references = ", ".join(
            f"{name}={value}" for name, value in correlation_ids.items()
        )
        message += f". Correlation: {references}"
    return message


def _ssl_context(settings: dict[str, Any]) -> ssl.SSLContext:
    ca_certificate = decrypt_secret(settings.get("ca_certificate_ciphertext"))
    context = ssl.create_default_context(cadata=ca_certificate or None)
    if not settings.get("mtls_enabled"):
        return context
    certificate = decrypt_secret(settings.get("client_certificate_ciphertext")) or ""
    private_key = decrypt_secret(settings.get("client_private_key_ciphertext")) or ""
    certificate_path = ""
    private_key_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False
        ) as certificate_file:
            certificate_file.write(certificate)
            certificate_path = certificate_file.name
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False
        ) as private_key_file:
            private_key_file.write(private_key)
            private_key_path = private_key_file.name
        os.chmod(certificate_path, 0o600)
        os.chmod(private_key_path, 0o600)
        context.load_cert_chain(certificate_path, private_key_path)
    finally:
        for path in (certificate_path, private_key_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass
    return context


def gateway_model_settings(
    settings: dict[str, Any], model: dict[str, Any]
) -> LLMProviderSettings:
    return LLMProviderSettings(
        provider=ModelProvider.OPENAI_COMPATIBLE,
        model=str(model["model"]),
        deployment=None,
        api_version="",
        endpoint=None,
        base_url=gateway_route_base_url(settings, model),
        api_key=decrypt_secret(settings.get("api_key_ciphertext")),
        organization=None,
    )


def gateway_route_base_url(
    settings: dict[str, Any], route: dict[str, Any] | None
) -> str:
    """Resolve a proxy endpoint while preserving legacy full-route URLs."""

    selected = route or {}
    override = str(selected.get("base_url") or "").strip().rstrip("/")
    if override:
        return override
    base_url = str(settings["base_url"]).rstrip("/")
    proxy_path = str(selected.get("proxy_path") or "").strip().strip("/")
    return f"{base_url}/{proxy_path}" if proxy_path else base_url


def build_external_gateway_profiles(settings: dict[str, Any]) -> dict[str, LLMProfile]:
    models = list(settings.get("models") or [])
    default_model_id = str(settings.get("default_model_id") or "")
    default_model = next(
        (item for item in models if item.get("id") == default_model_id), None
    )
    if default_model is None:
        raise ValueError("External AI Gateway default model is unavailable")
    profiles: dict[str, LLMProfile] = {
        DEFAULT_LLM_PROFILE_ID: LLMProfile(
            profile_id=DEFAULT_LLM_PROFILE_ID,
            label=(
                f"{settings.get('name') or 'External AI Gateway'} — "
                f"Default ({default_model.get('label') or default_model['model']})"
            ),
            settings=gateway_model_settings(settings, default_model),
            managed_provider_id="ai_gateway",
            managed_model_id=str(default_model["id"]),
            supports_tools=default_model.get("supports_tools", True) is not False,
            supports_vision=default_model.get("supports_vision", False) is True,
        )
    }
    for model in models:
        profile_id = f"gateway:{model['id']}"
        profile_kind = (
            "Semantic Proxy"
            if model.get("routing_strategy") == "semantic"
            else "Pinned Proxy"
        )
        profiles[profile_id] = LLMProfile(
            profile_id=profile_id,
            label=(
                f"{settings.get('name') or 'External AI Gateway'} — "
                f"{model.get('label') or model['model']} ({profile_kind})"
            ),
            settings=gateway_model_settings(settings, model),
            managed_provider_id="ai_gateway",
            managed_model_id=str(model["id"]),
            supports_tools=model.get("supports_tools", True) is not False,
            supports_vision=model.get("supports_vision", False) is True,
        )
    return profiles


def create_external_gateway_client(
    settings: dict[str, Any], model: dict[str, Any] | None = None
) -> AsyncOpenAI:
    ssl_context = _ssl_context(settings)
    auth_type = str(settings.get("auth_type") or "none")
    auth: httpx.Auth | None = GatewayManagedAuth() if auth_type == "none" else None
    api_key = (
        decrypt_secret(settings.get("api_key_ciphertext")) or "gateway-managed-auth"
    )
    if auth_type == "oauth2_client_credentials":
        auth = OAuth2ClientCredentialsAuth(
            token_url=str(settings.get("token_url") or ""),
            client_id=str(settings.get("client_id") or ""),
            client_secret=decrypt_secret(settings.get("client_secret_ciphertext"))
            or "",
            scope=str(settings.get("oauth_scope") or ""),
            audience=str(settings.get("oauth_audience") or ""),
            client_auth_method=str(
                settings.get("oauth_client_auth_method") or "client_secret_post"
            ),
            timeout_seconds=int(settings.get("timeout_seconds") or 60),
            ssl_context=ssl_context,
        )
    elif auth_type == "mulesoft_client_id_enforcement":
        auth = MuleSoftClientIdEnforcementAuth(
            client_id=str(settings.get("client_id") or ""),
            client_secret=decrypt_secret(
                settings.get("client_secret_ciphertext")
            )
            or "",
        )
    route = model or {}
    base_transport: httpx.AsyncBaseTransport = httpx.AsyncHTTPTransport(
        verify=ssl_context
    )
    transport = (
        SemanticRoutingTransport(base_transport)
        if route.get("routing_strategy") == "semantic"
        else base_transport
    )
    http_client = httpx.AsyncClient(
        auth=auth,
        transport=transport,
        timeout=int(settings.get("timeout_seconds") or 60),
    )
    return AsyncOpenAI(
        base_url=gateway_route_base_url(settings, route),
        api_key=api_key,
        http_client=http_client,
    )


def gateway_model_by_id(
    settings: dict[str, Any], model_id: str | None
) -> dict[str, Any]:
    selected_id = str(model_id or settings.get("default_model_id") or "")
    model = next(
        (item for item in settings.get("models") or [] if item.get("id") == selected_id),
        None,
    )
    if model is None:
        raise ValueError("External AI Gateway route is unavailable")
    return model


def _check(
    name: str,
    *,
    status: str,
    required: bool,
    diagnostic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": name,
        "status": status,
        "required": required,
    }
    if diagnostic:
        result.update(
            {
                "code": diagnostic.get("code"),
                "http_status": diagnostic.get("http_status"),
                "correlation_ids": diagnostic.get("correlation_ids") or {},
                "error_type": diagnostic.get("error_type"),
            }
        )
    return result


def _gateway_adapter(settings: dict[str, Any]) -> str:
    return str(
        settings.get("gateway_adapter")
        or (
            "mulesoft"
            if settings.get("auth_type") == "mulesoft_client_id_enforcement"
            else "generic_openai"
        )
    )


async def run_gateway_conformance(
    settings: dict[str, Any],
    model_id: str | None = None,
    probe_prompt: str | None = None,
) -> dict[str, Any]:
    """Run bounded OpenAI-compatible probes against the saved gateway route."""

    profiles = build_external_gateway_profiles(settings)
    route = gateway_model_by_id(settings, model_id)
    profile_id = (
        DEFAULT_LLM_PROFILE_ID
        if route.get("id") == settings.get("default_model_id")
        else f"gateway:{route['id']}"
    )
    profile = profiles[profile_id]
    model = profile.settings.model
    routing_strategy = str(route.get("routing_strategy") or "model_based")
    prompt = str(probe_prompt or "").strip()
    if len(prompt) > 2_000:
        raise ValueError("Gateway probe prompt exceeds 2000 characters")
    if routing_strategy == "semantic" and not prompt:
        raise ValueError("Semantic Model Proxy requires a probe prompt")
    prompt = prompt or "Reply with OK"
    client = create_external_gateway_client(settings, route)
    checks: list[dict[str, Any]] = []
    selected_model = ""
    try:
        try:
            completion = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8,
            )
            checks.append(
                _check("gateway_authentication", status="passed", required=True)
            )
            checks.append(_check("chat_completion", status="passed", required=True))
            selected_model = str(getattr(completion, "model", "") or "")[:255]
            if routing_strategy == "semantic":
                checks.append(
                    _check("semantic_routing", status="passed", required=True)
                )
        except Exception as error:
            diagnostic = gateway_error_diagnostic(error)
            auth_status = (
                "failed"
                if diagnostic["code"] == "authentication_failed"
                else "inconclusive"
            )
            checks.append(
                _check(
                    "gateway_authentication",
                    status=auth_status,
                    required=True,
                    diagnostic=diagnostic,
                )
            )
            if routing_strategy == "semantic":
                checks.append(
                    _check(
                        "semantic_routing",
                        status="failed",
                        required=True,
                        diagnostic=diagnostic,
                    )
                )
            checks.append(
                _check(
                    "chat_completion",
                    status="failed",
                    required=True,
                    diagnostic=diagnostic,
                )
            )
            checks.extend(
                [
                    _check("streaming", status="skipped", required=True),
                    _check(
                        "tool_calling",
                        status="skipped",
                        required=profile.supports_tools,
                    ),
                    _check(
                        "vision",
                        status="skipped",
                        required=profile.supports_vision,
                    ),
                ]
            )
            return {
                "ready": False,
                "adapter": _gateway_adapter(settings),
                "model_id": route.get("id"),
                "model_alias": model,
                "routing_strategy": routing_strategy,
                "selected_model": selected_model,
                "checks": checks,
            }

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8,
                stream=True,
            )
            received_chunk = False
            async for _chunk in stream:
                received_chunk = True
                break
            await stream.close()
            if not received_chunk:
                raise ValueError("Gateway stream returned no chunks")
            checks.append(_check("streaming", status="passed", required=True))
        except Exception as error:
            checks.append(
                _check(
                    "streaming",
                    status="failed",
                    required=True,
                    diagnostic=gateway_error_diagnostic(error),
                )
            )

        if profile.supports_tools:
            try:
                completion = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": f"{prompt}\nUse gateway_probe with value OK.",
                        }
                    ],
                    tools=[
                        {
                            "type": "function",
                            "function": {
                                "name": "gateway_probe",
                                "description": "Return the conformance probe value.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {"value": {"type": "string"}},
                                    "required": ["value"],
                                    "additionalProperties": False,
                                },
                            },
                        }
                    ],
                    tool_choice={
                        "type": "function",
                        "function": {"name": "gateway_probe"},
                    },
                    max_tokens=32,
                )
                tool_calls = completion.choices[0].message.tool_calls
                if not tool_calls or tool_calls[0].function.name != "gateway_probe":
                    raise ValueError("Gateway did not return the requested tool call")
                checks.append(
                    _check("tool_calling", status="passed", required=True)
                )
            except Exception as error:
                checks.append(
                    _check(
                        "tool_calling",
                        status="failed",
                        required=True,
                        diagnostic=gateway_error_diagnostic(error),
                    )
                )
        else:
            checks.append(_check("tool_calling", status="skipped", required=False))

        if profile.supports_vision:
            try:
                await client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": _VISION_PROBE_IMAGE},
                                },
                            ],
                        }
                    ],
                    max_tokens=8,
                )
                checks.append(_check("vision", status="passed", required=True))
            except Exception as error:
                checks.append(
                    _check(
                        "vision",
                        status="failed",
                        required=True,
                        diagnostic=gateway_error_diagnostic(error),
                    )
                )
        else:
            checks.append(_check("vision", status="skipped", required=False))

        ready = all(
            item["status"] == "passed"
            for item in checks
            if item.get("required") is True
        )
        return {
            "ready": ready,
            "adapter": _gateway_adapter(settings),
            "model_id": route.get("id"),
            "model_alias": model,
            "routing_strategy": routing_strategy,
            "selected_model": selected_model,
            "checks": checks,
        }
    finally:
        await client.close()
