from io import BytesIO

import pytest
from cryptography.fernet import Fernet
from quart.datastructures import FileStorage

import app as app_module
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


class FakeProfileCollection:
    def __init__(self):
        self.items = {}

    def update_many(self, query, update):
        return None

    def update_one(self, query, update, upsert=False):
        item_id = query["_id"]
        if "$setOnInsert" in update and item_id not in self.items:
            self.items[item_id] = dict(update["$setOnInsert"])
        elif "$set" in update and item_id in self.items:
            self.items[item_id].update(update["$set"])
        return None

    def find_one(self, query):
        return self.items.get(query["_id"])

    def insert_one(self, item):
        self.items[item["_id"]] = dict(item)


def test_profile_creation_is_idempotent_for_same_request_id(monkeypatch):
    collection = FakeProfileCollection()
    monkeypatch.setattr(storage, "profiles_collection", collection)
    request_id = "00ec4e94-1e98-4bc5-8a7a-982f33c6b7af"
    data = {
        "name": "PowerPoint",
        "provider_id": "docling-1",
        "file_types": [".pptx"],
        "languages": ["th", "en"],
        "extract_tables": True,
        "is_default": False,
        "enabled": True,
    }
    first = storage.save_profile(data, create_id=request_id)
    second = storage.save_profile(data, create_id=request_id)
    assert first["_id"] == second["_id"] == request_id
    assert len(collection.items) == 1


def test_routing_rule_validation_and_conflict(monkeypatch):
    monkeypatch.setattr(storage, "get_profile", lambda profile_id: {"_id": profile_id})
    rule = storage.normalize_routing_rule(
        {
            "name": "Global PDFs",
            "scope": "global",
            "file_types": [".PDF"],
            "profile_id": "profile-1",
            "priority": 80,
            "fallback_behavior": "continue",
        }
    )
    assert rule["file_types"] == [".pdf"]
    with pytest.raises(ValueError, match="conflicts"):
        storage.validate_routing_rule_conflicts(
            rule,
            [{"_id": "existing", **rule, "name": "Existing global PDFs"}],
        )


def _install_route_data(monkeypatch, rules, unavailable_profiles=()):
    profiles = {
        profile_id: {
            "_id": profile_id,
            "provider_id": f"provider-{profile_id}",
            "file_types": [".pdf"],
            "enabled": profile_id not in unavailable_profiles,
        }
        for profile_id in {str(rule["profile_id"]) for rule in rules}
    }
    monkeypatch.setattr(storage, "list_routing_rules", lambda enabled_only=False: rules)
    monkeypatch.setattr(storage, "get_profile", lambda profile_id: profiles.get(profile_id))
    monkeypatch.setattr(
        storage,
        "get_provider",
        lambda provider_id: {"_id": provider_id, "provider_type": "docling", "enabled": True},
    )
    monkeypatch.setattr(storage, "get_default_profile", lambda extension: None)


def test_route_precedence_team_scope_and_all(monkeypatch):
    rules = [
        {"_id": "all", "name": "All", "scope": "all", "team_id": "", "file_types": [".pdf"], "profile_id": "all-profile", "priority": 100, "enabled": True},
        {"_id": "global", "name": "Global", "scope": "global", "team_id": "", "file_types": [".pdf"], "profile_id": "global-profile", "priority": 80, "enabled": True},
        {"_id": "finance", "name": "Finance", "scope": "team", "team_id": "finance", "file_types": [".pdf"], "profile_id": "finance-profile", "priority": 70, "enabled": True},
    ]
    _install_route_data(monkeypatch, rules)
    assert storage.resolve_processing_route(file_extension=".pdf", scope="global")["rule"]["_id"] == "global"
    assert storage.resolve_processing_route(file_extension=".pdf", scope="team", team_id="finance")["rule"]["_id"] == "finance"
    assert storage.resolve_processing_route(file_extension=".pdf", scope="personal")["rule"]["_id"] == "all"


def test_route_exact_file_type_precedes_wildcard(monkeypatch):
    rules = [
        {"_id": "wildcard", "name": "Wildcard", "scope": "all", "team_id": "", "file_types": ["*"], "profile_id": "wildcard-profile", "priority": 1000, "enabled": True},
        {"_id": "pdf", "name": "PDF", "scope": "all", "team_id": "", "file_types": [".pdf"], "profile_id": "pdf-profile", "priority": 10, "enabled": True},
    ]
    _install_route_data(monkeypatch, rules)
    assert storage.resolve_processing_route(file_extension=".pdf", scope="personal")["rule"]["_id"] == "pdf"


def test_route_unavailable_profile_continue_and_error(monkeypatch):
    rules = [
        {"_id": "missing", "name": "Missing", "scope": "all", "team_id": "", "file_types": [".pdf"], "profile_id": "missing-profile", "priority": 100, "enabled": True, "fallback_behavior": "continue"},
        {"_id": "working", "name": "Working", "scope": "all", "team_id": "", "file_types": [".pdf"], "profile_id": "working-profile", "priority": 90, "enabled": True},
    ]
    _install_route_data(monkeypatch, rules, unavailable_profiles={"missing-profile"})
    route = storage.resolve_processing_route(file_extension=".pdf", scope="personal")
    assert route["rule"]["_id"] == "working"
    rules[0]["fallback_behavior"] = "error"
    route = storage.resolve_processing_route(file_extension=".pdf", scope="personal")
    assert route["status"] == "error"
    assert route["rule"]["_id"] == "missing"


