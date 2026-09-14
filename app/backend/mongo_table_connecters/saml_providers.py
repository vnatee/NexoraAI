from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from cryptography import x509
from onelogin.saml2.settings import OneLogin_Saml2_Settings

from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["saml_providers"]


def ensure_saml_provider_indexes() -> None:
    collection.create_index("entity_id", name="saml_provider_entity_id")
    collection.create_index("enabled", name="saml_provider_enabled")


def _domains(value: Any) -> list[str]:
    values = value.split(",") if isinstance(value, str) else (value or [])
    domains = sorted({str(item).strip().lower().lstrip("@") for item in values if str(item).strip()})
    if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", item) for item in domains):
        raise ValueError("SAML allowed email domains contain an invalid domain")
    return domains


def _https_url(value: Any, field: str) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"SAML {field} must be an absolute HTTPS URL")
    return url


def normalize_x509_certificate(value: Any) -> str:
    certificate = str(value or "").strip().replace("\r", "")
    if not certificate:
        raise ValueError("SAML identity provider signing certificate is required")
    if "BEGIN CERTIFICATE" not in certificate:
        compact = "".join(certificate.split())
        certificate = f"-----BEGIN CERTIFICATE-----\n{compact}\n-----END CERTIFICATE-----"
    if len(certificate) > 32768:
        raise ValueError("SAML identity provider signing certificate is too large")
    try:
        parsed = x509.load_pem_x509_certificate(certificate.encode("utf-8"))
        not_before = parsed.not_valid_before_utc
        not_after = parsed.not_valid_after_utc
    except (ValueError, TypeError) as error:
        raise ValueError("SAML identity provider signing certificate is invalid") from error
    now = datetime.now(timezone.utc)
    if now < not_before or now >= not_after:
        raise ValueError("SAML identity provider signing certificate is not currently valid")
    return certificate


def saml_settings(provider: dict[str, Any], *, acs_url: str, metadata_url: str) -> dict[str, Any]:
    settings = {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": metadata_url,
            "assertionConsumerService": {
                "url": acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified",
            "x509cert": "",
            "privateKey": "",
        },
        "idp": {
            "entityId": str(provider.get("entity_id") or ""),
            "singleSignOnService": {
                "url": str(provider.get("sso_url") or ""),
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": str(provider.get("x509_cert") or ""),
        },
        "security": {
            "authnRequestsSigned": False,
            "logoutRequestSigned": False,
            "logoutResponseSigned": False,
            "signMetadata": False,
            "wantMessagesSigned": False,
            "wantAssertionsSigned": True,
            "wantAssertionsEncrypted": False,
            "wantNameIdEncrypted": False,
            "requestedAuthnContext": False,
            "rejectUnsolicitedResponsesWithInResponseTo": True,
            "allowSingleLabelDomains": False,
        },
    }
    try:
        errors = OneLogin_Saml2_Settings(settings).get_errors()
    except Exception as error:
        raise ValueError("Invalid SAML configuration") from error
    if errors:
        raise ValueError("Invalid SAML configuration: " + ", ".join(errors))
    return settings


def list_saml_providers() -> list[dict[str, Any]]:
    return [dict(item) for item in collection.find({"delete_at": None}).sort("display_name", 1)]


def get_saml_provider(provider_id: str) -> dict[str, Any] | None:
    document = collection.find_one({"_id": str(provider_id), "delete_at": None})
    return dict(document) if document else None


def serialize_saml_provider(provider: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(provider.get("_id") or ""),
        "enabled": provider.get("enabled") is True,
        "display_name": str(provider.get("display_name") or "Enterprise SAML"),
        "entity_id": str(provider.get("entity_id") or ""),
        "sso_url": str(provider.get("sso_url") or ""),
        "x509_cert": str(provider.get("x509_cert") or ""),
        "email_attribute": str(provider.get("email_attribute") or "email"),
        "first_name_attribute": str(provider.get("first_name_attribute") or "firstName"),
        "last_name_attribute": str(provider.get("last_name_attribute") or "lastName"),
        "jit_enabled": provider.get("jit_enabled") is True,
        "allowed_domains": [str(item) for item in (provider.get("allowed_domains") or [])],
    }


def public_saml_providers() -> list[dict[str, str]]:
    return [
        {"id": str(item.get("_id") or ""), "display_name": str(item.get("display_name") or "Enterprise SAML")}
        for item in list_saml_providers()
        if item.get("enabled") is True
    ]


def save_saml_provider(payload: dict[str, Any], provider_id: str | None = None) -> dict[str, Any]:
    provider_id = str(provider_id or uuid.uuid4())
    try:
        provider_id = str(uuid.UUID(provider_id))
    except ValueError as error:
        raise ValueError("SAML provider ID is invalid") from error
    display_name = str(payload.get("display_name") or "").strip()
    entity_id = str(payload.get("entity_id") or "").strip()
    sso_url = _https_url(payload.get("sso_url"), "SSO URL")
    x509_cert = normalize_x509_certificate(payload.get("x509_cert"))
    allowed_domains = _domains(payload.get("allowed_domains"))
    jit_enabled = payload.get("jit_enabled") is True
    if not display_name or len(display_name) > 80:
        raise ValueError("SAML provider name is required and must not exceed 80 characters")
    if not entity_id or len(entity_id) > 2048:
        raise ValueError("SAML identity provider entity ID is required")
    if jit_enabled and not allowed_domains:
        raise ValueError("At least one allowed email domain is required when SAML JIT provisioning is enabled")
    attributes = {}
    for field, default in (
        ("email_attribute", "email"),
        ("first_name_attribute", "firstName"),
        ("last_name_attribute", "lastName"),
    ):
        value = str(payload.get(field) or default).strip()
        if not value or len(value) > 256:
            raise ValueError(f"SAML {field.replace('_', ' ')} is invalid")
        attributes[field] = value
    update = {
        "enabled": payload.get("enabled") is True,
        "display_name": display_name,
        "entity_id": entity_id,
        "sso_url": sso_url,
        "x509_cert": x509_cert,
        "jit_enabled": jit_enabled,
        "allowed_domains": allowed_domains,
        **attributes,
        "updated_at": datetime.now(timezone.utc),
        "delete_at": None,
    }
    saml_settings(
        {"_id": provider_id, **update},
        acs_url=f"https://nexora.invalid/auth/saml/{provider_id}/acs",
        metadata_url=f"https://nexora.invalid/auth/saml/{provider_id}/metadata",
    )
    collection.update_one(
        {"_id": provider_id},
        {"$set": update, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return get_saml_provider(provider_id) or {"_id": provider_id, **update}


def delete_saml_provider(provider_id: str) -> bool:
    result = collection.update_one(
        {"_id": str(provider_id), "delete_at": None},
        {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0
