import re
from typing import Any

from agent_runtime.tools import ToolRegistry, ToolSpec
from email_connectors import list_messages, send_message
from mongo_table_connecters.mail_bindings import list_mail_bindings
from mongo_table_connecters.mail_connections import (
    decrypt_mail_secrets,
    get_mail_connection,
)

_TEMPLATE_VARIABLE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*}}")


def _template_variables(*templates: str) -> list[str]:
    return list(dict.fromkeys(match.group(1) for value in templates for match in _TEMPLATE_VARIABLE.finditer(value)))


def _render_template(template: str, variables: dict[str, Any], field: str) -> str:
    required = _template_variables(template)
    missing = [name for name in required if name not in variables]
    if missing:
        raise ValueError(f"Missing {field} template variables: {', '.join(missing)}")
    return _TEMPLATE_VARIABLE.sub(lambda match: str(variables[match.group(1)]), template)


def _mail_send_required_fields(binding: dict[str, Any]) -> list[str]:
    required: list[str] = []
    if not binding.get("default_to"):
        required.append("to")
    subject = str(binding.get("subject") or "")
    body = str(binding.get("body") or "")
    if not subject:
        required.append("subject")
    if not body:
        required.append("body")
    if _template_variables(subject, body):
        required.append("variables")
    return required


def _validate_recipients(binding: dict[str, Any], recipients: list[str]) -> None:
    if len(recipients) > int(binding.get("max_recipients") or 10):
        raise ValueError("Recipient count exceeds this Agent mail binding policy")
    domains = set(binding.get("allowed_recipient_domains") or [])
    if domains:
        invalid = [value for value in recipients if "@" not in value or value.rsplit("@", 1)[1].lower() not in domains]
        if invalid:
            raise ValueError(f"Recipient domain is not allowed: {', '.join(invalid)}")


def register_mail_tools(registry: ToolRegistry, agent_id: str) -> None:
    for binding in list_mail_bindings(agent_id, enabled_only=True):
        connection = get_mail_connection(binding.get("email_id", ""))
        if not connection or connection.get("enabled") is False:
            continue
        secrets = decrypt_mail_secrets(connection)
        alias = str(connection.get("name") or connection.get("email_address") or "mail")
        suffix = str(binding.get("_id") or connection.get("_id"))[:8]
        permissions = set(binding.get("permissions") or ["read", "send"])
        if "read" in permissions:
            async def read_mail(arguments, context, _connection=connection, _secrets=secrets):
                return {
                    "messages": await list_messages(
                        _connection,
                        _secrets,
                        query=str(arguments.get("query") or ""),
                        limit=int(arguments.get("limit") or 10),
                    )
                }

            registry.register(
                ToolSpec(
                    name=f"mail_{alias}_search_{suffix}",
                    description=f"Read or search messages in the assigned {connection['provider']} mailbox '{alias}'.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Provider search text; blank lists recent mail."},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                        },
                        "additionalProperties": False,
                    },
                    handler=read_mail,
                    source=f"mail:{connection['_id']}",
                    risk_level="external",
                )
            )
        if "send" in permissions:
            configured_subject = str(binding.get("subject") or "")
            configured_body = str(binding.get("body") or "")
            variable_names = _template_variables(configured_subject, configured_body)
            default_to = list(binding.get("default_to") or [])
            required_fields = _mail_send_required_fields(binding)

            async def send_mail(arguments, context, _connection=connection, _secrets=secrets, _binding=binding):
                to = list(arguments.get("to") or _binding.get("default_to") or [])
                cc = list(arguments.get("cc") or _binding.get("default_cc") or [])
                bcc = list(arguments.get("bcc") or _binding.get("default_bcc") or [])
                recipients = to + cc + bcc
                if not to:
                    raise ValueError("At least one To recipient is required")
                _validate_recipients(_binding, recipients)
                variables = arguments.get("variables") or {}
                if not isinstance(variables, dict):
                    raise ValueError("variables must be an object")
                subject_template = str(_binding.get("subject") or "")
                body_template = str(_binding.get("body") or "")
                subject = (
                    _render_template(subject_template, variables, "subject")
                    if subject_template
                    else str(arguments.get("subject") or "")
                )
                body = (
                    _render_template(body_template, variables, "body")
                    if body_template
                    else str(arguments.get("body") or "")
                )
                if not subject or not body:
                    raise ValueError("Subject and body are required when no configured template is available")
                return await send_message(
                    _connection,
                    _secrets,
                    to=to,
                    cc=cc,
                    bcc=bcc,
                    subject=subject[:1000],
                    body=body[:50000],
                    is_html=bool(arguments.get("is_html", _binding.get("is_html", False))),
                )

            registry.register(
                ToolSpec(
                    name=f"mail_{alias}_send_{suffix}",
                    description=(
                        f"Send mail through the assigned {connection['provider']} mailbox '{alias}'. "
                        "This is a write action. Use only when the user explicitly requests sending mail. "
                        + (
                            f"Default To recipients are configured: {', '.join(default_to)}. "
                            if default_to
                            else "No Default To recipient is configured; you must supply the to field. "
                        )
                        + (
                            f"A managed template is configured; supply these variables: {', '.join(variable_names)}. "
                            f"Subject template: {configured_subject[:500]!r}. Body template: {configured_body[:1500]!r}."
                            if configured_subject or configured_body
                            else "No managed template is configured; generate and supply subject and body."
                        )
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "to": {"type": "array", "items": {"type": "string"}},
                            "cc": {"type": "array", "items": {"type": "string"}},
                            "bcc": {"type": "array", "items": {"type": "string"}},
                            "subject": {"type": "string"},
                            "body": {"type": "string"},
                            "variables": {
                                "type": "object",
                                "description": "Values used to replace {{variable}} placeholders in the managed template.",
                                "additionalProperties": {"type": "string"},
                            },
                            "is_html": {"type": "boolean"},
                        },
                        "required": required_fields,
                        "additionalProperties": False,
                    },
                    handler=send_mail,
                    source=f"mail:{connection['_id']}",
                    timeout_seconds=75,
                    risk_level="write",
                )
            )