def test_explicit_override_must_support_extension(monkeypatch):
    monkeypatch.setattr(
        storage,
        "get_profile",
        lambda profile_id: {"_id": profile_id, "provider_id": "provider-1", "file_types": [".png"], "enabled": True},
    )
    monkeypatch.setattr(storage, "get_provider", lambda provider_id: {"_id": provider_id, "enabled": True})
    route = storage.resolve_processing_route(
        file_extension=".pdf", scope="personal", explicit_profile_id="profile-1"
    )
    assert route["status"] == "error"


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


def test_router_uses_routing_context(monkeypatch):
    router = documentprocessing.ManagedDocumentParser({".pdf": StubParser("azure"), "default": None})
    monkeypatch.setattr(
        documentprocessing,
        "resolve_processing_route",
        lambda **kwargs: {
            "status": "matched",
            "profile": {"languages": ["en"], "extract_tables": True},
            "provider": {
                "provider_type": "docling",
                "config": {"execution_mode": "service", "endpoint": "http://docling:5001"},
            },
        },
    )
    parser = router.select_parser(
        NamedBytesIO(b"pdf"),
        routing_context={"scope": "team", "team_id": "finance", "explicit_profile_id": ""},
    )
    assert isinstance(parser, documentprocessing.DoclingParser)


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


@pytest.mark.asyncio
async def test_document_processing_management_requires_system_admin(auth_client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "get_user_by_ad_email",
        lambda username: {"active": True, "is_sys_admin": False},
    )
    response = await auth_client.get(
        "/document_processing/providers", headers={"Authorization": "Bearer test"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_upload_options_hide_manual_profiles_from_non_admin(auth_client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "get_user_by_ad_email",
        lambda username: {"active": True, "is_sys_admin": False},
    )
    response = await auth_client.get(
        "/document_processing/upload-options", headers={"Authorization": "Bearer test"}
    )
    assert response.status_code == 200
    assert await response.get_json() == {"can_override": False, "profiles": []}


@pytest.mark.asyncio
async def test_personal_upload_rejects_unauthorized_profile_override(auth_client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "get_user_by_ad_email",
        lambda username: {"active": True, "is_sys_admin": False},
    )
    response = await auth_client.post(
        "/upload",
        headers={"Authorization": "Bearer test"},
        form={"processing_profile_id": "profile-1"},
        files={"file": FileStorage(BytesIO(b"content"), filename="sample.pdf")},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_profile_save_replays_same_create_request_without_duplicate(auth_client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "get_user_by_ad_email",
        lambda username: {"active": True, "is_sys_admin": True},
    )
    monkeypatch.setattr(storage, "get_provider", lambda provider_id: {"_id": provider_id, "config": {}})
    monkeypatch.setattr(app_module, "get_document_provider", lambda provider_id: {"_id": provider_id, "config": {}})
    profiles = []
    monkeypatch.setattr(app_module, "list_document_profiles", lambda: list(profiles))

    def fake_save(data, profile_id="", create_id=""):
        item = {"_id": create_id, **data}
        profiles.append(item)
        return item

    monkeypatch.setattr(app_module, "save_document_profile", fake_save)
    payload = {
        "client_request_id": "00ec4e94-1e98-4bc5-8a7a-982f33c6b7af",
        "name": "PowerPoint",
        "provider_id": "docling-1",
        "file_types": [".pptx"],
        "languages": ["th", "en"],
    }
    first = await auth_client.post(
        "/document_processing/profiles/save",
        headers={"Authorization": "Bearer test"},
        json=payload,
    )
    second = await auth_client.post(
        "/document_processing/profiles/save",
        headers={"Authorization": "Bearer test"},
        json=payload,
    )
    assert first.status_code == second.status_code == 200
    assert (await first.get_json())["profile"]["_id"] == payload["client_request_id"]
    assert (await second.get_json())["profile"]["_id"] == payload["client_request_id"]
    assert len(profiles) == 1


@pytest.mark.asyncio
async def test_profile_save_rejects_duplicate_name_with_new_request(auth_client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "get_user_by_ad_email",
        lambda username: {"active": True, "is_sys_admin": True},
    )
    monkeypatch.setattr(storage, "get_provider", lambda provider_id: {"_id": provider_id, "config": {}})
    monkeypatch.setattr(
        app_module,
        "list_document_profiles",
        lambda: [{"_id": "existing", "name": "PowerPoint", "provider_id": "docling-1"}],
    )
    response = await auth_client.post(
        "/document_processing/profiles/save",
        headers={"Authorization": "Bearer test"},
        json={
            "client_request_id": "eeb04512-ee04-48a4-8637-2b7357686c82",
            "name": " powerpoint ",
            "provider_id": "docling-1",
            "file_types": [".pptx"],
            "languages": ["en"],
        },
    )
    assert response.status_code == 409
    assert "already exists" in (await response.get_json())["error"]
