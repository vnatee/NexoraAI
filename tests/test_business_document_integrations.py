import pytest
from cryptography.fernet import Fernet

from agent_runtime.adapters.business_documents import register_business_document_tools
from agent_runtime.tools import ToolRegistry, ToolRuntimeContext
from business_document_connectors import _office_bytes
from core.attachment_extraction import extract_attachment_chunks
from mongo_table_connecters.business_document_bindings import normalize_business_document_binding
from mongo_table_connecters.business_document_connections import (
    decrypt_business_document_secrets,
    normalize_business_document_connection,
    serialize_business_document_connection,
)


def test_microsoft_document_credentials_are_encrypted(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    normalized = normalize_business_document_connection({
        "team_id": "team-1",
        "name": "Finance SharePoint",
        "provider": "microsoft365",
        "public_config": {"tenant_id": "tenant", "client_id": "client", "drive_id": "drive"},
        "secrets": {"client_secret": "secret-value"},
    })
    document = {"_id": "documents-1", **normalized}
    assert "secret-value" not in normalized["secrets_ciphertext"]
    assert decrypt_business_document_secrets(document) == {"client_secret": "secret-value"}
    assert serialize_business_document_connection(document)["has_credentials"] is True
    assert "secrets_ciphertext" not in serialize_business_document_connection(document)


def test_google_workspace_requires_refresh_token(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(ValueError, match="refresh_token"):
        normalize_business_document_connection({
            "name": "Google Drive",
            "provider": "google_workspace",
            "public_config": {"client_id": "client"},
            "secrets": {"client_secret": "secret"},
        })


def test_create_permission_requires_a_valid_capability():
    assert normalize_business_document_binding({
        "agent_id": "agent", "connection_id": "documents", "permissions": ["read", "create", "invalid"]
    })["permissions"] == ["read", "create"]
    with pytest.raises(ValueError, match="At least one"):
        normalize_business_document_binding({"agent_id": "agent", "connection_id": "documents", "permissions": []})


@pytest.mark.parametrize(
    ("kind", "title", "content", "expected"),
    [
        ("word", "Quarterly report", "Revenue increased.", "Revenue increased."),
        ("excel", "Pipeline", "Account,Value\nContoso,100", "Contoso"),
        ("powerpoint", "Review", "Executive summary\nRevenue increased.", "Revenue increased."),
    ],
)
def test_generated_office_documents_are_valid_and_extractable(kind, title, content, expected):
    filename, content_type, payload = _office_bytes(kind, title, content)
    chunks = extract_attachment_chunks(filename=filename, content_type=content_type, content=payload)
    assert expected in "\n".join(chunk.text for chunk in chunks)


def test_document_adapter_registers_read_and_write_tools(monkeypatch):
    connection = {
        "_id": "documents-1", "name": "Business Docs", "provider": "microsoft365",
        "operation_mode": "read_write", "enabled": True,
    }
    monkeypatch.setattr(
        "agent_runtime.adapters.business_documents.list_business_document_bindings",
        lambda *_args, **_kwargs: [{"_id": "binding-1", "connection_id": "documents-1", "permissions": ["read", "create"]}],
    )
    monkeypatch.setattr(
        "agent_runtime.adapters.business_documents.get_business_document_connection",
        lambda _connection_id: connection,
    )
    monkeypatch.setattr(
        "agent_runtime.adapters.business_documents.decrypt_business_document_secrets",
        lambda _connection: {"client_secret": "secret"},
    )
    registry = ToolRegistry(ToolRuntimeContext(agent_id="agent-1", auth_claims={}))
    register_business_document_tools(registry, "agent-1")
    specs = registry.specs()
    assert len(specs) == 3
    assert {spec.risk_level for spec in specs} == {"external", "write"}
    assert any("create" in spec.name for spec in specs)
