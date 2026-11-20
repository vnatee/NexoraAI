from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone
from typing import Any

from mongo_table_connecters.mongo_connector import get_database


db = get_database()
collection = db["knowledge_metadata_profiles"]

FIELD_TYPES = {"text", "keyword", "number", "date", "boolean", "enum"}
FIELD_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
MAX_FIELDS = 20
MAX_VALUE_LENGTH = 500

PRODUCT_KNOWLEDGE_FIELDS = [
    {"key": "product_family", "label": "Product family", "type": "keyword", "required": True, "options": []},
    {"key": "product_model", "label": "Product model", "type": "keyword", "required": False, "options": []},
    {"key": "brand", "label": "Brand", "type": "keyword", "required": False, "options": []},
    {
        "key": "document_type",
        "label": "Document type",
        "type": "enum",
        "required": True,
        "options": [
            "datasheet",
            "user_manual",
            "installation_guide",
            "troubleshooting",
            "faq",
            "service_policy",
            "warranty",
            "other",
        ],
    },
    {
        "key": "language",
        "label": "Language",
        "type": "enum",
        "required": True,
        "options": ["th", "en", "th-en", "other"],
    },
    {"key": "document_version", "label": "Document version", "type": "keyword", "required": False, "options": []},
    {
        "key": "lifecycle_status",
        "label": "Lifecycle status",
        "type": "enum",
        "required": True,
        "options": ["draft", "active", "superseded", "retired"],
    },
    {"key": "effective_date", "label": "Effective date", "type": "date", "required": False, "options": []},
    {"key": "keywords", "label": "Search keywords", "type": "text", "required": False, "options": []},
]


class MetadataProfileError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_indexes() -> None:
    collection.create_index(
        [("team_id", 1), ("name_key", 1)],
        unique=True,
        name="knowledge_metadata_profile_team_name",
    )
    collection.create_index(
        [("team_id", 1), ("deleted_at", 1)],
        name="knowledge_metadata_profile_team_active",
    )


def _normalize_fields(fields: object) -> list[dict[str, Any]]:
    if not isinstance(fields, list) or not fields or len(fields) > MAX_FIELDS:
        raise MetadataProfileError(f"fields must contain 1-{MAX_FIELDS} definitions")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in fields:
        if not isinstance(item, dict):
            raise MetadataProfileError("field definitions must be objects")
        key = str(item.get("key") or "").strip().lower()
        label = str(item.get("label") or "").strip()
        field_type = str(item.get("type") or "").strip().lower()
        if not FIELD_KEY_PATTERN.fullmatch(key) or key in seen:
            raise MetadataProfileError(f"invalid or duplicate metadata field: {key or '<empty>'}")
        if not label or len(label) > 80:
            raise MetadataProfileError(f"invalid label for metadata field: {key}")
        if field_type not in FIELD_TYPES:
            raise MetadataProfileError(f"unsupported metadata field type: {field_type}")
        options = [str(value).strip() for value in (item.get("options") or []) if str(value).strip()]
        if field_type == "enum" and not options:
            raise MetadataProfileError(f"enum metadata field requires options: {key}")
        if len(options) > 50 or any(len(value) > 100 for value in options):
            raise MetadataProfileError(f"metadata options are too large: {key}")
        seen.add(key)
        normalized.append(
            {
                "key": key,
                "label": label,
                "type": field_type,
                "required": item.get("required") is True,
                "options": list(dict.fromkeys(options)),
            }
        )
    return normalized


def ensure_product_knowledge_profile(team_id: str, actor_id: str) -> dict[str, Any]:
    team_id = str(team_id or "").strip()
    if not team_id:
        raise MetadataProfileError("team_id is required")
    existing = collection.find_one(
        {"team_id": team_id, "template_key": "product_knowledge_v1", "deleted_at": None}
    )
    if existing:
        return existing
    now = _now()
    document = {
        "_id": str(uuid.uuid4()),
        "team_id": team_id,
        "name": "Product Knowledge",
        "name_key": "product knowledge",
        "description": "Reusable metadata for product, manual, service, and troubleshooting Knowledge.",
        "template_key": "product_knowledge_v1",
        "version": 1,
        "fields": _normalize_fields(PRODUCT_KNOWLEDGE_FIELDS),
        "created_by": str(actor_id or ""),
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    collection.insert_one(document)
    return document


def list_metadata_profiles(team_id: str) -> list[dict[str, Any]]:
    return list(
        collection.find({"team_id": str(team_id or ""), "deleted_at": None}).sort("name_key", 1)
    )


def get_metadata_profile(profile_id: str) -> dict[str, Any] | None:
    return collection.find_one({"_id": str(profile_id or ""), "deleted_at": None})


def normalize_document_metadata(
    profile: dict[str, Any],
    values: object,
) -> tuple[dict[str, Any], str, list[str]]:
    if not isinstance(values, dict):
        raise MetadataProfileError("document_metadata must be an object")
    allowed = {field["key"]: field for field in profile.get("fields") or []}
    unknown = sorted(set(values) - set(allowed))
    if unknown:
        raise MetadataProfileError(f"unsupported metadata fields: {', '.join(unknown)}")

    normalized: dict[str, Any] = {}
    text_parts: list[str] = []
    pairs: list[str] = []
    for key, field in allowed.items():
        raw = values.get(key)
        if raw in (None, ""):
            if field.get("required"):
                raise MetadataProfileError(f"{field['label']} is required")
            continue
        field_type = field["type"]
        if field_type == "boolean":
            if not isinstance(raw, bool):
                raise MetadataProfileError(f"{field['label']} must be true or false")
            value: Any = raw
        elif field_type == "number":
            if isinstance(raw, bool):
                raise MetadataProfileError(f"{field['label']} must be a number")
            try:
                value = float(raw)
            except (TypeError, ValueError) as error:
                raise MetadataProfileError(f"{field['label']} must be a number") from error
        elif field_type == "date":
            value = str(raw).strip()
            try:
                date.fromisoformat(value)
            except ValueError as error:
                raise MetadataProfileError(f"{field['label']} must use YYYY-MM-DD") from error
        else:
            value = str(raw).strip()
            if not value or len(value) > MAX_VALUE_LENGTH:
                raise MetadataProfileError(f"{field['label']} is invalid")
            if field_type == "enum" and value not in (field.get("options") or []):
                raise MetadataProfileError(f"{field['label']} has an unsupported value")
        normalized[key] = value
        display_value = "true" if value is True else "false" if value is False else str(value)
        text_parts.append(f"{field['label']}: {display_value}")
        pairs.append(f"{key}={display_value}")
    return normalized, " | ".join(text_parts), pairs


def profile_projection(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "_id": str(profile.get("_id") or ""),
        "team_id": str(profile.get("team_id") or ""),
        "name": str(profile.get("name") or ""),
        "description": str(profile.get("description") or ""),
        "template_key": str(profile.get("template_key") or ""),
        "version": int(profile.get("version") or 1),
        "fields": list(profile.get("fields") or []),
    }
