from io import BytesIO

import pytest
from cryptography.fernet import Fernet

from mongo_table_connecters import document_processing as storage
from prepdocslib import documentprocessing
from prepdocslib.page import Page
from prepdocslib.parser import Parser


class NamedBytesIO(BytesIO):
    name = "sample.pdf"


class StubParser(Parser):
    def __init__(self, name: str):
        self.name = name

    async def parse(self, content):
        yield Page(0, 0, self.name)


def test_provider_and_profile_validation(monkeypatch):
    provider = storage.normalize_provider({"name": "Local Docling", "provider_type": "docling", "config": {"endpoint": "http://docling:5001"}})
    assert provider["provider_type"] == "docling"
    monkeypatch.setattr(storage, "get_provider", lambda provider_id: {"_id": provider_id})
    profile = storage.normalize_profile({"name": "Scanned documents", "provider_id": "docling-1", "file_types": [".pdf", ".png"], "languages": ["th", "en"], "is_default": True})
    assert profile["file_types"] == [".pdf", ".png"]
    assert profile["is_default"] is True


def test_router_preserves_existing_fallback(monkeypatch):
    azure = StubParser("azure")
    router = documentprocessing.ManagedDocumentParser({".pdf": azure, "default": azure, "azure_document_intelligence": azure, "local_text": StubParser("local")})
    monkeypatch.setattr(documentprocessing, "get_default_profile", lambda extension: None)
    assert router.select_parser(NamedBytesIO(b"pdf")) is azure


def test_router_selects_docling_profile(monkeypatch):
    router = documentprocessing.ManagedDocumentParser({".pdf": StubParser("azure"), "default": None, "local_text": StubParser("local")})
    monkeypatch.setattr(documentprocessing, "get_default_profile", lambda extension: {"provider_id": "docling-1", "languages": ["th", "en"], "extract_tables": False})
    monkeypatch.setattr(documentprocessing, "get_provider", lambda provider_id: {"provider_type": "docling", "enabled": True, "config": {"execution_mode": "service", "endpoint": "http://docling:5001"}})
    parser = router.select_parser(NamedBytesIO(b"pdf"))
    assert isinstance(parser, documentprocessing.DoclingParser)
    assert parser.config["languages"] == ["th", "en"]
    assert parser.config["extract_tables"] is False


def test_docling_provider_requires_valid_service_endpoint():
    with pytest.raises(ValueError, match="HTTP"):
        storage.normalize_provider({"name": "Docling", "provider_type": "docling", "config": {"execution_mode": "service", "endpoint": "docling:5001"}})


@pytest.mark.parametrize("suffix", ["", "/", "/health", "/ready", "/docs", "/ui"])
def test_docling_endpoint_is_normalized_to_service_base(suffix):
    assert storage.normalize_docling_endpoint(f"http://docling:5001{suffix}") == "http://docling:5001"


