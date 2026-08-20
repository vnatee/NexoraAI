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
routing_rules_collection = db["document_processing_routing_rules"]
PROVIDER_TYPES = {
    "azure_document_intelligence",
    "docling",
    "google_document_ai",
    "generic_ocr_api",
    "paddleocr",
    "local_text",
}
ROUTING_SCOPES = {"all", "personal", "team", "global"}
ROUTING_FALLBACK_BEHAVIORS = {"continue", "system", "error"}


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


def get_profile(profile_id: str) -> dict[str, Any] | None:
    return profiles_collection.find_one({"_id": profile_id, "delete_at": None})


def get_default_profile(file_extension: str) -> dict[str, Any] | None:
    return profiles_collection.find_one({"delete_at": None, "enabled": True, "is_default": True, "file_types": file_extension.lower()})


def save_profile(
    data: dict[str, Any], profile_id: str = "", create_id: str = ""
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    target_id = profile_id or create_id
    if data.get("is_default"):
        profiles_collection.update_many({"delete_at": None, "_id": {"$ne": target_id}}, {"$set": {"is_default": False}})
    if profile_id:
        profiles_collection.update_one({"_id": profile_id, "delete_at": None}, {"$set": {**data, "updated_at": now}})
        return profiles_collection.find_one({"_id": profile_id}) or {"_id": profile_id, **data}
    item_id = create_id or str(uuid.uuid4())
    item = {"_id": item_id, **data, "created_at": now, "updated_at": now, "delete_at": None}
    if create_id:
        profiles_collection.update_one(
            {"_id": item_id}, {"$setOnInsert": item}, upsert=True
        )
        return profiles_collection.find_one({"_id": item_id}) or item
    profiles_collection.insert_one(item)
    return item


def delete_profile(profile_id: str) -> bool:
    if routing_rules_collection.find_one({"profile_id": profile_id, "delete_at": None}):
        return False
    return profiles_collection.update_one({"_id": profile_id, "delete_at": None}, {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc)}}).matched_count > 0


def _normalize_rule_file_types(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("file_types must be an array")
    normalized: list[str] = []
    for item in value:
        file_type = str(item or "").strip().lower()
        if file_type != "*" and not file_type.startswith("."):
            raise ValueError("Routing rule file types must be * or extensions beginning with .")
        if file_type and file_type not in normalized:
            normalized.append(file_type)
    if not normalized:
        raise ValueError("At least one routing rule file type is required")
    return normalized


def normalize_routing_rule(data: object, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Routing rule payload must be an object")
    old = existing or {}
    name = str(data.get("name") or old.get("name") or "").strip()
    if not name:
        raise ValueError("Routing rule name is required")
    scope = str(data.get("scope") or old.get("scope") or "all").strip().lower()
    if scope not in ROUTING_SCOPES:
        raise ValueError("Routing rule scope must be all, personal, team or global")
    team_id = str(data.get("team_id") or old.get("team_id") or "").strip()
    if scope == "team" and not team_id:
        raise ValueError("A team routing rule requires team_id")
    if scope != "team":
        team_id = ""
    profile_id = str(data.get("profile_id") or old.get("profile_id") or "").strip()
    if not profile_id or not get_profile(profile_id):
        raise ValueError("A valid processing profile is required")
    fallback_behavior = str(
        data.get("fallback_behavior") or old.get("fallback_behavior") or "continue"
    ).strip().lower()
    if fallback_behavior not in ROUTING_FALLBACK_BEHAVIORS:
        raise ValueError("fallback_behavior must be continue, system or error")
    try:
        priority = int(data.get("priority", old.get("priority", 100)))
    except (TypeError, ValueError) as exc:
        raise ValueError("Routing rule priority must be an integer") from exc
    return {
        "name": name[:100],
        "scope": scope,
        "team_id": team_id,
        "file_types": _normalize_rule_file_types(data.get("file_types", old.get("file_types", ["*"]))),
        "profile_id": profile_id,
        "priority": max(-100000, min(priority, 100000)),
        "enabled": data.get("enabled", old.get("enabled", True)) is not False,
        "fallback_behavior": fallback_behavior,
    }


def list_routing_rules(*, enabled_only: bool = False) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"delete_at": None}
    if enabled_only:
        query["enabled"] = True
    return list(routing_rules_collection.find(query).sort([("priority", -1), ("name", 1)]))


def get_routing_rule(rule_id: str) -> dict[str, Any] | None:
    return routing_rules_collection.find_one({"_id": rule_id, "delete_at": None})


def _rule_file_overlap(left: list[str], right: list[str]) -> bool:
    exact_overlap = (set(left) - {"*"}) & (set(right) - {"*"})
    return bool(exact_overlap or ("*" in left and "*" in right))


def validate_routing_rule_conflicts(
    candidate: dict[str, Any], rules: list[dict[str, Any]], rule_id: str = ""
) -> None:
    if not candidate.get("enabled"):
        return
    for rule in rules:
        if str(rule.get("_id") or "") == rule_id or not rule.get("enabled", True):
            continue
        if (
            rule.get("scope") == candidate.get("scope")
            and str(rule.get("team_id") or "") == str(candidate.get("team_id") or "")
            and int(rule.get("priority", 100)) == int(candidate.get("priority", 100))
            and _rule_file_overlap(rule.get("file_types") or ["*"], candidate.get("file_types") or ["*"])
        ):
            raise ValueError(
                f"Routing rule conflicts with '{rule.get('name') or rule.get('_id')}' at the same scope, file type and priority"
            )


def save_routing_rule(data: dict[str, Any], rule_id: str = "") -> dict[str, Any]:
    validate_routing_rule_conflicts(data, list_routing_rules(), rule_id)
    now = datetime.now(timezone.utc)
    if rule_id:
        routing_rules_collection.update_one(
            {"_id": rule_id, "delete_at": None}, {"$set": {**data, "updated_at": now}}
        )
        return get_routing_rule(rule_id) or {"_id": rule_id, **data}
    item = {
        "_id": str(uuid.uuid4()),
        **data,
        "created_at": now,
        "updated_at": now,
        "delete_at": None,
    }
    routing_rules_collection.insert_one(item)
    return item


def delete_routing_rule(rule_id: str) -> bool:
    return routing_rules_collection.update_one(
        {"_id": rule_id, "delete_at": None},
        {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc)}},
    ).matched_count > 0


