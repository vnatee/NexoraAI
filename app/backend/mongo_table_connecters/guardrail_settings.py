from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.guardrails import GuardrailPolicy, merge_guardrail_policies
from mongo_table_connecters.mongo_connector import get_database

SYSTEM_SETTINGS_ID = "guardrails:system"
collection = get_database()["application_settings"]


def _settings_id(team_id: str | None) -> str:
    return f"guardrails:team:{team_id}" if team_id else SYSTEM_SETTINGS_ID


def get_guardrail_settings(team_id: str | None = None) -> dict[str, Any] | None:
    document = collection.find_one({"_id": _settings_id(team_id)})
    if not document:
        return None
    return dict(document.get("policy") or {})


def save_guardrail_settings(policy: object, team_id: str | None = None) -> dict[str, Any]:
    normalized = GuardrailPolicy.from_config(policy).serialize()
    now = datetime.now(timezone.utc)
    collection.update_one(
        {"_id": _settings_id(team_id)},
        {
            "$set": {"policy": normalized, "team_id": team_id, "updated_at": now},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return normalized


def effective_guardrail_policy(
    agent_policy: object,
    *,
    team_id: str | None,
) -> GuardrailPolicy:
    system_config = get_guardrail_settings()
    team_config = get_guardrail_settings(team_id) if team_id else None
    return merge_guardrail_policies(
        GuardrailPolicy.from_config(system_config) if system_config is not None else None,
        GuardrailPolicy.from_config(team_config) if team_config is not None else None,
        GuardrailPolicy.from_config(agent_policy),
    )
