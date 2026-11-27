import pytest
from cryptography.fernet import Fernet

from agent_runtime.adapters.mail import (
    _mail_send_required_fields,
    _playground_mail_mode,
    _render_template,
    _template_variables,
    _validate_recipients,
    register_mail_tools,
)
from agent_runtime.tools import ToolRegistry, ToolRuntimeContext
from mongo_table_connecters.mail_bindings import normalize_mail_binding
from mongo_table_connecters.mail_connections import (
    decrypt_mail_secrets,
    normalize_mail_connection,
    serialize_mail_connection,
)
from mongo_table_connecters.user_mail_accounts import (
    materialize_user_mail_connection,
    normalize_user_mail_account,
    serialize_user_mail_account,
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


def test_playground_mail_mode_defaults_to_test_and_allows_explicit_live():
    test_context = ToolRuntimeContext(
        agent_id="draft-1",
        auth_claims={"application_user_id": "user-1"},
        metadata={"execution_context": "playground"},
    )
    live_context = ToolRuntimeContext(
        agent_id="draft-1",
        auth_claims={"application_user_id": "user-1"},
        metadata={"execution_context": "playground", "playground_mail_mode": "live"},
    )
    runtime_context = ToolRuntimeContext(
        agent_id="agent-1", auth_claims={"application_user_id": "user-1"}
    )

    assert _playground_mail_mode(test_context) == "test"
    assert _playground_mail_mode(live_context) == "live"
    assert _playground_mail_mode(runtime_context) is None


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


@pytest.mark.asyncio
async def test_playground_test_mode_simulates_mail_and_live_mode_calls_provider(
    monkeypatch,
):
    binding = {
        "_id": "binding-1",
        "agent_id": "draft-1",
        "email_id": "profile-1",
        "enabled": True,
        "permissions": ["send"],
        "max_recipients": 10,
    }
    profile = {
        "_id": "profile-1",
        "team_id": "team-1",
        "name": "Operations",
        "provider": "generic",
        "account_mode": "shared",
        "enabled": True,
    }
    provider_calls = []

    async def provider_send(*args, **kwargs):
        provider_calls.append((args, kwargs))
        return {"sent": True, "message_id": "provider-message"}

    monkeypatch.setattr(
        "agent_runtime.adapters.mail.list_mail_bindings",
        lambda *_args, **_kwargs: [binding],
    )
    monkeypatch.setattr(
        "agent_runtime.adapters.mail.get_mail_connection", lambda *_args: profile
    )
    monkeypatch.setattr(
        "agent_runtime.adapters.mail.decrypt_mail_secrets",
        lambda *_args: {"password": "not-returned"},
    )
    monkeypatch.setattr("agent_runtime.adapters.mail.send_message", provider_send)

    def registry(mode):
        result = ToolRegistry(
            ToolRuntimeContext(
                agent_id="draft-1",
                team_id="team-1",
                auth_claims={"application_user_id": "user-1"},
                metadata={
                    "execution_context": "playground",
                    "playground_mail_mode": mode,
                },
            )
        )
        register_mail_tools(result, "draft-1")
        return result

    arguments = {
        "to": ["one@example.com", "two@example.com"],
        "cc": ["copy@example.com"],
        "bcc": ["audit@example.com"],
        "subject": "Test subject",
        "body": "Test body",
    }
    test_registry = registry("test")
    send_tool = next(spec.name for spec in test_registry.specs() if spec.risk_level == "write")
    simulated = await test_registry.execute(send_tool, arguments)

    assert '"simulated": true' in simulated
    assert '"to_count": 2' in simulated
    assert provider_calls == []

    live_registry = registry("live")
    live_send_tool = next(spec.name for spec in live_registry.specs() if spec.risk_level == "write")
    live = await live_registry.execute(live_send_tool, arguments)

    assert '"sent": true' in live
    assert len(provider_calls) == 1
    assert provider_calls[0][1]["cc"] == ["copy@example.com"]
    assert provider_calls[0][1]["bcc"] == ["audit@example.com"]


def test_personal_generic_profile_keeps_user_credentials_out_of_team_profile(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    profile = normalize_mail_connection({
        "team_id": "team-1",
        "name": "Personal company mail",
        "provider": "generic",
        "account_mode": "personal",
        "public_config": {
            "receive_host": "imap.example.com",
            "receive_port": 993,
            "receive_security": "ssl",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_security": "starttls",
        },
    })
    assert profile["account_mode"] == "personal"
    assert profile["email_address"] == ""
    assert profile["secrets_ciphertext"] is None

    account = normalize_user_mail_account(
        {
            "email_address": "alice@example.com",
            "public_config": {"username": "alice@example.com"},
            "secrets": {"password": "personal-secret"},
        },
        profile={"_id": "profile-1", **profile},
    )
    assert "personal-secret" not in account["secrets_ciphertext"]
    assert account["verification_status"] == "pending"

    connection, secrets = materialize_user_mail_connection(
        {"_id": "profile-1", **profile},
        {"_id": "account-1", **account},
    )
    assert connection["email_address"] == "alice@example.com"
    assert connection["public_config"]["username"] == "alice@example.com"
    assert secrets == {"password": "personal-secret"}
    public = serialize_user_mail_account({"_id": "account-1", **account})
    assert public["has_credentials"] is True
    assert "secrets_ciphertext" not in public


def test_personal_microsoft_mailbox_is_derived_from_managed_identity(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    profile = {
        "_id": "profile-1",
        "team_id": "team-1",
        "provider": "microsoft365",
        "account_mode": "personal",
    }
    account = normalize_user_mail_account(
        {"email_address": "someone-else@example.com"},
        profile=profile,
        managed_email="alice@example.com",
    )
    assert account["email_address"] == "alice@example.com"
    assert account["secrets_ciphertext"] is None


def test_shared_mail_connection_remains_the_backward_compatible_default(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    value = normalize_mail_connection({
        "team_id": "team-1",
        "name": "Support",
        "provider": "generic",
        "email_address": "support@example.com",
        "public_config": {
            "receive_host": "imap.example.com",
            "receive_port": 993,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
        },
        "secrets": {"password": "secret"},
    })
    assert value["account_mode"] == "shared"


def test_personal_mail_tools_resolve_only_the_signed_in_users_verified_account(monkeypatch):
    binding = {
        "_id": "binding-1",
        "agent_id": "agent-1",
        "email_id": "profile-1",
        "enabled": True,
        "permissions": ["read", "send"],
    }
    profile = {
        "_id": "profile-1",
        "team_id": "team-1",
        "name": "Personal mail",
        "provider": "generic",
        "account_mode": "personal",
        "connection_revision": 1,
        "enabled": True,
    }
    account = {
        "_id": "account-1",
        "profile_id": "profile-1",
        "team_id": "team-1",
        "user_id": "user-1",
        "email_address": "alice@example.com",
        "verification_status": "verified",
        "verified_profile_revision": 1,
        "enabled": True,
    }
    requested_users = []
    monkeypatch.setattr("agent_runtime.adapters.mail.list_mail_bindings", lambda *_args, **_kwargs: [binding])
    monkeypatch.setattr("agent_runtime.adapters.mail.get_mail_connection", lambda *_args: profile)

    def account_for(user_id, _profile_id):
        requested_users.append(user_id)
        return account if user_id == "user-1" else None

    monkeypatch.setattr("agent_runtime.adapters.mail.get_user_mail_account", account_for)
    monkeypatch.setattr(
        "agent_runtime.adapters.mail.materialize_user_mail_connection",
        lambda current_profile, current_account: (
            {**current_profile, "email_address": current_account["email_address"]},
            {"password": "not-returned"},
        ),
    )

    own_registry = ToolRegistry(ToolRuntimeContext(
        agent_id="agent-1",
        team_id="team-1",
        auth_claims={"application_user_id": "user-1"},
    ))
    register_mail_tools(own_registry, "agent-1")
    assert len(own_registry.specs()) == 2

    other_registry = ToolRegistry(ToolRuntimeContext(
        agent_id="agent-1",
        team_id="team-1",
        auth_claims={"application_user_id": "user-2"},
    ))
    register_mail_tools(other_registry, "agent-1")
    assert other_registry.specs() == []

    profile["connection_revision"] = 2
    stale_registry = ToolRegistry(ToolRuntimeContext(
        agent_id="agent-1",
        team_id="team-1",
        auth_claims={"application_user_id": "user-1"},
    ))
    register_mail_tools(stale_registry, "agent-1")
    assert stale_registry.specs() == []
    assert requested_users == ["user-1", "user-2", "user-1"]
