from types import SimpleNamespace

import pytest

from core import mcp_auth
from core.mcp_auth import EntraClientCredentials, entra_authorization_header


@pytest.mark.asyncio
async def test_entra_client_credentials_token_is_cached(monkeypatch):
    requests = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"access_token": "short-lived-token", "expires_in": 3600}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **kwargs):
            requests.append((url, kwargs))
            return Response()

    monkeypatch.setattr(
        mcp_auth.httpx2,
        "AsyncClient",
        lambda **_kwargs: Client(),
    )
    mcp_auth.clear_mcp_token_cache()
    credentials = EntraClientCredentials(
        tenant_id="tenant-a",
        client_id="client-a",
        client_secret="secret-a",
        scope="api://server/.default",
    )

    first = await entra_authorization_header("connection-a", credentials)
    second = await entra_authorization_header("connection-a", credentials)

    assert first == second == {"Authorization": "Bearer short-lived-token"}
    assert len(requests) == 1
    assert requests[0][1]["data"] == {
        "grant_type": "client_credentials",
        "client_id": "client-a",
        "client_secret": "secret-a",
        "scope": "api://server/.default",
    }


@pytest.mark.asyncio
async def test_entra_token_error_does_not_expose_response_body(monkeypatch):
    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return SimpleNamespace(status_code=401, json=lambda: {"error": "secret-detail"})

    monkeypatch.setattr(mcp_auth.httpx2, "AsyncClient", lambda **_kwargs: Client())
    mcp_auth.clear_mcp_token_cache()

    with pytest.raises(ValueError, match=r"failed \(401\)") as error:
        await entra_authorization_header(
            "connection-b",
            EntraClientCredentials("tenant", "client", "secret", "scope"),
        )

    assert "secret-detail" not in str(error.value)
