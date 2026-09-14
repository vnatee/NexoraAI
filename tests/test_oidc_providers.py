from __future__ import annotations

from copy import deepcopy

import pytest
from cryptography.fernet import Fernet

from mongo_table_connecters import oidc_providers


class Cursor(list):
    def sort(self, key, direction):
        return Cursor(sorted(self, key=lambda item: item.get(key) or ""))


class MemoryCollection:
    def __init__(self):
        self.documents: list[dict] = []

    @staticmethod
    def _matches(document, query):
        for key, expected in query.items():
            actual = document.get(key)
            if isinstance(expected, dict) and "$ne" in expected:
                if actual == expected["$ne"]:
                    return False
            elif isinstance(expected, dict) and "$in" in expected:
                values = actual if isinstance(actual, list) else [actual]
                if not set(values).intersection(expected["$in"]):
                    return False
            elif actual != expected:
                return False
        return True

    def create_index(self, *args, **kwargs):
        return None

    def find(self, query):
        return Cursor(deepcopy([item for item in self.documents if self._matches(item, query)]))

    def find_one(self, query, projection=None):
        return next((deepcopy(item) for item in self.documents if self._matches(item, query)), None)

    def update_one(self, query, update, upsert=False):
        for item in self.documents:
            if self._matches(item, query):
                item.update(deepcopy(update.get("$set") or {}))
                return type("Result", (), {"modified_count": 1})()
        if upsert:
            document = {key: value for key, value in query.items() if not isinstance(value, dict)}
            document.update(deepcopy(update.get("$setOnInsert") or {}))
            document.update(deepcopy(update.get("$set") or {}))
            self.documents.append(document)
            return type("Result", (), {"modified_count": 0})()
        return type("Result", (), {"modified_count": 0})()


@pytest.fixture
def store(monkeypatch):
    collection = MemoryCollection()
    monkeypatch.setattr(oidc_providers, "collection", collection)
    monkeypatch.setattr(oidc_providers, "get_auth_settings", lambda **kwargs: None)
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    return collection


def payload(**overrides):
    result = {
        "enabled": True,
        "display_name": "Company SSO",
        "issuer": "https://id.example.com",
        "client_id": "nexora",
        "client_secret": "top-secret",
        "token_auth_method": "client_secret_basic",
        "jit_enabled": True,
        "allowed_domains": ["EXAMPLE.com"],
    }
    result.update(overrides)
    return result


def test_secret_is_encrypted_and_never_serialized(store):
    provider = oidc_providers.save_oidc_provider(payload(), "provider-a")

    assert store.documents[0]["client_secret_ciphertext"] != "top-secret"
    assert provider["has_client_secret"] is True
    assert "client_secret" not in oidc_providers.serialize_oidc_provider(provider)
    decrypted = oidc_providers.get_oidc_provider("provider-a", decrypt_client_secret=True)
    assert decrypted["client_secret"] == "top-secret"


def test_update_preserves_stored_secret_when_blank(store):
    oidc_providers.save_oidc_provider(payload(), "provider-a")
    original = store.documents[0]["client_secret_ciphertext"]

    oidc_providers.save_oidc_provider(payload(client_secret="", display_name="Renamed"), "provider-a")

    assert store.documents[0]["client_secret_ciphertext"] == original
    assert store.documents[0]["display_name"] == "Renamed"


def test_enabled_connections_cannot_share_routing_domain(store):
    oidc_providers.save_oidc_provider(payload(), "provider-a")

    with pytest.raises(ValueError, match="already uses"):
        oidc_providers.save_oidc_provider(
            payload(issuer="https://other.example.com", allowed_domains=["example.com"]),
            "provider-b",
        )


def test_managed_and_legacy_connections_are_both_listed(store, monkeypatch):
    oidc_providers.save_oidc_provider(payload(enabled=False), "provider-a")
    monkeypatch.setattr(
        oidc_providers,
        "get_auth_settings",
        lambda **kwargs: {
            "oidc_issuer": "https://legacy.example.com",
            "oidc_enabled": True,
            "oidc_display_name": "Legacy SSO",
            "oidc_client_id": "legacy-client",
            "oidc_allowed_domains": ["legacy.example"],
        },
    )

    providers = oidc_providers.list_oidc_providers()
    assert {item["_id"] for item in providers} == {"provider-a", "legacy"}
    assert oidc_providers.public_oidc_providers() == [{"id": "legacy", "display_name": "Legacy SSO"}]


def test_enabled_connection_cannot_reuse_legacy_domain(store, monkeypatch):
    monkeypatch.setattr(
        oidc_providers,
        "get_auth_settings",
        lambda **kwargs: {
            "oidc_issuer": "https://legacy.example.com",
            "oidc_enabled": True,
            "oidc_client_id": "legacy-client",
            "oidc_allowed_domains": ["example.com"],
        },
    )

    with pytest.raises(ValueError, match="legacy OIDC provider"):
        oidc_providers.save_oidc_provider(payload(), "provider-a")
