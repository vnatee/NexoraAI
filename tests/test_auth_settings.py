from copy import deepcopy

from cryptography.fernet import Fernet

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
