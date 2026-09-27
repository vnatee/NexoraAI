"""Bounded crawler for administrator-approved public Knowledge sources."""
from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
import posixpath
import re
import socket
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib import robotparser
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

LOGGER = logging.getLogger(__name__)
USER_AGENT = "NexoraAI-KnowledgeBot/1.0"
REDIRECT_CODES = {301, 302, 303, 307, 308}


class WebScrapingError(ValueError):
    """Safe user-facing validation or retrieval failure."""


@dataclass(frozen=True)
class ScrapedPage:
    source_url: str
    title: str
    text: str
    content_hash: str
    retrieved_at: str
    storage_name: str

    def upload(self) -> dict[str, str]:
        evidence_text = "\n".join([
            f"Source title: {self.title}",
            f"Source URL: {self.source_url}",
            f"Retrieved at: {self.retrieved_at}",
            f"Content SHA-256: {self.content_hash}",
            "",
            self.text,
        ])
        return {
            "source_url": self.source_url,
            "title": self.title,
            "text": evidence_text,
            "content_hash": self.content_hash,
            "retrieved_at": self.retrieved_at,
            "storage_name": self.storage_name,
        }


def _limit(name: str, default: int, maximum: int) -> int:
    try:
        return max(1, min(int(os.getenv(name, str(default))), maximum))
    except ValueError:
        return default


def _resolve_public(hostname: str, port: int, resolver: Callable[..., Iterable[tuple]]) -> None:
    try:
        records = list(resolver(hostname, port, type=socket.SOCK_STREAM))
    except OSError as error:
        raise WebScrapingError("The website hostname could not be resolved") from error
    addresses = {str(record[4][0]).split("%", 1)[0] for record in records if record[4]}
    if not addresses:
        raise WebScrapingError("The website hostname did not resolve to an address")
    for address in addresses:
        value = ipaddress.ip_address(address)
        if isinstance(value, ipaddress.IPv6Address) and value.ipv4_mapped:
            value = value.ipv4_mapped
        if not value.is_global:
            raise WebScrapingError("Private, loopback, link-local, and reserved network addresses are not allowed")


def _canonicalize(raw_url: str, *, allow_query: bool, resolve: bool, resolver: Callable[..., Iterable[tuple]]) -> str:
    value = str(raw_url or "").strip()
    if not value or len(value) > 2048:
        raise WebScrapingError("A website URL between 1 and 2048 characters is required")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise WebScrapingError("The website URL is invalid") from error
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").rstrip(".").lower()
    if scheme not in {"http", "https"} or not hostname:
        raise WebScrapingError("Only absolute http:// or https:// website URLs are allowed")
    if parsed.username or parsed.password:
        raise WebScrapingError("Website URLs must not contain credentials")
    if parsed.query and not allow_query:
        raise WebScrapingError("The approved root URL must not contain a query string")
    expected_port = 443 if scheme == "https" else 80
    if port not in {None, expected_port}:
        raise WebScrapingError("Only the standard HTTP and HTTPS ports are allowed")
    if resolve:
        _resolve_public(hostname, expected_port, resolver)
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    normalized = posixpath.normpath(path)
    if path.endswith("/") and not normalized.endswith("/"):
        normalized += "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return urlunsplit((scheme, hostname, normalized, parsed.query if allow_query else "", ""))


def normalize_public_url(raw_url: str, *, resolver: Callable[..., Iterable[tuple]] = socket.getaddrinfo, allow_query: bool = False) -> str:
    return _canonicalize(raw_url, allow_query=allow_query, resolve=True, resolver=resolver)


def normalize_stored_source_url(raw_url: str) -> str:
    return _canonicalize(raw_url, allow_query=False, resolve=False, resolver=socket.getaddrinfo)


def source_identifier(source_url: str) -> str:
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:20]


def source_folder(source_url: str) -> str:
    return f"source-{source_identifier(source_url)}||url={quote(source_url, safe='')}"


def _path_prefix(source_url: str) -> str:
    path = urlsplit(source_url).path or "/"
    if path == "/" or path.endswith("/"):
        return path
    return f"{path}/" if "." not in posixpath.basename(path) else f"{posixpath.dirname(path).rstrip('/')}/"


