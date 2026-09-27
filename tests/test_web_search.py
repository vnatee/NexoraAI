import json

import pytest
from cryptography.fernet import Fernet

import app as backend_app
from agent_runtime.adapters.web_search import register_web_search_tool
from agent_runtime.tools import ToolRegistry, ToolRuntimeContext
from core.web_search import (
    BraveSearchProvider,
    SearxngSearchProvider,
    WebSearchError,
    WebSearchResult,
    configured_web_search_provider,
    create_web_search_provider,
    governed_web_search,
    normalize_allowed_domains,
)

from mongo_table_connecters import web_search_connections


class FakeProvider:
    name = "fake"

    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, query, limit):
        self.calls.append((query, limit))
        return self.results


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.closed = False

    def json(self):
        return self.payload

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_normalize_allowed_domains_rejects_urls_and_invalid_labels():
    assert normalize_allowed_domains(
        ["*.Docs.DatadogHQ.com.", "docs.datadoghq.com", "learn.microsoft.com"]
    ) == ("docs.datadoghq.com", "learn.microsoft.com")

    for value in (["https://example.com"], ["bad/path"], ["-bad.example"], ["bad-.example"]):
        with pytest.raises(ValueError):
            normalize_allowed_domains(value)


def test_governed_search_filters_and_deduplicates_results():
    provider = FakeProvider(
        [
            WebSearchResult("Allowed", "https://docs.example.com/a#part", "one"),
            WebSearchResult("Duplicate", "https://docs.example.com/a", "two"),
            WebSearchResult("Blocked", "https://example.net/b", "three"),
            WebSearchResult("Credential", "https://user@example.com/c", "four"),
            WebSearchResult("Second", "https://example.com/d", "five"),
        ]
    )

    result = governed_web_search(
        provider,
        "current documentation",
        ("example.com",),
        2,
    )

    assert result["result_count"] == 2
    assert [item["title"] for item in result["results"]] == ["Allowed", "Second"]
    assert result["results"][0]["url"] == "https://docs.example.com/a"
    assert result["searched_at"].endswith("+00:00")
    assert provider.calls == [("current documentation", 6)]


def test_brave_provider_uses_fixed_endpoint_and_secret_header():
    response = FakeResponse(
        {"web": {"results": [{"title": "Doc", "url": "https://example.com", "description": "Text"}]}}
    )
    session = FakeSession(response)
    provider = BraveSearchProvider("secret", timeout_seconds=7, session=session)

    results = provider.search("query", 3)

    assert results[0].title == "Doc"
    url, kwargs = session.calls[0]
    assert url == BraveSearchProvider.endpoint
    assert kwargs["headers"]["X-Subscription-Token"] == "secret"
    assert kwargs["allow_redirects"] is False
    assert response.closed is True


def test_searxng_provider_uses_json_safe_search():
    response = FakeResponse(
        {"results": [{"title": "Doc", "url": "https://example.com", "content": "Text"}]}
    )
    session = FakeSession(response)
    provider = SearxngSearchProvider(
        "https://search.example.com",
        timeout_seconds=4,
        session=session,
    )

    results = provider.search("query", 2)

    assert results[0].snippet == "Text"
    url, kwargs = session.calls[0]
    assert url == "https://search.example.com/search"
    assert kwargs["params"]["format"] == "json"
    assert kwargs["params"]["safesearch"] == 2
    assert kwargs["allow_redirects"] is False


def test_configured_provider_requires_supported_configuration(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "brave")
    monkeypatch.delenv("WEB_SEARCH_API_KEY", raising=False)
    with pytest.raises(WebSearchError):
        configured_web_search_provider()

    monkeypatch.setenv("WEB_SEARCH_API_KEY", "secret")
    assert configured_web_search_provider().name == "brave"

    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "unsupported")
    with pytest.raises(WebSearchError):
        configured_web_search_provider()


@pytest.mark.asyncio
async def test_web_search_adapter_registers_read_only_bounded_tool():
    provider = FakeProvider(
        [WebSearchResult("Doc", "https://docs.example.com/a", "Answer")]
    )
    registry = ToolRegistry(
        ToolRuntimeContext(agent_id="agent-1", auth_claims={"oid": "user-1"})
    )
    register_web_search_tool(
        registry,
        provider,
        allowed_domains=("example.com",),
        max_results=2,
        timeout_seconds=5,
    )

    spec = registry.specs()[0]
    assert spec.name == "search_web"
    assert spec.source == "web_search:fake"
    assert spec.risk_level == "read"
    result = json.loads(
        await registry.execute(
            "search_web",
            {"query": "supported feature", "max_results": 9},
        )
    )
    assert result["result_count"] == 1
    assert provider.calls == [("supported feature", 6)]


def test_connection_normalization_encrypts_secret_and_never_serializes_it(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    normalized = web_search_connections.normalize_web_search_connection(
        {
            "team_id": "team-1",
            "name": "Corporate Search",
            "provider": "brave",
            "api_key": "secret-value",
            "timeout_seconds": 99,
        }
    )

    assert "secret-value" not in normalized["api_key_ciphertext"]
    assert (
        web_search_connections.decrypt_web_search_api_key(
            {"api_key_ciphertext": normalized["api_key_ciphertext"]}
        )
        == "secret-value"
    )
    assert normalized["timeout_seconds"] == 30
    serialized = web_search_connections.serialize_web_search_connection(
        {"_id": "connection-1", **normalized}
    )
    assert serialized["has_api_key"] is True
    assert "api_key" not in serialized
    assert "api_key_ciphertext" not in serialized
    assert "secret-value" not in str(serialized)


def test_connection_update_preserves_stored_secret_and_searxng_requires_url():
    existing = {
        "provider": "brave",
        "name": "Existing",
        "team_id": "team-1",
        "api_key_ciphertext": "encrypted",
        "enabled": True,
    }
    normalized = web_search_connections.normalize_web_search_connection(
        {"name": "Renamed", "provider": "brave"},
        existing=existing,
    )
    assert normalized["api_key_ciphertext"] == "encrypted"
    with pytest.raises(ValueError, match="base URL"):
        web_search_connections.normalize_web_search_connection(
            {"name": "Search", "provider": "searxng"}
        )


def test_create_provider_supports_managed_connection_fields():
    assert create_web_search_provider("brave", api_key="secret").name == "brave"
    assert create_web_search_provider(
        "searxng", base_url="https://search.example.com"
    ).name == "searxng"


@pytest.mark.asyncio
async def test_web_search_connection_list_route_is_secret_free(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_require_integration_catalog_access",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        backend_app,
        "list_web_search_connections",
        lambda _team_id: [
            {
                "_id": "search-1",
                "team_id": "team-1",
                "name": "Corporate Search",
                "provider": "brave",
                "base_url": "",
                "timeout_seconds": 10,
                "enabled": True,
                "api_key_ciphertext": "must-not-leak",
            }
        ],
    )
    monkeypatch.setattr(
        backend_app, "web_search_connection_usage_count", lambda _connection_id: 2
    )

    response = await client.get("/web_search_connections?team_id=team-1")
    payload = await response.get_json()

    assert response.status_code == 200
    assert payload[0]["agent_usage_count"] == 2
    assert payload[0]["has_api_key"] is True
    assert "must-not-leak" not in str(payload)
