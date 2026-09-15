import re

from agent_runtime.tools import ToolRegistry, ToolSpec
from messaging_connectors import send_messaging_message
from mongo_table_connecters.messaging_bindings import list_messaging_bindings
from mongo_table_connecters.messaging_connections import (
    decrypt_messaging_secrets,
    get_messaging_connection,
)

_VARIABLE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*}}")


def register_messaging_tools(registry: ToolRegistry, agent_id: str) -> None:
    for binding in list_messaging_bindings(agent_id, enabled_only=True):
        connection = get_messaging_connection(binding.get("connection_id", ""))
        if not connection or connection.get("enabled") is False: continue
        secrets = decrypt_messaging_secrets(connection)
        template = str(binding.get("message_template") or "")
        variables = list(dict.fromkeys(match.group(1) for match in _VARIABLE.finditer(template)))
        default_target = str(binding.get("default_target") or (connection.get("public_config") or {}).get("default_target") or "")

        async def send_message(arguments, context, _connection=connection, _secrets=secrets, _template=template, _target=default_target):
            target = str(arguments.get("target") or _target)
            if _connection["provider"] != "discord" and not target:
                raise ValueError("A target is required for this messaging provider")
            values = arguments.get("variables") or {}
            if _template:
                missing = [name for name in dict.fromkeys(m.group(1) for m in _VARIABLE.finditer(_template)) if name not in values]
                if missing: raise ValueError(f"Missing message template variables: {', '.join(missing)}")
                text = _VARIABLE.sub(lambda match: str(values[match.group(1)]), _template)
            else:
                text = str(arguments.get("text") or "")
            if not text: raise ValueError("Message text is required")
            return await send_messaging_message(_connection, _secrets, target=target, text=text)

        required = []
        if connection["provider"] != "discord" and not default_target: required.append("target")
        required.append("variables" if variables else "text")
        registry.register(ToolSpec(
            name=f"message_{connection['provider']}_{connection.get('name')}_{str(binding.get('_id'))[:8]}",
            description=f"Send a message through {connection['provider']} connection '{connection.get('name')}'. " +
                (f"Default target: {default_target}. " if default_target else "Supply the destination target. ") +
                (f"Use managed template variables: {', '.join(variables)}. Template: {template[:1500]!r}" if template else "Generate and supply message text."),
            input_schema={"type": "object", "properties": {
                "target": {"type": "string", "description": "LINE user/group/room ID or Slack channel ID/name."},
                "text": {"type": "string"},
                "variables": {"type": "object", "additionalProperties": {"type": "string"}},
            }, "required": required, "additionalProperties": False},
            handler=send_message, source=f"messaging:{connection['_id']}", timeout_seconds=45, risk_level="write"))