def _in_scope(url: str, source_url: str, path_prefix: str) -> bool:
    parsed, source = urlsplit(url), urlsplit(source_url)
    return (
        parsed.hostname == source.hostname
        and parsed.scheme in {source.scheme, "https"}
        and (url == source_url or (parsed.path or "/").startswith(path_prefix))
    )


def _read_body(response: requests.Response, maximum_bytes: int) -> bytes:
    declared = response.headers.get("Content-Length")
    if declared:
        try:
            if int(declared) > maximum_bytes:
                raise WebScrapingError("A website page exceeded the configured size limit")
        except ValueError:
            pass
    chunks, total = [], 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > maximum_bytes:
            raise WebScrapingError("A website page exceeded the configured size limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _fetch(session: requests.Session, url: str, *, resolver: Callable[..., Iterable[tuple]], timeout: float,
           maximum_bytes: int, allowed_types: set[str], source_url: str, path_prefix: str) -> tuple[str, bytes]:
    current = url
    for _ in range(4):
        current = _canonicalize(current, allow_query=False, resolve=False, resolver=resolver)
        if not _in_scope(current, source_url, path_prefix):
            raise WebScrapingError("A website redirect left the approved host or path")
        current = normalize_public_url(current, resolver=resolver)
        try:
            response = session.get(current, timeout=timeout, stream=True, allow_redirects=False)
        except requests.RequestException as error:
            raise WebScrapingError("The website could not be reached") from error
        try:
            if response.status_code in REDIRECT_CODES:
                location = response.headers.get("Location")
                if not location:
                    raise WebScrapingError("The website returned an invalid redirect")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            kind = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if kind not in allowed_types:
                raise WebScrapingError(f"Unsupported website content type: {kind or 'unknown'}")
            return current, _read_body(response, maximum_bytes)
        except requests.RequestException as error:
            raise WebScrapingError(f"The website returned HTTP {response.status_code}") from error
        finally:
            response.close()
    raise WebScrapingError("The website exceeded the redirect limit")


def _robots(session: requests.Session, source_url: str, *, resolver: Callable[..., Iterable[tuple]],
            timeout: float, maximum_bytes: int) -> robotparser.RobotFileParser:
    parsed = urlsplit(source_url)
    robots_url = urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
    policy = robotparser.RobotFileParser(robots_url)
    try:
        _, body = _fetch(
            session, robots_url, resolver=resolver, timeout=timeout,
            maximum_bytes=min(maximum_bytes, 512 * 1024),
            allowed_types={"text/plain", "text/html", "application/octet-stream"},
            source_url=urlunsplit((parsed.scheme, parsed.netloc, "/", "", "")), path_prefix="/",
        )
        policy.parse(body.decode("utf-8", errors="replace").splitlines())
    except WebScrapingError:
        policy.parse([])
    return policy


def _extract(body: bytes, url: str, retrieved_at: str) -> tuple[ScrapedPage, list[str]]:
    soup = BeautifulSoup(body, "html.parser")
    links = [str(link.get("href") or "") for link in soup.find_all("a", href=True)]
    for element in soup(["script", "style", "noscript", "svg", "form", "nav", "footer"]):
        element.decompose()
    title = " ".join((soup.title.get_text(" ", strip=True) if soup.title else "").split())[:300]
    content_root = soup.find("main") or soup.find("article") or soup.body or soup
    text = " ".join(content_root.get_text(" ", strip=True).split())
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    page_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    page = ScrapedPage(
        source_url=url,
        title=title or urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1] or urlsplit(url).hostname or "Website",
        text=text,
        content_hash=digest,
        retrieved_at=retrieved_at,
        storage_name=f"page-{page_id}||{url.replace('_', '%5F').replace('/', '_')}.txt",
    )
    return page, links


