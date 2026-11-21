"""Provider-neutral external AI Gateway client and effective model profiles."""

from __future__ import annotations

import asyncio
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
        base_url=str(settings["base_url"]),
        api_key=decrypt_secret(settings.get("api_key_ciphertext")),
        organization=None,
    )


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
            label=f"{settings.get('name') or 'External AI Gateway'} — {default_model.get('label') or default_model['model']}",
            settings=gateway_model_settings(settings, default_model),
            managed_provider_id="ai_gateway",
            managed_model_id=str(default_model["id"]),
            supports_tools=default_model.get("supports_tools", True) is not False,
            supports_vision=default_model.get("supports_vision", False) is True,
        )
    }
    for model in models:
        profile_id = f"gateway:{model['id']}"
        profiles[profile_id] = LLMProfile(
            profile_id=profile_id,
            label=f"{settings.get('name') or 'External AI Gateway'} — {model.get('label') or model['model']}",
            settings=gateway_model_settings(settings, model),
            managed_provider_id="ai_gateway",
            managed_model_id=str(model["id"]),
            supports_tools=model.get("supports_tools", True) is not False,
            supports_vision=model.get("supports_vision", False) is True,
        )
    return profiles


def create_external_gateway_client(settings: dict[str, Any]) -> AsyncOpenAI:
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
    http_client = httpx.AsyncClient(
        auth=auth,
        verify=ssl_context,
        timeout=int(settings.get("timeout_seconds") or 60),
    )
    return AsyncOpenAI(
        base_url=str(settings["base_url"]),
        api_key=api_key,
        http_client=http_client,
    )