def test_google_provider_encrypts_credentials(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    credentials = {"client_email": "ocr@example.iam.gserviceaccount.com", "private_key": "secret"}
    provider = storage.normalize_provider(
        {
            "name": "Google OCR",
            "provider_type": "google_document_ai",
            "config": {"project_id": "demo", "location": "us", "processor_id": "processor-1"},
            "credentials": credentials,
        }
    )
    assert provider["credentials_ciphertext"] != str(credentials)
    assert "credentials_ciphertext" not in storage.serialize_provider(provider)
    assert storage.serialize_provider(provider)["has_credentials"] is True
    assert "ocr@example" in storage.decrypt_provider_credentials(provider)


def test_generic_ocr_provider_normalizes_mapping():
    provider = storage.normalize_provider(
        {
            "name": "Internal OCR",
            "provider_type": "generic_ocr_api",
            "config": {
                "endpoint": "http://ocr-api:8000/",
                "request_mode": "base64_json",
                "response_mapping": {"pages_path": "result.pages", "text_path": "content"},
            },
        }
    )
    assert provider["config"]["endpoint"] == "http://ocr-api:8000"
    assert provider["config"]["response_mapping"]["pages_path"] == "result.pages"
    assert provider["config"]["response_mapping"]["text_path"] == "content"


@pytest.mark.parametrize(
    ("provider_type", "parser_type"),
    [
        ("generic_ocr_api", documentprocessing.GenericOCRAPIParser),
        ("paddleocr", documentprocessing.PaddleOCRAPIParser),
        ("google_document_ai", documentprocessing.GoogleDocumentAIParser),
    ],
)
def test_router_selects_remote_ocr_adapters(monkeypatch, provider_type, parser_type):
    router = documentprocessing.ManagedDocumentParser({".pdf": StubParser("azure"), "default": None})
    monkeypatch.setattr(documentprocessing, "get_default_profile", lambda extension: {"provider_id": "ocr-1"})
    monkeypatch.setattr(
        documentprocessing,
        "get_provider",
        lambda provider_id: {"name": "OCR", "provider_type": provider_type, "enabled": True, "config": {}},
    )
    assert isinstance(router.select_parser(NamedBytesIO(b"pdf")), parser_type)


def test_generic_response_path_and_page_metadata():
    payload = {"result": {"pages": [{"page": 2, "content": "hello", "score": 0.9}]}}
    item = documentprocessing._path_value(payload, "result.pages.0")
    assert item["content"] == "hello"
    page = Page(1, 0, "hello", metadata={"confidence": 0.9})
    assert page.metadata["confidence"] == 0.9


def test_google_processor_resource_and_text_anchor():
    parser = documentprocessing.GoogleDocumentAIParser(
        {
            "config": {
                "project_id": "project-1",
                "location": "asia-southeast1",
                "processor_id": "processor-1",
                "processor_version": "v2",
            }
        }
    )
    assert parser._processor_name().endswith("/processorVersions/v2")
    assert parser._api_endpoint() == "https://asia-southeast1-documentai.googleapis.com"
    assert parser._anchor_text("hello world", {"textAnchor": {"textSegments": [{"startIndex": "6", "endIndex": "11"}]}}) == "world"


class FakeHTTPResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def json(self, content_type=None):
        return self.payload


class FakeHTTPSession:
    payload = {}

    def __init__(self, *args, **kwargs):
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def post(self, url, **kwargs):
        self.request = (url, kwargs)
        return FakeHTTPResponse(self.payload)


@pytest.mark.asyncio
async def test_generic_ocr_parser_normalizes_pages(monkeypatch):
    FakeHTTPSession.payload = {
        "result": {"pages": [{"number": 1, "content": "first page", "tables": [{"name": "items"}], "score": 0.95}]}
    }
    monkeypatch.setattr(documentprocessing.aiohttp, "ClientSession", FakeHTTPSession)
    parser = documentprocessing.GenericOCRAPIParser(
        {
            "name": "Internal OCR",
            "config": {
                "endpoint": "http://ocr-api:8000",
                "process_path": "/ocr",
                "request_mode": "base64_json",
                "file_field": "file",
                "response_mapping": {
                    "pages_path": "result.pages",
                    "text_path": "content",
                    "page_number_path": "number",
                    "tables_path": "tables",
                    "confidence_path": "score",
                },
            },
        }
    )
    pages = [page async for page in parser.parse(NamedBytesIO(b"pdf"))]
    assert pages[0].page_num == 0
    assert "first page" in pages[0].text
    assert pages[0].metadata["confidence"] == 0.95


@pytest.mark.asyncio
async def test_paddleocr_parser_reads_official_response(monkeypatch):
    FakeHTTPSession.payload = {
        "result": {
            "ocrResults": [
                {"prunedResult": {"rec_texts": ["hello", "world"], "rec_scores": [0.8, 1.0]}}
            ]
        }
    }
    monkeypatch.setattr(documentprocessing.aiohttp, "ClientSession", FakeHTTPSession)
    parser = documentprocessing.PaddleOCRAPIParser(
        {"name": "Paddle", "config": {"endpoint": "http://paddleocr:8080", "process_path": "/ocr"}}
    )
    pages = [page async for page in parser.parse(NamedBytesIO(b"pdf"))]
    assert pages[0].text == "hello\nworld"
    assert pages[0].metadata["confidence"] == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_router_local_text_parser(monkeypatch):
    local = StubParser("local")
    router = documentprocessing.ManagedDocumentParser({".pdf": StubParser("azure"), "default": None, "local_text": local})
    monkeypatch.setattr(documentprocessing, "get_default_profile", lambda extension: {"provider_id": "local-text"})
    monkeypatch.setattr(documentprocessing, "get_provider", lambda provider_id: {"provider_type": "local_text", "enabled": True})
    pages = [page async for page in router.parse(NamedBytesIO(b"pdf"))]
    assert pages[0].text == "local"
