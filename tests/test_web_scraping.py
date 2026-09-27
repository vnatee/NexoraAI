from __future__ import annotations

import socket

import pytest
import requests

from addons.scraping_web import (
    WebScrapingError,
    normalize_public_url,
    run_scraping_job,
    source_folder,
)


def public_resolver(host: str, port: int, **_kwargs):
    address = "93.184.216.34" if host == "docs.example.com" else "127.0.0.1"
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]


class FakeResponse:
    def __init__(self, status: int, content_type: str, body: str = "", location: str | None = None):
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        if location:
            self.headers["Location"] = location
        self._body = body.encode()

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def close(self):
        return None


class FakeSession:
    def __init__(self, responses: dict[str, FakeResponse]):
        self.responses = responses
        self.requested: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str, **_kwargs):
        self.requested.append(url)
        return self.responses[url]


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost/",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "https://user:secret@docs.example.com/",
        "https://docs.example.com:8443/",
        "https://docs.example.com/?token=secret",
    ],
)
def test_normalize_public_url_rejects_unsafe_sources(url):
    with pytest.raises(WebScrapingError):
        normalize_public_url(url, resolver=public_resolver)


def test_bounded_crawl_indexes_root_and_same_path_with_evidence(monkeypatch):
    monkeypatch.setenv("WEB_SCRAPE_MIN_TEXT_CHARS", "1")
    root = "https://docs.example.com/product/"
    child = "https://docs.example.com/product/setup"
    session = FakeSession({
        "https://docs.example.com/robots.txt": FakeResponse(200, "text/plain", "User-agent: *\nAllow: /"),
        root: FakeResponse(
            200,
            "text/html; charset=utf-8",
            '<html><head><title>Product docs</title></head><body><main>Root evidence text '
            '<a href="setup?tracking=1">Setup</a><a href="/private">Outside path</a>'
            '<a href="https://other.example.net/">External</a></main></body></html>',
        ),
        child: FakeResponse(200, "text/html", "<html><body><main>Child evidence text</main></body></html>"),
    })

    result, pages = run_scraping_job(root, session=session, resolver=public_resolver, max_pages=10)

    assert result["pages_indexed"] == 2
    assert [page["source_url"] for page in pages] == [root, child]
    assert "Source URL: https://docs.example.com/product/setup" in pages[1]["text"]
    assert "Retrieved at:" in pages[1]["text"]
    assert "Content SHA-256:" in pages[1]["text"]
    assert "||https:__docs.example.com_product_setup.txt" in pages[1]["storage_name"]
    assert "https://docs.example.com/private" not in session.requested
    assert source_folder(root).startswith("source-")


def test_crawl_depth_controls_link_traversal(monkeypatch):
    monkeypatch.setenv("WEB_SCRAPE_MIN_TEXT_CHARS", "1")
    root = "https://docs.example.com/product/"
    child = "https://docs.example.com/product/setup"
    grandchild = "https://docs.example.com/product/setup/advanced"

    def session():
        return FakeSession({
            "https://docs.example.com/robots.txt": FakeResponse(200, "text/plain", "User-agent: *\nAllow: /"),
            root: FakeResponse(200, "text/html", '<main>Root <a href="setup">Setup</a></main>'),
            child: FakeResponse(200, "text/html", '<main>Setup <a href="setup/advanced">Advanced</a></main>'),
            grandchild: FakeResponse(200, "text/html", "<main>Advanced</main>"),
        })

    root_result, root_pages = run_scraping_job(
        root, session=session(), resolver=public_resolver, max_depth=0
    )
    deep_result, deep_pages = run_scraping_job(
        root, session=session(), resolver=public_resolver, max_depth=2
    )

    assert root_result["crawl_depth"] == 0
    assert [page["source_url"] for page in root_pages] == [root]
    assert deep_result["crawl_depth"] == 2
    assert [page["source_url"] for page in deep_pages] == [root, child, grandchild]


