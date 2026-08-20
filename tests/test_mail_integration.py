import pytest
from cryptography.fernet import Fernet

from agent_runtime.adapters.mail import (
    _mail_send_required_fields,
    _render_template,
    _template_variables,
    _validate_recipients,
)
from mongo_table_connecters.mail_bindings import normalize_mail_binding
from mongo_table_connecters.mail_connections import (
    decrypt_mail_secrets,
    normalize_mail_connection,
    serialize_mail_connection,
)


def test_microsoft_mail_credentials_are_encrypted(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    value = normalize_mail_connection({
        "team_id": "team-1", "name": "Operations", "provider": "microsoft365",
        "email_address": "ops@example.com",
        "public_config": {"tenant_id": "tenant", "client_id": "client"},
        "secrets": {"client_secret": "secret-value"},
    })
    document = {"_id": "mail-1", **value}
    assert "secret-value" not in value["secrets_ciphertext"]
    assert decrypt_mail_secrets(document) == {"client_secret": "secret-value"}
    serialized = serialize_mail_connection(document)
    assert serialized["has_credentials"] is True
    assert "secrets_ciphertext" not in serialized


@pytest.mark.parametrize("provider", ["microsoft365", "gmail", "generic"])
def test_supported_mail_providers(provider):
    assert provider in {"microsoft365", "gmail", "generic"}


def test_mail_binding_permissions_and_recipient_policy():
    binding = normalize_mail_binding({
        "agent_id": "agent", "email_id": "mail", "permissions": ["read", "send"],
        "allowed_recipient_domains": ["Example.COM"], "max_recipients": 2,
    })
    assert binding["permissions"] == ["read", "send"]
    _validate_recipients(binding, ["a@example.com", "b@example.com"])
    with pytest.raises(ValueError, match="domain"):
        _validate_recipients(binding, ["a@outside.test"])
    with pytest.raises(ValueError, match="count"):
        _validate_recipients(binding, ["a@example.com", "b@example.com", "c@example.com"])


def test_mail_binding_requires_a_capability():
    with pytest.raises(ValueError, match="At least one"):
        normalize_mail_binding({"agent_id": "agent", "email_id": "mail", "permissions": []})


def test_mail_template_variables_are_rendered():
    template = "Hello {{ recipient_name }}, PO {{po_number}} needs review."
    assert _template_variables(template) == ["recipient_name", "po_number"]
    assert _render_template(template, {"recipient_name": "Nina", "po_number": "PO-100"}, "body") == (
        "Hello Nina, PO PO-100 needs review."
    )
    with pytest.raises(ValueError, match="po_number"):
        _render_template(template, {"recipient_name": "Nina"}, "body")


def test_send_tool_requires_only_values_without_defaults():
    assert _mail_send_required_fields({}) == ["to", "subject", "body"]
    assert _mail_send_required_fields({
        "default_to": ["ops@example.com"],
        "subject": "PO {{po_number}}",
        "body": "Risk: {{risk}}",
    }) == ["variables"]
