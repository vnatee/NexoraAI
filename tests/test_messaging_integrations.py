from cryptography.fernet import Fernet

from agent_runtime.adapters import messaging
from agent_runtime.tools import ToolRegistry, ToolRuntimeContext
from mongo_table_connecters.messaging_connections import (
    decrypt_messaging_secrets,
    normalize_messaging_connection,
    serialize_messaging_connection,
)


def test_messaging_token_is_encrypted(monkeypatch):
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    normalized = normalize_messaging_connection({
        "team_id": "team", "name": "Ops Slack", "provider": "slack",
        "public_config": {"default_target": "C123"},
        "secrets": {"bot_token": "xoxb-secret"},
    })
    document = {"_id": "message-1", **normalized}
    assert "xoxb-secret" not in normalized["secrets_ciphertext"]
    assert decrypt_messaging_secrets(document) == {"bot_token": "xoxb-secret"}
    assert "secrets_ciphertext" not in serialize_messaging_connection(document)


def test_line_tool_requires_target_when_no_default(monkeypatch):
    monkeypatch.setattr(messaging, "list_messaging_bindings", lambda *_args, **_kwargs: [{"_id": "bind-1", "connection_id": "line-1", "enabled": True}])
    monkeypatch.setattr(messaging, "get_messaging_connection", lambda *_args: {"_id": "line-1", "name": "LINE Alerts", "provider": "line", "enabled": True, "public_config": {}})
    monkeypatch.setattr(messaging, "decrypt_messaging_secrets", lambda *_args: {"channel_access_token": "secret"})
    registry = ToolRegistry(ToolRuntimeContext(agent_id="agent", auth_claims={}))
    messaging.register_messaging_tools(registry, "agent")
    assert registry.specs()[0].input_schema["required"] == ["target", "text"]


def test_managed_message_template_requires_variables(monkeypatch):
    monkeypatch.setattr(messaging, "list_messaging_bindings", lambda *_args, **_kwargs: [{"_id": "bind-1", "connection_id": "slack-1", "default_target": "C123", "message_template": "{{service}} is {{status}}"}])
    monkeypatch.setattr(messaging, "get_messaging_connection", lambda *_args: {"_id": "slack-1", "name": "Slack", "provider": "slack", "enabled": True, "public_config": {}})
    monkeypatch.setattr(messaging, "decrypt_messaging_secrets", lambda *_args: {"bot_token": "secret"})
    registry = ToolRegistry(ToolRuntimeContext(agent_id="agent", auth_claims={}))
    messaging.register_messaging_tools(registry, "agent")
    assert registry.specs()[0].input_schema["required"] == ["variables"]
