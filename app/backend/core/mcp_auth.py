import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx2


@dataclass(frozen=True)
class EntraClientCredentials:
    tenant_id: str
    client_id: str
    client_secret: str
    scope: str


_token_cache: dict[str, tuple[str, float, str]] = {}
_token_locks: dict[str, asyncio.Lock] = {}


def clear_mcp_token_cache(connection_id: str | None = None) -> None:
    if connection_id:
        _token_cache.pop(connection_id, None)
        _token_locks.pop(connection_id, None)
        return
    _token_cache.clear()
    _token_locks.clear()


async def entra_authorization_header(
    connection_id: str,
    credentials: EntraClientCredentials,
    *,
    timeout_seconds: float = 15,
) -> dict[str, str]:
    now = time.monotonic()
    credential_fingerprint = hashlib.sha256(
        "\0".join(
            (
                credentials.tenant_id,
                credentials.client_id,
                credentials.client_secret,
                credentials.scope,
            )
        ).encode("utf-8")
    ).hexdigest()
    cached = _token_cache.get(connection_id)
    if cached and cached[1] > now + 30 and cached[2] == credential_fingerprint:
        return {"Authorization": f"Bearer {cached[0]}"}

    lock = _token_locks.setdefault(connection_id, asyncio.Lock())
    async with lock:
        now = time.monotonic()
        cached = _token_cache.get(connection_id)
        if cached and cached[1] > now + 30 and cached[2] == credential_fingerprint:
            return {"Authorization": f"Bearer {cached[0]}"}

        tenant = quote(credentials.tenant_id, safe="")
        token_url = (
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        )
        async with httpx2.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": credentials.client_id,
                    "client_secret": credentials.client_secret,
                    "scope": credentials.scope,
                },
            )
        if response.status_code >= 400:
            raise ValueError(
                f"Microsoft Entra token request failed ({response.status_code})"
            )
        payload: Any = response.json()
        token = str(payload.get("access_token") or "") if isinstance(payload, dict) else ""
        if not token:
            raise ValueError("Microsoft Entra token response did not include an access token")
        try:
            expires_in = max(60, int(payload.get("expires_in") or 3600))
        except (TypeError, ValueError):
            expires_in = 3600
        _token_cache[connection_id] = (
            token,
            time.monotonic() + expires_in,
            credential_fingerprint,
        )
        return {"Authorization": f"Bearer {token}"}