def run_scraping_job(start_url: str, *, session: requests.Session | None = None,
                     resolver: Callable[..., Iterable[tuple]] = socket.getaddrinfo,
                     max_pages: int | None = None, max_total_bytes: int | None = None,
                     max_depth: int = 1) -> tuple[dict[str, object], list[dict[str, str]]]:
    """Crawl the approved host/path and return upload-ready evidence documents."""
    source_url = normalize_public_url(start_url, resolver=resolver)
    folder = source_folder(source_url)
    if len(folder.encode("utf-8")) > 480:
        raise WebScrapingError("The approved root URL is too long to store safely")
    page_limit = max(1, min(int(max_pages or _limit("WEB_SCRAPE_MAX_PAGES", 50, 250)), 250))
    byte_limit = _limit("WEB_SCRAPE_MAX_PAGE_BYTES", 2 * 1024 * 1024, 10 * 1024 * 1024)
    total_limit = max(
        1,
        min(
            int(max_total_bytes or _limit("WEB_SCRAPE_MAX_TOTAL_BYTES", 20 * 1024 * 1024, 100 * 1024 * 1024)),
            100 * 1024 * 1024,
        ),
    )
    timeout = float(_limit("WEB_SCRAPE_TIMEOUT_SECONDS", 15, 60))
    minimum_chars = _limit("WEB_SCRAPE_MIN_TEXT_CHARS", 80, 10_000)
    depth_limit = max(0, min(int(max_depth), 2))
    prefix = _path_prefix(source_url)
    client = session or requests.Session()
    client.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    robots = _robots(client, source_url, resolver=resolver, timeout=timeout, maximum_bytes=byte_limit)
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    pending = deque([(source_url, 0)])
    queued, visited = {source_url}, set()
    pages, skipped, total_bytes = [], 0, 0
    issues: list[dict[str, str]] = []
    total_size_reached = False

    while pending and len(visited) < page_limit:
        candidate, depth = pending.popleft()
        if not robots.can_fetch(USER_AGENT, candidate):
            skipped += 1
            if len(issues) < 50:
                issues.append({"url": candidate, "reason": "Blocked by robots.txt"})
            continue
        visited.add(candidate)
        try:
            final_url, body = _fetch(
                client, candidate, resolver=resolver, timeout=timeout, maximum_bytes=byte_limit,
                allowed_types={"text/html", "application/xhtml+xml"}, source_url=source_url, path_prefix=prefix,
            )
        except WebScrapingError as error:
            if depth == 0:
                raise
            LOGGER.info("Approved web source page skipped: %s", error)
            skipped += 1
            if len(issues) < 50:
                issues.append({"url": candidate, "reason": str(error)})
            continue
        if total_bytes + len(body) > total_limit:
            total_size_reached = True
            skipped += 1
            if len(issues) < 50:
                issues.append({"url": final_url, "reason": "Total size limit reached"})
            break
        total_bytes += len(body)
        page, links = _extract(body, final_url, retrieved_at)
        storage_key_size = len(f"{folder}/{page.storage_name}".encode())
        if len(page.text) >= minimum_chars and storage_key_size <= 900:
            pages.append(page)
        else:
            skipped += 1
            if len(issues) < 50:
                reason = "Extracted text was too short" if len(page.text) < minimum_chars else "Storage key was too long"
                issues.append({"url": final_url, "reason": reason})
        if depth >= depth_limit:
            continue
        for href in links:
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            try:
                candidate_url = _canonicalize(
                    urljoin(final_url, href), allow_query=True, resolve=False, resolver=resolver
                )
                parsed = urlsplit(candidate_url)
                candidate_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
                if not _in_scope(candidate_url, source_url, prefix):
                    skipped += 1
                    continue
                normalized = normalize_public_url(candidate_url, resolver=resolver)
            except WebScrapingError:
                skipped += 1
                continue
            if normalized not in queued:
                queued.add(normalized)
                pending.append((normalized, depth + 1))

    if not pages:
        if total_size_reached:
            raise WebScrapingError(
                "The approved root page exceeded the configured total size limit"
            )
        raise WebScrapingError("No readable website content was found within the approved scope")
    page_limit_reached = bool(pending and len(visited) >= page_limit)
    limit_reason = (
        "total_size" if total_size_reached else "page_limit" if page_limit_reached else None
    )
    message = f"Approved web source refreshed. Indexed {len(pages)} page(s); skipped {skipped}."
    if limit_reason == "total_size":
        message += " Crawl stopped at the total size limit; this is a partial snapshot."
    elif limit_reason == "page_limit":
        message += " Crawl stopped at the page limit; this is a partial snapshot."
    return ({
        "status": "partial" if limit_reason else "success",
        "message": message,
        "source_url": source_url,
        "source_id": source_identifier(source_url),
        "retrieved_at": retrieved_at,
        "pages_indexed": len(pages),
        "pages_skipped": skipped,
        "crawl_depth": depth_limit,
        "truncated": bool(limit_reason),
        "limit_reason": limit_reason,
        "bytes_indexed": total_bytes,
        "issues": issues,
    }, [page.upload() for page in pages])
