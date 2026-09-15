import pytest
from cryptography.fernet import Fernet

from core.provider_secrets import decrypt_provider_secret, encrypt_provider_secret


def test_provider_secret_round_trip(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))

    encrypted = encrypt_provider_secret("provider-secret")

    assert encrypted is not None
    assert encrypted != "provider-secret"
    assert decrypt_provider_secret(encrypted) == "provider-secret"


def test_provider_secret_requires_master_key(monkeypatch):
    monkeypatch.delenv("APP_DATA_ENCRYPTION_KEY", raising=False)

    with pytest.raises(ValueError, match="APP_DATA_ENCRYPTION_KEY"):
        encrypt_provider_secret("provider-secret")


def test_empty_provider_secret_does_not_require_master_key(monkeypatch):
    monkeypatch.delenv("APP_DATA_ENCRYPTION_KEY", raising=False)

    assert encrypt_provider_secret(None) is None
    assert decrypt_provider_secret(None) is None
