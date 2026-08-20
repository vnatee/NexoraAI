import json
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from core.provider_secrets import decrypt_provider_secret, encrypt_provider_secret
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
providers_collection = db["document_processing_providers"]
profiles_collection = db["document_processing_profiles"]
PROVIDER_TYPES = {
    "azure_document_intelligence",
    "docling",
    "google_document_ai",
    "generic_ocr_api",
    "paddleocr",
    "local_text",
}


def _http_endpoint(value: object, label: str) -> str:
    endpoint = str(value or "").strip().rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"A valid {label} HTTP(S) endpoint is required")
    return endpoint


def normalize_docling_endpoint(value: object) -> str:
    endpoint = _http_endpoint(value, "Docling Serve")
    for suffix in ("/health", "/ready", "/docs", "/ui"):
        if endpoint.lower().endswith(suffix):
            endpoint = endpoint[: -len(suffix)].rstrip("/")
            break
    return endpoint


def normalize_provider(data: object, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Provider payload must be an object")
    old = existing or {}
    provider_type = str(data.get("provider_type") or old.get("provider_type") or "").strip().lower()
    if provider_type not in PROVIDER_TYPES:
        raise ValueError("Unsupported document processing provider")
    name = str(data.get("name") or old.get("name") or "").strip()
    if not name:
        raise ValueError("Provider name is required")
    config = dict(old.get("config") or {})
    incoming = data.get("config") or {}
    if not isinstance(incoming, dict):
        raise ValueError("config must be an object")
    config.update(incoming)
    if provider_type == "docling":
        execution_mode = str(config.get("execution_mode") or "service").strip().lower()
        if execution_mode not in {"service", "embedded"}:
            raise ValueError("Docling execution_mode must be service or embedded")
        config["execution_mode"] = execution_mode
        if execution_mode == "service":
            config["endpoint"] = normalize_docling_endpoint(config.get("endpoint"))
    elif provider_type in {"generic_ocr_api", "paddleocr"}:
        config["endpoint"] = _http_endpoint(config.get("endpoint"), "OCR API")
        config["process_path"] = str(
            config.get("process_path") or ("/ocr" if provider_type == "paddleocr" else "/v1/ocr")
        ).strip()
        config["health_path"] = str(config.get("health_path") or "/docs").strip()
        if not config["process_path"].startswith("/") or not config["health_path"].startswith("/"):
            raise ValueError("OCR API process_path and health_path must start with /")
        auth_type = str(config.get("auth_type") or "none").strip().lower()
        if auth_type not in {"none", "api_key", "bearer"}:
            raise ValueError("OCR API auth_type must be none, api_key or bearer")
        config["auth_type"] = auth_type
        config["api_key_header"] = str(config.get("api_key_header") or "X-API-Key").strip()
        if provider_type == "generic_ocr_api":
            request_mode = str(config.get("request_mode") or "multipart").strip().lower()
            if request_mode not in {"multipart", "base64_json"}:
                raise ValueError("Generic OCR request_mode must be multipart or base64_json")
            config["request_mode"] = request_mode
            config["file_field"] = str(config.get("file_field") or "file").strip()
            mapping = config.get("response_mapping") or {}
            if not isinstance(mapping, dict):
                raise ValueError("response_mapping must be an object")
            config["response_mapping"] = {
                "pages_path": str(mapping.get("pages_path") or "pages"),
                "text_path": str(mapping.get("text_path") or "text"),
                "page_number_path": str(mapping.get("page_number_path") or "page_number"),
                "tables_path": str(mapping.get("tables_path") or "tables"),
                "confidence_path": str(mapping.get("confidence_path") or "confidence"),
            }
    elif provider_type == "google_document_ai":
        project_id = str(config.get("project_id") or "").strip()
        location = str(config.get("location") or "us").strip().lower()
        processor_id = str(config.get("processor_id") or "").strip()
        if not project_id or not location or not processor_id:
            raise ValueError("Google project_id, location and processor_id are required")
        config.update({"project_id": project_id, "location": location, "processor_id": processor_id})
        config["processor_version"] = str(config.get("processor_version") or "").strip()
        if config.get("api_endpoint"):
            config["api_endpoint"] = _http_endpoint(config.get("api_endpoint"), "Google Document AI")

    credentials_ciphertext = old.get("credentials_ciphertext")
    credentials = None
    if data.get("clear_credentials") is True:
        credentials_ciphertext = None
    else:
        credentials = data.get("credentials")
    if credentials is not None and credentials != "":
        if isinstance(credentials, dict):
            credentials = json.dumps(credentials, ensure_ascii=False)
        credentials_ciphertext = encrypt_provider_secret(str(credentials))
    if provider_type == "google_document_ai" and not credentials_ciphertext:
        raise ValueError("Google Document AI requires Service Account JSON credentials")
    if provider_type in {"generic_ocr_api", "paddleocr"} and config.get("auth_type") != "none" and not credentials_ciphertext:
        raise ValueError("OCR API credentials are required for the selected authentication type")
    return {
        "name": name[:100], "provider_type": provider_type, "config": config,
        "enabled": data.get("enabled", old.get("enabled", True)) is not False,
        "system_managed": old.get("system_managed", data.get("system_managed", False)) is True,
        "credentials_ciphertext": credentials_ciphertext,
    }


def serialize_provider(item: dict[str, Any]) -> dict[str, Any]:
    serialized = {
        key: value
        for key, value in item.items()
        if key not in {"created_at", "updated_at", "delete_at", "credentials_ciphertext"}
    }
    return serialized | {"has_credentials": bool(item.get("credentials_ciphertext"))}


def decrypt_provider_credentials(item: dict[str, Any]) -> str:
    return decrypt_provider_secret(item.get("credentials_ciphertext")) or ""


def list_providers() -> list[dict[str, Any]]:
    return list(providers_collection.find({"delete_at": None}).sort("name", 1))


def get_provider(provider_id: str) -> dict[str, Any] | None:
    return providers_collection.find_one({"_id": provider_id, "delete_at": None})


def save_provider(data: dict[str, Any], provider_id: str = "") -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    if provider_id:
        providers_collection.update_one({"_id": provider_id, "delete_at": None}, {"$set": {**data, "updated_at": now}})
        return get_provider(provider_id) or {"_id": provider_id, **data}
    item = {"_id": str(uuid.uuid4()), **data, "created_at": now, "updated_at": now, "delete_at": None}
    providers_collection.insert_one(item)
    return item


def delete_provider(provider_id: str) -> bool:
    return providers_collection.update_one({"_id": provider_id, "delete_at": None, "system_managed": {"$ne": True}}, {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc)}}).matched_count > 0