def _matching_rule_sort_key(rule: dict[str, Any], scope: str, team_id: str, extension: str):
    if rule.get("scope") == "team" and team_id and rule.get("team_id") == team_id:
        scope_rank = 0
    elif rule.get("scope") == scope and scope != "team":
        scope_rank = 1
    elif rule.get("scope") == "all":
        scope_rank = 2
    else:
        return None
    file_types = rule.get("file_types") or ["*"]
    if extension in file_types:
        file_rank = 0
    elif "*" in file_types:
        file_rank = 1
    else:
        return None
    return (scope_rank, file_rank, -int(rule.get("priority", 100)), str(rule.get("name") or rule.get("_id") or ""))


def resolve_processing_route(
    *,
    file_extension: str,
    scope: str,
    team_id: str = "",
    explicit_profile_id: str = "",
) -> dict[str, Any]:
    extension = file_extension.lower()
    normalized_scope = scope.lower()
    if normalized_scope not in {"personal", "team", "global"}:
        raise ValueError("Upload scope must be personal, team or global")

    def available(profile_id: str):
        profile = get_profile(profile_id)
        provider = get_provider(str((profile or {}).get("provider_id") or "")) if profile else None
        if not profile or profile.get("enabled") is False or not provider or provider.get("enabled") is False:
            return None, None
        if extension not in (profile.get("file_types") or []):
            return None, None
        return profile, provider

    if explicit_profile_id:
        profile, provider = available(explicit_profile_id)
        if not profile:
            return {
                "source": "explicit_override",
                "status": "error",
                "reason": "The selected processing profile is unavailable or does not support this file type",
                "profile": None,
                "provider": None,
                "rule": None,
                "candidates": [],
            }
        return {
            "source": "explicit_override", "status": "matched", "reason": "Authorized upload override",
            "profile": profile, "provider": provider, "rule": None, "candidates": [],
        }

    ranked: list[tuple[tuple, dict[str, Any]]] = []
    for rule in list_routing_rules(enabled_only=True):
        key = _matching_rule_sort_key(rule, normalized_scope, team_id, extension)
        if key is not None:
            ranked.append((key, rule))
    ranked.sort(key=lambda item: item[0])
    candidates: list[dict[str, Any]] = []
    for _, rule in ranked:
        profile, provider = available(str(rule.get("profile_id") or ""))
        candidates.append({
            "rule_id": rule.get("_id"), "name": rule.get("name"),
            "profile_id": rule.get("profile_id"), "available": bool(profile),
            "fallback_behavior": rule.get("fallback_behavior", "continue"),
        })
        if profile:
            return {
                "source": "routing_rule", "status": "matched", "reason": "Matched enabled routing rule",
                "profile": profile, "provider": provider, "rule": rule, "candidates": candidates,
            }
        fallback_behavior = rule.get("fallback_behavior", "continue")
        if fallback_behavior == "error":
            return {
                "source": "routing_rule", "status": "error",
                "reason": "The matched routing rule's profile or provider is unavailable",
                "profile": None, "provider": None, "rule": rule, "candidates": candidates,
            }
        if fallback_behavior == "system":
            break

    legacy_profile = get_default_profile(extension)
    legacy_provider = get_provider(str((legacy_profile or {}).get("provider_id") or "")) if legacy_profile else None
    if legacy_profile and legacy_profile.get("enabled") is not False and legacy_provider and legacy_provider.get("enabled") is not False:
        return {
            "source": "legacy_default", "status": "matched",
            "reason": "No active routing rule matched; using the legacy default profile",
            "profile": legacy_profile, "provider": legacy_provider, "rule": None, "candidates": candidates,
        }
    return {
        "source": "system_fallback", "status": "fallback",
        "reason": "No active routing rule or legacy default profile matched",
        "profile": None, "provider": None, "rule": None, "candidates": candidates,
    }


def ensure_system_providers(has_azure: bool) -> None:
    definitions = [("local-text", "Local text extraction", "local_text")]
    if has_azure:
        definitions.insert(0, ("system-azure-document-intelligence", "Azure Document Intelligence (system)", "azure_document_intelligence"))
    for provider_id, name, provider_type in definitions:
        providers_collection.update_one({"_id": provider_id}, {"$setOnInsert": {"_id": provider_id, "name": name, "provider_type": provider_type, "config": {}, "enabled": True, "system_managed": True, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc), "delete_at": None}}, upsert=True)
