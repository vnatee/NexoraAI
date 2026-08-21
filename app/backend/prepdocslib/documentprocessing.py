import asyncio
import base64
import json
import logging
import mimetypes
import os
import tempfile
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import IO, Any

import aiohttp
import jwt

from mongo_table_connecters.document_processing import (
    decrypt_provider_credentials,
    get_default_profile,
    get_provider,
    normalize_docling_endpoint,
    resolve_processing_route,
)

from .page import Page
from .parser import Parser

logger = logging.getLogger("scripts")


def _path_value(value: Any, path: str, default: Any = None) -> Any:
    current = value
    for part in (item for item in path.split(".") if item):
        if isinstance(current, dict):
            current = current.get(part, default)
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return default
    return current


def _render_tables(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def _json_pointer(value: Any, reference: str) -> Any:
    current = value
    for raw_part in str(reference).removeprefix("#/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def _docling_table_markdown(item: dict[str, Any]) -> str:
    data = item.get("data") or {}
    grid = data.get("grid")
    if isinstance(grid, list) and grid:
        rows = [
            [str(cell.get("text") or "") if isinstance(cell, dict) else str(cell or "") for cell in row]
            for row in grid
            if isinstance(row, list)
        ]
    else:
        cells = data.get("table_cells") or data.get("tableCells") or []
        row_count = int(data.get("num_rows") or data.get("numRows") or 0)
        column_count = int(data.get("num_cols") or data.get("numCols") or 0)
        rows = [[""] * column_count for _ in range(row_count)]
        for cell in cells if isinstance(cells, list) else []:
            if not isinstance(cell, dict):
                continue
            row = int(cell.get("start_row_offset_idx") or cell.get("startRowOffsetIdx") or 0)
            column = int(cell.get("start_col_offset_idx") or cell.get("startColOffsetIdx") or 0)
            if 0 <= row < row_count and 0 <= column < column_count:
                rows[row][column] = str(cell.get("text") or "")
    if not rows or not any(rows):
        return str(item.get("text") or item.get("orig") or "").strip()
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    escaped = [[value.replace("|", "\\|").replace("\n", " ") for value in row] for row in rows]
    separator = ["---"] * width
    return "\n".join("| " + " | ".join(row) + " |" for row in [escaped[0], separator, *escaped[1:]])


def _docling_pages(document: Any) -> list[Page]:
    """Normalize a DoclingDocument export without coupling it to a search backend."""

    if isinstance(document, str):
        try:
            document = json.loads(document)
        except json.JSONDecodeError:
            return []
    if not isinstance(document, dict):
        return []

    page_parts: dict[int, list[str]] = {}
    page_tables: dict[int, list[str]] = {}
    visited: set[str] = set()

    def add_item(item: Any, reference: str = "") -> None:
        if reference:
            if reference in visited:
                return
            visited.add(reference)
        if not isinstance(item, dict):
            return
        provenance = item.get("prov") or item.get("provenance") or []
        first_provenance = provenance[0] if isinstance(provenance, list) and provenance else {}
        page_number = int(
            (first_provenance or {}).get("page_no")
            or (first_provenance or {}).get("pageNo")
            or item.get("page_no")
            or item.get("pageNo")
            or 1
        )
        page_num = max(0, page_number - 1)
        label = str(item.get("label") or "").lower()
        if label == "table" or reference.startswith("#/tables/"):
            rendered = _docling_table_markdown(item)
            if rendered:
                page_parts.setdefault(page_num, []).append(rendered)
                page_tables.setdefault(page_num, []).append(rendered)
            return
        rendered = str(item.get("text") or item.get("orig") or "").strip()
        if rendered:
            page_parts.setdefault(page_num, []).append(rendered)
            return
        for child in item.get("children") or []:
            child_reference = str(child.get("$ref") or "") if isinstance(child, dict) else ""
            add_item(_json_pointer(document, child_reference) if child_reference else child, child_reference)

    body = document.get("body") or {}
    for child in body.get("children") or []:
        reference = str(child.get("$ref") or "") if isinstance(child, dict) else ""
        add_item(_json_pointer(document, reference) if reference else child, reference)

    if not page_parts:
        for collection_name in ("texts", "tables", "key_value_items", "form_items", "pictures"):
            values = document.get(collection_name) or []
            for index, item in enumerate(values if isinstance(values, list) else []):
                add_item(item, f"#/{collection_name}/{index}")

    pages: list[Page] = []
    offset = 0
    for page_num in sorted(page_parts):
        text = "\n\n".join(part for part in page_parts[page_num] if part).strip()
        if not text:
            continue
        text += "\n"
        pages.append(
            Page(
                page_num=page_num,
                offset=offset,
                text=text,
                metadata={"provider": "Docling", "tables": page_tables.get(page_num, [])},
            )
        )
        offset += len(text)
    return pages


def _mime_type(content: IO) -> str:
    name = str(getattr(content, "name", "document.pdf"))
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def _auth_headers(provider: dict[str, Any]) -> dict[str, str]:
    config = provider.get("config") or {}
    auth_type = config.get("auth_type", "none")
    secret = decrypt_provider_credentials(provider)
    if auth_type == "bearer" and secret:
        return {"Authorization": f"Bearer {secret}"}
    if auth_type == "api_key" and secret:
        return {str(config.get("api_key_header") or "X-API-Key"): secret}
    return {}


class GenericOCRAPIParser(Parser):
    """Adapter for an administrator-defined OCR REST API response mapping."""

    def __init__(self, provider: dict[str, Any]):
        self.provider = provider
        self.config = provider.get("config") or {}

    async def parse(self, content: IO) -> AsyncGenerator[Page, None]:
        endpoint = str(self.config["endpoint"]).rstrip("/")
        process_path = str(self.config.get("process_path") or "/v1/ocr")
        filename = Path(getattr(content, "name", "document.pdf")).name
        content.seek(0)
        raw = content.read()
        content.seek(0)
        headers = _auth_headers(self.provider)
        request_mode = self.config.get("request_mode", "multipart")
        request_kwargs: dict[str, Any]
        if request_mode == "base64_json":
            field = str(self.config.get("file_field") or "file")
            request_kwargs = {
                "json": {
                    field: base64.b64encode(raw).decode("ascii"),
                    "filename": filename,
                    "mime_type": _mime_type(content),
                }
            }
        else:
            form = aiohttp.FormData()
            form.add_field(
                str(self.config.get("file_field") or "file"),
                raw,
                filename=filename,
                content_type=_mime_type(content),
            )
            request_kwargs = {"data": form}
        timeout = aiohttp.ClientTimeout(total=float(self.config.get("timeout_seconds") or 300))
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.post(f"{endpoint}{process_path}", **request_kwargs) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise ValueError(f"OCR API returned HTTP {response.status}: {payload}")
        mapping = self.config.get("response_mapping") or {}
        pages = _path_value(payload, str(mapping.get("pages_path") or "pages"))
        if not isinstance(pages, list):
            pages = [payload]
        offset = 0
        for index, item in enumerate(pages):
            text = str(_path_value(item, str(mapping.get("text_path") or "text"), "") or "")
            tables = _path_value(item, str(mapping.get("tables_path") or "tables"), [])
            table_text = _render_tables(tables)
            if table_text:
                text = f"{text}\n\n{table_text}".strip()
            if not text:
                continue
            page_number = _path_value(item, str(mapping.get("page_number_path") or "page_number"), index + 1)
            confidence = _path_value(item, str(mapping.get("confidence_path") or "confidence"))
            yield Page(
                page_num=max(0, int(page_number or index + 1) - 1),
                offset=offset,
                text=text,
                metadata={"provider": self.provider.get("name"), "confidence": confidence, "tables": tables},
            )
            offset += len(text)
        if offset == 0:
            raise ValueError("OCR API response did not contain text using the configured response mapping")


class PaddleOCRAPIParser(Parser):
    """Adapter for PaddleOCR/PaddleX basic self-hosted serving."""

    def __init__(self, provider: dict[str, Any]):
        self.provider = provider
        self.config = provider.get("config") or {}

    async def parse(self, content: IO) -> AsyncGenerator[Page, None]:
        content.seek(0)
        raw = content.read()
        content.seek(0)
        payload = {
            "file": base64.b64encode(raw).decode("ascii"),
            "fileType": 0 if Path(getattr(content, "name", "document.pdf")).suffix.lower() == ".pdf" else 1,
            "visualize": False,
        }
        endpoint = str(self.config["endpoint"]).rstrip("/")
        process_path = str(self.config.get("process_path") or "/ocr")
        timeout = aiohttp.ClientTimeout(total=float(self.config.get("timeout_seconds") or 300))
        async with aiohttp.ClientSession(timeout=timeout, headers=_auth_headers(self.provider)) as session:
            async with session.post(f"{endpoint}{process_path}", json=payload) as response:
                result = await response.json(content_type=None)
                if response.status >= 400:
                    raise ValueError(f"PaddleOCR returned HTTP {response.status}: {result}")
        result_body = result.get("result") or {}
        items = result_body.get("layoutParsingResults") or result_body.get("ocrResults") or []
        offset = 0
        for index, item in enumerate(items):
            markdown = _path_value(item, "markdown.text", "")
            pruned = item.get("prunedResult") or {}
            texts = pruned.get("rec_texts") or pruned.get("recTexts") or []
            text = str(markdown or "\n".join(str(value) for value in texts if value is not None)).strip()
            if not text and isinstance(pruned, str):
                text = pruned.strip()
            if not text:
                continue
            scores = pruned.get("rec_scores") or pruned.get("recScores") or [] if isinstance(pruned, dict) else []
            confidence = sum(float(value) for value in scores) / len(scores) if scores else None
            yield Page(
                page_num=index,
                offset=offset,
                text=text,
                metadata={"provider": self.provider.get("name"), "confidence": confidence},
            )
            offset += len(text)
        if offset == 0:
            raise ValueError("PaddleOCR response contained no recognized text")


class GoogleDocumentAIParser(Parser):
    """Google Document AI REST adapter using encrypted service-account credentials."""

    def __init__(self, provider: dict[str, Any]):
        self.provider = provider
        self.config = provider.get("config") or {}

    async def _access_token(self, session: aiohttp.ClientSession) -> str:
        try:
            credentials = json.loads(decrypt_provider_credentials(self.provider))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Stored Google Service Account JSON is invalid") from exc
        now = int(time.time())
        token_uri = str(credentials.get("token_uri") or "https://oauth2.googleapis.com/token")
        assertion = jwt.encode(
            {
                "iss": credentials.get("client_email"),
                "scope": "https://www.googleapis.com/auth/cloud-platform",
                "aud": token_uri,
                "iat": now,
                "exp": now + 3600,
            },
            credentials.get("private_key"),
            algorithm="RS256",
        )
        async with session.post(
            token_uri,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
        ) as response:
            payload = await response.json(content_type=None)
            if response.status >= 400 or not payload.get("access_token"):
                raise ValueError(f"Google authentication failed: {payload}")
            return str(payload["access_token"])

    def _processor_name(self) -> str:
        base = (
            f"projects/{self.config['project_id']}/locations/{self.config['location']}"
            f"/processors/{self.config['processor_id']}"
        )
        version = self.config.get("processor_version")
        return f"{base}/processorVersions/{version}" if version else base

    def _api_endpoint(self) -> str:
        configured = str(self.config.get("api_endpoint") or "").rstrip("/")
        if configured:
            return configured
        location = str(self.config.get("location") or "us")
        host = "documentai.googleapis.com" if location == "global" else f"{location}-documentai.googleapis.com"
        return f"https://{host}"

    @staticmethod
    def _anchor_text(document_text: str, layout: dict[str, Any]) -> str:
        segments = (layout.get("textAnchor") or {}).get("textSegments") or []
        return "".join(
            document_text[int(segment.get("startIndex") or 0) : int(segment.get("endIndex") or 0)]
            for segment in segments
        )

    def _table_markdown(self, document_text: str, table: dict[str, Any]) -> str:
        rows = (table.get("headerRows") or []) + (table.get("bodyRows") or [])
        matrix = [
            [self._anchor_text(document_text, cell.get("layout") or {}).strip().replace("|", "\\|") for cell in row.get("cells") or []]
            for row in rows
        ]
        if not matrix:
            return ""
        width = max(len(row) for row in matrix)
        matrix = [row + [""] * (width - len(row)) for row in matrix]
        separator = ["---"] * width
        return "\n".join("| " + " | ".join(row) + " |" for row in [matrix[0], separator, *matrix[1:]])

    async def parse(self, content: IO) -> AsyncGenerator[Page, None]:
        content.seek(0)
        raw = content.read()
        content.seek(0)
        timeout = aiohttp.ClientTimeout(total=float(self.config.get("timeout_seconds") or 300))
        async with aiohttp.ClientSession(timeout=timeout) as session:
            token = await self._access_token(session)
            request_body = {
                "rawDocument": {
                    "content": base64.b64encode(raw).decode("ascii"),
                    "mimeType": _mime_type(content),
                }
            }
            url = f"{self._api_endpoint()}/v1/{self._processor_name()}:process"
            async with session.post(url, json=request_body, headers={"Authorization": f"Bearer {token}"}) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise ValueError(f"Google Document AI returned HTTP {response.status}: {payload}")
        document = payload.get("document") or {}
        document_text = str(document.get("text") or "")
        pages = document.get("pages") or []
        offset = 0
        for index, page in enumerate(pages):
            text = self._anchor_text(document_text, page.get("layout") or {}).strip()
            tables = [self._table_markdown(document_text, table) for table in page.get("tables") or []]
            table_text = "\n\n".join(value for value in tables if value)
            if table_text and table_text not in text:
                text = f"{text}\n\n{table_text}".strip()
            if not text:
                continue
            confidence = (page.get("layout") or {}).get("confidence")
            yield Page(
                page_num=index,
                offset=offset,
                text=text,
                metadata={"provider": self.provider.get("name"), "confidence": confidence, "tables": tables},
            )
            offset += len(text)
        if offset == 0 and document_text.strip():
            yield Page(page_num=0, offset=0, text=document_text, metadata={"provider": self.provider.get("name")})
        elif offset == 0:
            raise ValueError("Google Document AI returned no document text")


async def check_document_provider(provider: dict[str, Any]) -> str:
    """Run a non-document health/authentication check for a managed provider."""

    provider_type = provider.get("provider_type")
    config = provider.get("config") or {}
    if provider_type == "docling":
        if config.get("execution_mode", "service") == "embedded":
            try:
                import docling  # noqa: F401
            except ImportError as exc:
                raise ValueError("Docling is not installed in this backend container") from exc
            return "Embedded Docling is installed"
        endpoint = normalize_docling_endpoint(config.get("endpoint") or "http://docling:5001")
        health_url = f"{endpoint}/health"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(health_url) as response:
                if response.status >= 400:
                    raise ValueError(f"Docling health check returned HTTP {response.status} from {health_url}")
        return "Docling Serve is available"
    if provider_type in {"generic_ocr_api", "paddleocr"}:
        endpoint = str(config.get("endpoint") or "").rstrip("/")
        health_path = str(config.get("health_path") or "/docs")
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10), headers=_auth_headers(provider)
        ) as session:
            async with session.get(f"{endpoint}{health_path}") as response:
                if response.status >= 400:
                    raise ValueError(f"OCR API health check returned HTTP {response.status}")
        return "OCR API is available"
    if provider_type == "google_document_ai":
        parser = GoogleDocumentAIParser(provider)
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            token = await parser._access_token(session)
            url = f"{parser._api_endpoint()}/v1/{parser._processor_name()}"
            async with session.get(url, headers={"Authorization": f"Bearer {token}"}) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise ValueError(f"Google processor check returned HTTP {response.status}: {payload}")
        return "Google Document AI processor is available"
    return "Provider configuration is available"


