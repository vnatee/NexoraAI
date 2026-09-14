from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from mongo_table_connecters.mongo_connector import get_database


db = get_database()
items_collection = db["agent_catalog_items"]
versions_collection = db["agent_catalog_versions"]
installations_collection = db["agent_catalog_installations"]
audit_collection = db["agent_catalog_audit_events"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_agent_catalog_indexes() -> None:
    items_collection.create_index([("status", 1), ("visibility", 1), ("publisher_team_id", 1)])
    items_collection.create_index([("source_agent_id", 1)], unique=True)
    versions_collection.create_index([("catalog_item_id", 1), ("version", 1)], unique=True)
    installations_collection.create_index(
        [("catalog_item_id", 1), ("version", 1), ("team_id", 1)], unique=True
    )
    installations_collection.create_index([("team_id", 1), ("status", 1)])
    audit_collection.create_index([("created_at", -1)])


def sanitized_agent_snapshot(agent: dict[str, Any]) -> dict[str, Any]:
    """Return a portable snapshot without tenant/team integration bindings."""
    config = copy.deepcopy(agent.get("config") or {})
    tool_settings = config.get("tool_settings")
    if not isinstance(tool_settings, dict):
        tool_settings = {}
        config["tool_settings"] = tool_settings
    tool_settings["mcp_server_ids"] = []
    tool_settings["mcp_tool_allowlists"] = {}
    tool_settings["subagent_ids"] = []
    return {
        "agent_name": str(agent.get("agent_name") or "").strip(),
        "prompt": copy.deepcopy(agent.get("prompt") or {}),
        "config": config,
    }


def snapshot_requirements(snapshot: dict[str, Any]) -> dict[str, Any]:
    config = snapshot.get("config") or {}
    tools = config.get("tool_settings") or {}
    return {
        "llm_profile_id": str(config.get("llm_profile_id") or "system"),
        "runtime": str(config.get("runtime") or config.get("runtime_mode") or "legacy"),
        "uses_knowledge": str(tools.get("knowledge_search") or "disabled") != "disabled",
        "declared_tools": sorted(
            key
            for key in (
                "external_database",
                "rest_integrations",
                "mail",
                "business_documents",
                "messaging",
                "mcp",
                "subagents",
            )
            if tools.get(key) is True
        ),
    }


def publish_agent(
    *,
    agent: dict[str, Any],
    publisher_team_id: str,
    created_by: str,
    summary: str,
    usage_instructions: str,
    tags: list[str],
    category: str,
    visibility: str,
    allowed_team_ids: list[str],
    publisher_type: str = "team",
) -> tuple[dict[str, Any], int]:
    now = _now()
    source_agent_id = str(agent.get("_id") or "")
    item = items_collection.find_one({"source_agent_id": source_agent_id, "delete_at": None})
    if item:
        catalog_item_id = str(item["_id"])
        version = int(item.get("latest_version") or 0) + 1
        items_collection.update_one(
            {"_id": catalog_item_id},
            {"$set": {
                "name": str(agent.get("agent_name") or "").strip(),
                "summary": summary,
                "usage_instructions": usage_instructions,
                "tags": tags,
                "category": category,
                "visibility": visibility,
                "allowed_team_ids": allowed_team_ids,
                "status": "published",
                "latest_version": version,
                "updated_at": now,
            }},
        )
    else:
        catalog_item_id = str(uuid.uuid4())
        version = 1
        item = {
            "_id": catalog_item_id,
            "name": str(agent.get("agent_name") or "").strip(),
            "summary": summary,
            "usage_instructions": usage_instructions,
            "tags": tags,
            "category": category,
            "publisher_type": publisher_type,
            "publisher_team_id": publisher_team_id,
            "source_agent_id": source_agent_id,
            "visibility": visibility,
            "allowed_team_ids": allowed_team_ids,
            "status": "published",
            "latest_version": version,
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
            "delete_at": None,
        }
        items_collection.insert_one(item)

    snapshot = sanitized_agent_snapshot(agent)
    versions_collection.insert_one({
        "_id": str(uuid.uuid4()),
        "catalog_item_id": catalog_item_id,
        "version": version,
        "source_agent_id": source_agent_id,
        "snapshot": snapshot,
        "requirements": snapshot_requirements(snapshot),
        "created_by": created_by,
        "created_at": now,
    })
    return items_collection.find_one({"_id": catalog_item_id}), version


def list_catalog_items(*, team_id: str | None = None, include_unpublished: bool = False) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"delete_at": None}
    if not include_unpublished:
        query["status"] = "published"
    items = list(items_collection.find(query).sort([("updated_at", -1), ("name", 1)]))
    if not team_id:
        return items
    return [item for item in items if is_visible_to_team(item, team_id)]


def is_visible_to_team(item: dict[str, Any], team_id: str) -> bool:
    if item.get("status") != "published":
        return False
    visibility = str(item.get("visibility") or "team")
    return (
        visibility == "all_teams"
        or (visibility == "team" and str(item.get("publisher_team_id") or "") == team_id)
        or (visibility == "selected_teams" and team_id in {str(value) for value in item.get("allowed_team_ids") or []})
    )


def get_catalog_item(catalog_item_id: str) -> dict[str, Any] | None:
    return items_collection.find_one({"_id": catalog_item_id, "delete_at": None})


def get_catalog_version(catalog_item_id: str, version: int) -> dict[str, Any] | None:
    return versions_collection.find_one({"catalog_item_id": catalog_item_id, "version": version})


def get_installation(catalog_item_id: str, version: int, team_id: str) -> dict[str, Any] | None:
    return installations_collection.find_one({
        "catalog_item_id": catalog_item_id,
        "version": version,
        "team_id": team_id,
        "status": "active",
    })


def get_active_installation(catalog_item_id: str, team_id: str) -> dict[str, Any] | None:
    return installations_collection.find_one({
        "catalog_item_id": catalog_item_id,
        "team_id": team_id,
        "status": "active",
    })


def record_installation(*, catalog_item_id: str, version: int, team_id: str, agent_id: str, created_by: str) -> dict[str, Any]:
    now = _now()
    installation = {
        "_id": str(uuid.uuid4()),
        "catalog_item_id": catalog_item_id,
        "version": version,
        "team_id": team_id,
        "installed_agent_id": agent_id,
        "status": "active",
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }
    installations_collection.insert_one(installation)
    return installation


def installations_for_team(team_id: str) -> list[dict[str, Any]]:
    return list(installations_collection.find({"team_id": team_id, "status": "active"}))


def update_catalog_item(catalog_item_id: str, changes: dict[str, Any]) -> bool:
    changes = {**changes, "updated_at": _now()}
    return items_collection.update_one(
        {"_id": catalog_item_id, "delete_at": None}, {"$set": changes}
    ).matched_count > 0


def insert_catalog_audit_event(
    event: str,
    *,
    actor_id: str,
    catalog_item_id: str,
    team_id: str | None = None,
    version: int | None = None,
) -> None:
    audit_collection.insert_one({
        "_id": str(uuid.uuid4()),
        "event": event,
        "actor_id": actor_id,
        "catalog_item_id": catalog_item_id,
        "team_id": team_id,
        "version": version,
        "created_at": _now(),
    })
