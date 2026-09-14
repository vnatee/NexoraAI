from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from mongo_table_connecters import saml_providers


class Cursor(list):
    def sort(self, key, direction):
        return Cursor(sorted(self, key=lambda item: item.get(key) or ""))


class MemoryCollection:
    def __init__(self):
        self.documents: list[dict] = []

    def create_index(self, *args, **kwargs):
        return None

    def find(self, query):
        return Cursor(deepcopy([item for item in self.documents if all(item.get(k) == v for k, v in query.items())]))

    def find_one(self, query):
        return next((deepcopy(item) for item in self.documents if all(item.get(k) == v for k, v in query.items())), None)

    def update_one(self, query, update, upsert=False):
        for item in self.documents:
            if all(item.get(k) == v for k, v in query.items()):
                item.update(deepcopy(update.get("$set") or {}))
                return type("Result", (), {"modified_count": 1})()
        if upsert:
            document = deepcopy(query)
            document.update(deepcopy(update.get("$setOnInsert") or {}))
            document.update(deepcopy(update.get("$set") or {}))
            self.documents.append(document)
        return type("Result", (), {"modified_count": 0})()


@pytest.fixture
def signing_certificate():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "id.example.com")])
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .sign(key, hashes.SHA256())
        .public_bytes(serialization.Encoding.PEM)
        .decode()
    )


@pytest.fixture
def store(monkeypatch):
    collection = MemoryCollection()
    monkeypatch.setattr(saml_providers, "collection", collection)
    return collection


def payload(certificate, **overrides):
    result = {
        "enabled": False,
        "display_name": "Company SAML",
        "entity_id": "https://id.example.com/entity",
        "sso_url": "https://id.example.com/saml/sso",
        "x509_cert": certificate,
        "email_attribute": "mail",
        "first_name_attribute": "givenName",
        "last_name_attribute": "surname",
        "jit_enabled": True,
        "allowed_domains": ["EXAMPLE.com"],
    }
    result.update(overrides)
    return result


def test_provider_is_validated_and_serialized(store, signing_certificate):
    provider_id = "b8b87e21-c5cb-448f-b6c6-a05c4bba6dd4"
    provider = saml_providers.save_saml_provider(payload(signing_certificate), provider_id)

    serialized = saml_providers.serialize_saml_provider(provider)
    assert serialized["id"] == provider_id
    assert serialized["allowed_domains"] == ["example.com"]
    assert "BEGIN CERTIFICATE" in serialized["x509_cert"]


def test_provider_requires_https_sso(store, signing_certificate):
    with pytest.raises(ValueError, match="HTTPS"):
        saml_providers.save_saml_provider(payload(signing_certificate, sso_url="http://id.example.com/sso"))


def test_security_policy_requires_signed_assertions(signing_certificate):
    settings = saml_providers.saml_settings(
        payload(signing_certificate),
        acs_url="https://portal.example.com/auth/saml/id/acs",
        metadata_url="https://portal.example.com/auth/saml/id/metadata",
    )

    assert settings["strict"] is True
    assert settings["security"]["wantAssertionsSigned"] is True
    assert settings["security"]["rejectUnsolicitedResponsesWithInResponseTo"] is True