def normalize_profile(data: object, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Profile payload must be an object")
    old = existing or {}
    name = str(data.get("name") or old.get("name") or "").strip()
    provider_id = str(data.get("provider_id") or old.get("provider_id") or "")
    if not name or not get_provider(provider_id):
        raise ValueError("Profile name and a valid provider are required")
    file_types = data.get("file_types", old.get("file_types", [".pdf", ".png", ".jpg", ".jpeg", ".tiff"]))
    if not isinstance(file_types, list):
        raise ValueError("file_types must be an array")
    return {
        "name": name[:100], "provider_id": provider_id,
        "file_types": [str(v).lower() for v in file_types if str(v).startswith(".")],
        "languages": [str(v) for v in data.get("languages", old.get("languages", ["en"]))],
        "extract_tables": data.get("extract_tables", old.get("extract_tables", True)) is not False,
        "is_default": data.get("is_default", old.get("is_default", False)) is True,
        "enabled": data.get("enabled", old.get("enabled", True)) is not False,
    }


def list_profiles() -> list[dict[str, Any]]:
    return list(profiles_collection.find({"delete_at": None}).sort("name", 1))


def get_default_profile(file_extension: str) -> dict[str, Any] | None:
    return profiles_collection.find_one({"delete_at": None, "enabled": True, "is_default": True, "file_types": file_extension.lower()})


def save_profile(data: dict[str, Any], profile_id: str = "") -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    if data.get("is_default"):
        profiles_collection.update_many({"delete_at": None, "_id": {"$ne": profile_id}}, {"$set": {"is_default": False}})
    if profile_id:
        profiles_collection.update_one({"_id": profile_id, "delete_at": None}, {"$set": {**data, "updated_at": now}})
        return profiles_collection.find_one({"_id": profile_id}) or {"_id": profile_id, **data}
    item = {"_id": str(uuid.uuid4()), **data, "created_at": now, "updated_at": now, "delete_at": None}
    profiles_collection.insert_one(item)
    return item


def delete_profile(profile_id: str) -> bool:
    return profiles_collection.update_one({"_id": profile_id, "delete_at": None}, {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc)}}).matched_count > 0


def ensure_system_providers(has_azure: bool) -> None:
    definitions = [("local-text", "Local text extraction", "local_text")]
    if has_azure:
        definitions.insert(0, ("system-azure-document-intelligence", "Azure Document Intelligence (system)", "azure_document_intelligence"))
    for provider_id, name, provider_type in definitions:
        providers_collection.update_one({"_id": provider_id}, {"$setOnInsert": {"_id": provider_id, "name": name, "provider_type": provider_type, "config": {}, "enabled": True, "system_managed": True, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc), "delete_at": None}}, upsert=True)
