import os

from cryptography.fernet import Fernet, InvalidToken


def _cipher() -> Fernet:
    key = os.getenv("APP_DATA_ENCRYPTION_KEY", "").strip()
    if not key:
        raise ValueError(
            "APP_DATA_ENCRYPTION_KEY is required before application secrets can be stored. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.encode("utf-8"))
    except (TypeError, ValueError) as error:
        raise ValueError("APP_DATA_ENCRYPTION_KEY is not a valid Fernet key") from error


def encrypt_provider_secret(secret: str | None) -> str | None:
    if not secret:
        return None
    return _cipher().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_provider_secret(encrypted_secret: str | None) -> str | None:
    if not encrypted_secret:
        return None
    try:
        return _cipher().decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")
    except InvalidToken as error:
        raise ValueError("Unable to decrypt provider API key with APP_DATA_ENCRYPTION_KEY") from error


def encrypt_secret(secret: str | None) -> str | None:
    """Encrypt application secrets; provider-specific names remain for compatibility."""
    return encrypt_provider_secret(secret)


def decrypt_secret(encrypted_secret: str | None) -> str | None:
    return decrypt_provider_secret(encrypted_secret)
