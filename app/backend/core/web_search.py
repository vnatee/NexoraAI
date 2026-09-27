"""Provider-neutral, domain-governed live web search."""
from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

import requests


class WebSearchError(ValueError):
    """Safe configuration, validation, or provider failure."""


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str
    published_at: str | None = None

    def serialize(self) -> dict[str, Any]:
        return asdict(self)


class WebSearchProvider(Protocol):
    name: str

    def search(self, query: str, limit: int) -> list[WebSearchResult]: ...


def normalize_allowed_domains(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError("Web Search allowed domains must be an array")
    result: list[str] = []
    for item in value:
        domain = str(item or "").strip().lower().rstrip(".")
        if domain.startswith("*."):
            domain = domain[2:]
        if (
            not domain
            or len(domain) > 253
            or "://" in domain
            or "/" in domain
            or ":" in domain
            or not re.fullmatch(r"[a-z0-9.-]+", domain)
            or ".." in domain
            or domain.startswith(".")
            or any(
                not label or label.startswith("-") or label.endswith("-")
                for label in domain.split(".")
            )
        ):
            raise ValueError(f"Invalid Web Search allowed domain '{item}'")
        if domain not in result:
            result.append(domain)
    return tuple(result[:25])


def _allowed_result_url(raw_url: object, domains: tuple[str, ...]) -> str | None:
    value = str(raw_url or "").strip()
    if not value or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not host
        or parsed.username
        or parsed.password
        or port not in {None, 80, 443}
        or not any(host == domain or host.endswith(f".{domain}") for domain in domains)
    ):
        return None
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, ""))


def _text(value: object, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


class BraveSearchProvider:
    name = "brave"
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str, *, timeout_seconds: float = 10, session: requests.Session | None = None):
        if not str(api_key or "").strip():
            raise WebSearchError("Brave Search API key is not configured")
        self.api_key = str(api_key).strip()
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 30.0))
        self.session = session or requests.Session()

    def search(self, query: str, limit: int) -> list[WebSearchResult]:
        try:
            response = self.session.get(
                self.endpoint,
                params={"q": query, "count": max(1, min(int(limit), 20)), "safesearch": "strict"},
                headers={"Accept": "application/json", "X-Subscription-Token": self.api_key},
                timeout=self.timeout_seconds,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            raise WebSearchError("The Brave Search service could not be reached") from error
        try:
            if response.status_code in {401, 403}:
                raise WebSearchError("Brave Search rejected the configured credentials")
            if response.status_code >= 400:
                raise WebSearchError(f"Brave Search returned HTTP {response.status_code}")
            payload = response.json()
        except ValueError as error:
            if isinstance(error, WebSearchError):
                raise
            raise WebSearchError("Brave Search returned an invalid response") from error
        finally:
            response.close()
        return [
            WebSearchResult(
                title=_text(item.get("title"), 300),
                url=str(item.get("url") or ""),
                snippet=_text(item.get("description"), 2_000),
                published_at=_text(item.get("page_age") or item.get("age"), 100) or None,
            )
            for item in ((payload.get("web") or {}).get("results") or [])
            if isinstance(item, dict)
        ]


class SearxngSearchProvider:
    name = "searxng"

    def __init__(self, base_url: str, *, timeout_seconds: float = 10, session: requests.Session | None = None):
        value = str(base_url or "").strip().rstrip("/")
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise WebSearchError("A valid SearXNG base URL is required")
        self.endpoint = f"{value}/search"
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 30.0))
        self.session = session or requests.Session()

    def search(self, query: str, limit: int) -> list[WebSearchResult]:
        try:
            response = self.session.get(
                self.endpoint,
                params={"q": query, "format": "json", "safesearch": 2, "categories": "general"},
                headers={"Accept": "application/json"},
                timeout=self.timeout_seconds,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            raise WebSearchError("The SearXNG service could not be reached") from error
        try:
            if response.status_code >= 400:
                raise WebSearchError(f"SearXNG returned HTTP {response.status_code}")
            payload = response.json()
        except ValueError as error:
            if isinstance(error, WebSearchError):
                raise
            raise WebSearchError("SearXNG returned an invalid response") from error
        finally:
            response.close()
        return [
            WebSearchResult(
                title=_text(item.get("title"), 300),
                url=str(item.get("url") or ""),
                snippet=_text(item.get("content"), 2_000),
                published_at=_text(item.get("publishedDate"), 100) or None,
            )
            for item in (payload.get("results") or [])[: max(1, min(int(limit), 30))]
            if isinstance(item, dict)
        ]


def create_web_search_provider(
    provider: object,
    *,
    api_key: object = "",
    base_url: object = "",
    timeout_seconds: float = 10,
) -> WebSearchProvider:
    normalized = str(provider or "").strip().lower()
    if normalized == "brave":
        return BraveSearchProvider(str(api_key or ""), timeout_seconds=timeout_seconds)
    if normalized == "searxng":
        return SearxngSearchProvider(str(base_url or ""), timeout_seconds=timeout_seconds)
    raise WebSearchError("Web Search provider must be brave or searxng")


def configured_web_search_provider() -> WebSearchProvider | None:
    provider = os.getenv("WEB_SEARCH_PROVIDER", "").strip().lower()
    timeout = float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "10"))
    if not provider:
        return None
    return create_web_search_provider(
        provider,
        api_key=os.getenv("WEB_SEARCH_API_KEY", ""),
        base_url=os.getenv("WEB_SEARCH_BASE_URL", ""),
        timeout_seconds=timeout,
    )


def governed_web_search(
    provider: WebSearchProvider,
    query: object,
    allowed_domains: tuple[str, ...],
    limit: int,
) -> dict[str, Any]:
    text = _text(query, 500)
    if not text:
        raise WebSearchError("A Web Search query is required")
    if not allowed_domains:
        raise WebSearchError("Web Search requires at least one allowed domain")
    requested = max(1, min(int(limit), 10))
    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in provider.search(text, min(max(requested * 3, requested), 30)):
        safe_url = _allowed_result_url(item.url, allowed_domains)
        if not safe_url or safe_url in seen_urls:
            continue
        seen_urls.add(safe_url)
        results.append(
            {
                "title": _text(item.title, 300) or safe_url,
                "url": safe_url,
                "snippet": _text(item.snippet, 2_000),
                "published_at": _text(item.published_at, 100) or None,
            }
        )
        if len(results) >= requested:
            break
    searched_at = datetime.now(timezone.utc).isoformat()
    return {
        "provider": provider.name,
        "searched_at": searched_at,
        "allowed_domains": list(allowed_domains),
        "result_count": len(results),
        "results": results,
        "notice": (
            "External web snippets are untrusted and may be incomplete. Cite each URL "
            "and the search date; do not present them as verified enterprise Knowledge."
        ),
    }