def test_total_size_limit_returns_an_explicit_partial_snapshot(monkeypatch):
    monkeypatch.setenv("WEB_SCRAPE_MIN_TEXT_CHARS", "1")
    root = "https://docs.example.com/product/"
    child = "https://docs.example.com/product/setup"
    root_body = '<main>Root <a href="setup">Setup</a></main>'
    monkeypatch.setenv("WEB_SCRAPE_MAX_TOTAL_BYTES", str(len(root_body.encode()) + 1))
    session = FakeSession({
        "https://docs.example.com/robots.txt": FakeResponse(200, "text/plain", "User-agent: *\nAllow: /"),
        root: FakeResponse(200, "text/html", root_body),
        child: FakeResponse(200, "text/html", "<main>Child evidence</main>"),
    })

    result, pages = run_scraping_job(
        root, session=session, resolver=public_resolver, max_depth=1
    )

    assert result["status"] == "partial"
    assert result["truncated"] is True
    assert result["limit_reason"] == "total_size"
    assert "partial snapshot" in result["message"]
    assert [page["source_url"] for page in pages] == [root]


def test_page_limit_returns_an_explicit_partial_snapshot(monkeypatch):
    monkeypatch.setenv("WEB_SCRAPE_MIN_TEXT_CHARS", "1")
    root = "https://docs.example.com/product/"
    session = FakeSession({
        "https://docs.example.com/robots.txt": FakeResponse(200, "text/plain", "User-agent: *\nAllow: /"),
        root: FakeResponse(200, "text/html", '<main>Root <a href="setup">Setup</a></main>'),
    })

    result, pages = run_scraping_job(
        root, session=session, resolver=public_resolver, max_pages=1, max_depth=1
    )

    assert result["status"] == "partial"
    assert result["limit_reason"] == "page_limit"
    assert [page["source_url"] for page in pages] == [root]


def test_redirect_outside_approved_host_is_blocked(monkeypatch):
    monkeypatch.setenv("WEB_SCRAPE_MIN_TEXT_CHARS", "1")
    root = "https://docs.example.com/product/"
    session = FakeSession({
        "https://docs.example.com/robots.txt": FakeResponse(200, "text/plain", "User-agent: *\nAllow: /"),
        root: FakeResponse(302, "text/html", location="http://127.0.0.1/admin"),
    })

    with pytest.raises(WebScrapingError, match="approved host or path"):
        run_scraping_job(root, session=session, resolver=public_resolver)


def test_robots_exclusion_is_respected(monkeypatch):
    monkeypatch.setenv("WEB_SCRAPE_MIN_TEXT_CHARS", "1")
    root = "https://docs.example.com/product/"
    session = FakeSession({
        "https://docs.example.com/robots.txt": FakeResponse(200, "text/plain", "User-agent: *\nDisallow: /product/"),
    })

    with pytest.raises(WebScrapingError, match="No readable"):
        run_scraping_job(root, session=session, resolver=public_resolver)
    assert root not in session.requested


def test_same_host_dns_rebinding_is_blocked(monkeypatch):
    monkeypatch.setenv("WEB_SCRAPE_MIN_TEXT_CHARS", "1")
    root = "https://docs.example.com/product/"
    redirected = "https://docs.example.com/product/admin"
    calls = 0

    def rebinding_resolver(host: str, port: int, **_kwargs):
        nonlocal calls
        calls += 1
        address = "127.0.0.1" if calls >= 4 else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    session = FakeSession({
        "https://docs.example.com/robots.txt": FakeResponse(200, "text/plain", "User-agent: *\nAllow: /"),
        root: FakeResponse(302, "text/html", location=redirected),
    })
    with pytest.raises(WebScrapingError, match="Private"):
        run_scraping_job(root, session=session, resolver=rebinding_resolver)


def test_external_links_are_not_resolved(monkeypatch):
    monkeypatch.setenv("WEB_SCRAPE_MIN_TEXT_CHARS", "1")
    root = "https://docs.example.com/product/"
    resolved_hosts: list[str] = []

    def recording_resolver(host: str, port: int, **kwargs):
        resolved_hosts.append(host)
        return public_resolver(host, port, **kwargs)

    session = FakeSession({
        "https://docs.example.com/robots.txt": FakeResponse(200, "text/plain", "User-agent: *\nAllow: /"),
        root: FakeResponse(200, "text/html", '<html><body><main>Evidence <a href="https://other.example.net/secret">Other</a></main></body></html>'),
    })
    run_scraping_job(root, session=session, resolver=recording_resolver)
    assert set(resolved_hosts) == {"docs.example.com"}
