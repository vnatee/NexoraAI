import pytest
from cryptography.fernet import Fernet

from mongo_table_connecters.mcp_servers import (
    decrypt_mcp_headers,
    normalize_mcp_server_payload,
    serialize_mcp_server,
)


def test_mcp_server_headers_are_encrypted_and_never_serialized(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    normalized = normalize_mcp_server_payload(
        {
            "name": "Datadog",
            "url": "https://mcp.example.test/mcp",
            "headers": {"Authorization": "Bearer secret"},
            "allowed_tools": ["query", "query"],
        }
    )
    document = {"_id": "mcp-1", **normalized}

    assert "secret" not in normalized["headers_ciphertext"]
    assert decrypt_mcp_headers(document) == {"Authorization": "Bearer secret"}
    serialized = serialize_mcp_server(document)
    assert serialized["has_headers"] is True
    assert "headers" not in serialized
    assert "headers_ciphertext" not in serialized
    assert serialized["allowed_tools"] == ["query"]
    assert serialized["category"] == "custom"


def test_mcp_server_update_keeps_existing_headers_when_blank(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    existing = normalize_mcp_server_payload(
        {
            "name": "DrawIO",
            "url": "https://mcp.example.test/mcp",
            "headers": {"X-Key": "secret"},
        }
    )

    updated = normalize_mcp_server_payload(
        {"name": "DrawIO 2", "url": "https://mcp.example.test/mcp"},
        existing=existing,
    )

    assert updated["headers_ciphertext"] == existing["headers_ciphertext"]


def test_datadog_preset_validates_endpoint_and_bearer_token(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    normalized = normalize_mcp_server_payload(
        {
            "name": "Datadog US1",
            "vendor": "datadog",
            "auth_type": "bearer",
            "url": "https://mcp.datadoghq.com/v1/mcp?toolsets=core,synthetics",
            "headers": {"Authorization": "Bearer datadog-secret"},
        }
    )

    assert normalized["vendor"] == "datadog"
    assert normalized["category"] == "observability"
    assert normalized["auth_type"] == "bearer"
    assert decrypt_mcp_headers(
        {"headers_ciphertext": normalized["headers_ciphertext"]}
    ) == {"Authorization": "Bearer datadog-secret"}


@pytest.mark.parametrize(
    ("url", "headers"),
    [
        ("https://example.com/v1/mcp", {"Authorization": "Bearer secret"}),
        ("https://mcp.datadoghq.com/old/mcp", {"Authorization": "Bearer secret"}),
        ("https://mcp.datadoghq.com/v1/mcp", {"Authorization": "secret"}),
    ],
)
def test_datadog_preset_rejects_unsafe_or_invalid_configuration(
    monkeypatch, url, headers
):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(ValueError):
        normalize_mcp_server_payload(
            {
                "name": "Datadog",
                "vendor": "datadog",
                "auth_type": "bearer",
                "url": url,
                "headers": headers,
            }
        )
