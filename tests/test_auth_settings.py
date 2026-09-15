from copy import deepcopy

from cryptography.fernet import Fernet
import pytest

from mongo_table_connecters import auth_settings


class MemoryCollection:
    def __init__(self):
        self.document = None

    def find_one(self, query):
        if self.document and self.document.get("_id") == query.get("_id"):
            return deepcopy(self.document)
        return None

    def update_one(self, query, update, upsert=False):
        self.document = self.document or {"_id": query["_id"]}
        for key, value in (update.get("$setOnInsert") or {}).items():
            self.document.setdefault(key, deepcopy(value))
        self.document.update(deepcopy(update.get("$set") or {}))


def test_managed_auth_settings_encrypt_secret_and_never_serialize_it(monkeypatch):
    collection = MemoryCollection()
    monkeypatch.setattr(auth_settings, "collection", collection)
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())

    saved = auth_settings.save_auth_settings(
        {
            "entra_enabled": True,
            "tenant_id": "tenant",
            "server_app_id": "server",
            "client_app_id": "client",
            "client_secret": "top-secret",
        }
    )

    assert saved["has_client_secret"] is True
    assert "top-secret" not in str(collection.document)
    assert auth_settings.get_auth_settings(decrypt_client_secret=True)["client_secret"] == "top-secret"
    assert "client_secret" not in auth_settings.serialize_auth_settings(saved)


def test_updating_ids_preserves_existing_secret(monkeypatch):
    collection = MemoryCollection()
    monkeypatch.setattr(auth_settings, "collection", collection)
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    auth_settings.save_auth_settings(
        {
            "entra_enabled": True,
            "tenant_id": "tenant-1",
            "server_app_id": "server",
            "client_app_id": "client",
            "client_secret": "top-secret",
        }
    )

    auth_settings.save_auth_settings(
        {
            "entra_enabled": True,
            "tenant_id": "tenant-2",
            "server_app_id": "server",
            "client_app_id": "client",
        }
    )

    loaded = auth_settings.get_auth_settings(decrypt_client_secret=True)
    assert loaded["tenant_id"] == "tenant-2"
    assert loaded["client_secret"] == "top-secret"


def test_oidc_settings_encrypt_secret_and_require_jit_domain(monkeypatch):
    collection = MemoryCollection()
    monkeypatch.setattr(auth_settings, "collection", collection)
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())

    saved = auth_settings.save_auth_settings(
        {
            "entra_enabled": False,
            "oidc_enabled": True,
            "oidc_display_name": "Company SSO",
            "oidc_issuer": "https://id.example.com/realms/company/",
            "oidc_client_id": "nexora",
            "oidc_client_secret": "oidc-secret",
            "oidc_jit_enabled": True,
            "oidc_allowed_domains": "Example.com, subsidiary.example",
        }
    )

    assert saved["oidc_has_client_secret"] is True
    assert saved["oidc_issuer"] == "https://id.example.com/realms/company"
    assert saved["oidc_allowed_domains"] == ["example.com", "subsidiary.example"]
    assert "oidc-secret" not in str(collection.document)
    assert auth_settings.get_auth_settings(decrypt_client_secret=True)["oidc_client_secret"] == "oidc-secret"
    assert "oidc_client_secret" not in auth_settings.serialize_auth_settings(saved)

    with pytest.raises(ValueError, match="allowed email domain"):
        auth_settings.save_auth_settings(
            {
                "entra_enabled": False,
                "oidc_enabled": True,
                "oidc_issuer": "https://id.example.com",
                "oidc_client_id": "nexora",
                "oidc_jit_enabled": True,
                "oidc_allowed_domains": [],
            }
        )


def test_oidc_settings_reject_insecure_issuer(monkeypatch):
    collection = MemoryCollection()
    monkeypatch.setattr(auth_settings, "collection", collection)
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())

    with pytest.raises(ValueError, match="must use HTTPS"):
        auth_settings.save_auth_settings(
            {
                "entra_enabled": False,
                "oidc_enabled": True,
                "oidc_issuer": "http://id.example.com",
                "oidc_client_id": "nexora",
                "oidc_client_secret": "secret",
            }
        )