class DoclingParser(Parser):
    """Optional local document parser. The heavy dependency is loaded only when selected."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def parse(self, content: IO) -> AsyncGenerator[Page, None]:
        if self.config.get("execution_mode", "service") == "service":
            pages = await self._convert_service(content)
        else:
            pages = await asyncio.to_thread(self._convert, content)
        for page in pages:
            yield page

    async def _convert_service(self, content: IO) -> list[Page]:
        endpoint = normalize_docling_endpoint(self.config.get("endpoint") or "http://docling:5001")
        content.seek(0)
        raw = content.read()
        filename = Path(getattr(content, "name", "document.pdf")).name

        def request_form(output_format: str) -> aiohttp.FormData:
            form = aiohttp.FormData()
            form.add_field("files", raw, filename=filename)
            form.add_field("to_formats", output_format)
            form.add_field("do_ocr", "true")
            form.add_field("do_table_structure", "true" if self.config.get("extract_tables", True) else "false")
            form.add_field("table_mode", "accurate" if self.config.get("extract_tables", True) else "fast")
            for language in self.config.get("languages") or []:
                if str(language).strip():
                    form.add_field("ocr_lang", str(language).strip())
            return form

        async def convert(session: aiohttp.ClientSession, output_format: str) -> tuple[int, Any]:
            async with session.post(
                f"{endpoint}/v1/convert/file", data=request_form(output_format)
            ) as response:
                return response.status, await response.json(content_type=None)

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
                status, payload = await convert(session, "json")
                if status >= 400:
                    logger.warning(
                        "Docling Serve JSON conversion returned HTTP %s; retrying Markdown compatibility mode",
                        status,
                    )
                    json_error = payload
                    status, payload = await convert(session, "md")
                    if status >= 400:
                        raise ValueError(
                            f"Docling Serve returned HTTP {status}: {payload}; JSON request also failed: {json_error}"
                        )
                elif isinstance(payload, dict):
                    converted_document = payload.get("document") or {}
                    pages = _docling_pages(converted_document.get("json_content"))
                    if pages:
                        return pages
                    markdown = str(converted_document.get("md_content") or "")
                    if markdown.strip():
                        return [Page(page_num=0, offset=0, text=markdown, metadata={"provider": "Docling"})]
                    logger.warning(
                        "Docling Serve JSON response contained no recognized pages; retrying Markdown compatibility mode"
                    )
                    status, payload = await convert(session, "md")
                    if status >= 400:
                        raise ValueError(f"Docling Serve Markdown fallback returned HTTP {status}: {payload}")
                else:
                    logger.warning(
                        "Docling Serve JSON response was not an object; retrying Markdown compatibility mode"
                    )
                    status, payload = await convert(session, "md")
                    if status >= 400:
                        raise ValueError(f"Docling Serve Markdown fallback returned HTTP {status}: {payload}")
        finally:
            content.seek(0)
        if not isinstance(payload, dict):
            raise ValueError("Docling Serve returned an invalid response")
        converted_document = payload.get("document") or {}
        pages = _docling_pages(converted_document.get("json_content"))
        if pages:
            return pages
        markdown = str(converted_document.get("md_content") or "")
        if not markdown.strip():
            raise ValueError(f"Docling Serve returned no Markdown content: {payload.get('errors') or payload.get('status')}")
        return [Page(page_num=0, offset=0, text=markdown, metadata={"provider": "Docling"})]

    @staticmethod
    def _convert(content: IO) -> list[Page]:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise ValueError("Docling is not installed. Install backend dependencies or run the Docling container image.") from exc
        suffix = Path(getattr(content, "name", "document.pdf")).suffix or ".pdf"
        content.seek(0)
        temporary_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
                temporary.write(content.read())
                temporary_path = temporary.name
            result = DocumentConverter().convert(temporary_path)
            if hasattr(result.document, "export_to_dict"):
                pages = _docling_pages(result.document.export_to_dict())
                if pages:
                    return pages
            exported_pages: list[Page] = []
            offset = 0
            for page_number in sorted(int(value) for value in (getattr(result.document, "pages", {}) or {})):
                markdown = result.document.export_to_markdown(page_no=page_number)
                if not markdown.strip():
                    continue
                exported_pages.append(
                    Page(
                        page_num=max(0, page_number - 1),
                        offset=offset,
                        text=markdown,
                        metadata={"provider": "Docling"},
                    )
                )
                offset += len(markdown)
            if exported_pages:
                return exported_pages
            markdown = result.document.export_to_markdown()
            if not markdown.strip():
                raise ValueError("Docling returned no searchable content")
            return [Page(page_num=0, offset=0, text=markdown, metadata={"provider": "Docling"})]
        finally:
            content.seek(0)
            if temporary_path:
                os.unlink(temporary_path)


class ManagedDocumentParser(Parser):
    """Selects a managed profile per file type, preserving the existing parser as fallback."""

    def __init__(self, fallback_parsers: dict[str, Parser | None]):
        self.fallback_parsers = fallback_parsers

    def _profile_parser(self, profile: dict[str, Any], provider: dict[str, Any], extension: str) -> Parser:
        provider_type = provider.get("provider_type")
        if provider_type == "docling":
            config = {**(provider.get("config") or {})}
            config["extract_tables"] = profile.get("extract_tables", True)
            config["languages"] = profile.get("languages") or []
            return DoclingParser(config)
        if provider_type == "generic_ocr_api":
            return GenericOCRAPIParser(provider)
        if provider_type == "paddleocr":
            return PaddleOCRAPIParser(provider)
        if provider_type == "google_document_ai":
            return GoogleDocumentAIParser(provider)
        if provider_type == "local_text":
            if extension != ".pdf":
                raise ValueError("Local text extraction currently supports PDF files only")
            parser = self.fallback_parsers.get("local_text")
            if parser:
                return parser
        if provider_type == "azure_document_intelligence":
            parser = self.fallback_parsers.get("azure_document_intelligence")
            if parser:
                return parser
        raise ValueError(f"No parser is available for provider type {provider_type}")

    def select_parser(self, content: IO, routing_context: dict[str, Any] | None = None) -> Parser:
        extension = Path(getattr(content, "name", "")).suffix.lower()
        if routing_context is not None:
            route = resolve_processing_route(
                file_extension=extension,
                scope=str(routing_context.get("scope") or "personal"),
                team_id=str(routing_context.get("team_id") or ""),
                explicit_profile_id=str(
                    routing_context.get("resolved_profile_id")
                    or routing_context.get("explicit_profile_id")
                    or ""
                ),
            )
            if route.get("status") == "error":
                raise ValueError(str(route.get("reason") or "Document processing route failed"))
            profile = route.get("profile")
            provider = route.get("provider")
            if profile and provider:
                return self._profile_parser(profile, provider, extension)
        else:
            try:
                profile = get_default_profile(extension)
                provider = get_provider(str(profile.get("provider_id"))) if profile else None
                if profile and provider and provider.get("enabled") is not False:
                    return self._profile_parser(profile, provider, extension)
            except Exception as exc:
                logger.warning("Unable to resolve managed document profile; using startup fallback: %s", exc)
        parser = (
            self.fallback_parsers.get(extension)
            if extension in self.fallback_parsers
            else self.fallback_parsers.get("default")
        )
        if parser is None:
            raise ValueError(f"No document processor is available for {extension or 'this file type'}")
        return parser

    async def parse(
        self, content: IO, routing_context: dict[str, Any] | None = None
    ) -> AsyncGenerator[Page, None]:
        parser = self.select_parser(content, routing_context=routing_context)
        async for page in parser.parse(content):
            yield page
