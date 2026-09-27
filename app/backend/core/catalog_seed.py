from __future__ import annotations

import argparse
import copy
import json
from typing import Any

from core.catalog_templates import (
    DATADOG_OPERATIONS_SOURCE_ID,
    HR_EMPLOYEE_SERVICES_SOURCE_ID,
    datadog_operations_analyst_template,
    hr_employee_services_advisor_template,
)
from core.model_profiles import managed_profile_id
from mongo_table_connecters.agent_catalog import (
    get_catalog_version,
    insert_catalog_audit_event,
    items_collection,
    publish_agent,
    sanitized_agent_snapshot,
)
from mongo_table_connecters.llm_providers import list_llm_providers
from mongo_table_connecters.mongo_connector import get_database


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _is_current(existing: dict[str, Any], template: dict[str, Any]) -> bool:
    version = get_catalog_version(str(existing.get("_id") or ""), int(existing.get("latest_version") or 1)) or {}
    metadata = {
        key: existing.get(key)
        for key in ("summary", "usage_instructions", "tags", "category", "visibility", "allowed_team_ids", "status")
    }
    expected_metadata = {
        "summary": template["summary"],
        "usage_instructions": template["usage_instructions"],
        "tags": template["tags"],
        "category": template["category"],
        "visibility": template["visibility"],
        "allowed_team_ids": template["allowed_team_ids"],
        "status": "published",
    }
    return (
        _canonical(metadata) == _canonical(expected_metadata)
        and _canonical(version.get("snapshot") or {}) == _canonical(sanitized_agent_snapshot(template["agent"]))
    )


def select_tool_profile_id(providers: list[dict[str, Any]]) -> str:
    """Prefer a tested managed cloud profile, with the System profile as fallback."""
    priorities = {"azure_openai": 0, "openai": 1, "openai_compatible": 2}
    candidates: list[tuple[int, int, str, str]] = []
    for provider in providers:
        if provider.get("delete_at") is not None or provider.get("enabled", True) is not True:
            continue
        provider_type = str(provider.get("provider") or "")
        for model in provider.get("models") or []:
            if model.get("supports_tools", True) is False:
                continue
            capability = str(model.get("tool_capability_status") or "unknown")
            if capability == "unsupported":
                continue
            candidates.append((
                priorities.get(provider_type, 99),
                0 if capability == "supported" else 1,
                str(provider.get("_id") or ""),
                str(model.get("id") or ""),
            ))
    candidates = [item for item in candidates if item[2] and item[3]]
    if not candidates:
        return "system"
    _, _, provider_id, model_id = min(candidates)
    return managed_profile_id(provider_id, model_id)


def _seed_template(template: dict[str, Any], *, source_id: str, apply: bool) -> tuple[str, int]:
    existing = items_collection.find_one({
        "source_agent_id": source_id,
        "delete_at": None,
    })
    if existing and _is_current(existing, template):
        return "already-current", int(existing.get("latest_version") or 1)
    if not apply:
        return ("would-update" if existing else "would-create"), int((existing or {}).get("latest_version") or 0) + 1

    actor = get_database()["users"].find_one(
        {"is_sys_admin": True, "delete_at": None},
        {"_id": 1},
    ) or {"_id": "system"}
    item, version = publish_agent(
        agent=copy.deepcopy(template["agent"]),
        publisher_team_id="",
        created_by=str(actor.get("_id") or "system"),
        summary=template["summary"],
        usage_instructions=template["usage_instructions"],
        tags=template["tags"],
        category=template["category"],
        visibility=template["visibility"],
        allowed_team_ids=template["allowed_team_ids"],
        publisher_type=template["publisher_type"],
    )
    insert_catalog_audit_event(
        "system_template_seeded" if version == 1 else "system_template_updated",
        actor_id=str(actor.get("_id") or "system"),
        catalog_item_id=str(item.get("_id") or ""),
        version=version,
    )
    return ("created" if version == 1 else "updated"), version


def seed_datadog_operations_analyst(*, apply: bool) -> tuple[str, int]:
    template = datadog_operations_analyst_template(
        llm_profile_id=select_tool_profile_id(list_llm_providers())
    )
    return _seed_template(template, source_id=DATADOG_OPERATIONS_SOURCE_ID, apply=apply)


def seed_hr_employee_services_advisor(*, apply: bool) -> tuple[str, int]:
    template = hr_employee_services_advisor_template(
        llm_profile_id=select_tool_profile_id(list_llm_providers())
    )
    return _seed_template(template, source_id=HR_EMPLOYEE_SERVICES_SOURCE_ID, apply=apply)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the built-in NexoraAI Agent Catalog templates.")
    parser.add_argument("--apply", action="store_true", help="Write templates to the configured MongoDB database.")
    args = parser.parse_args()
    templates = (
        ("Datadog Operations Analyst", seed_datadog_operations_analyst),
        ("HR Employee Services Advisor", seed_hr_employee_services_advisor),
    )
    for name, seed_template in templates:
        status, version = seed_template(apply=args.apply)
        print(f"{name}: {status} (version {version})")


if __name__ == "__main__":
    main()
