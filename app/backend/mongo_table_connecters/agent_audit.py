from datetime import datetime, timedelta, timezone
from typing import Any

from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["agent_audit_events"]


def insert_agent_audit_event(event: dict[str, Any]) -> None:
    collection.insert_one(event)


def list_agent_audit_events(
    *,
    agent_id: str | None = None,
    run_id: str | None = None,
    event_type: str | None = None,
    status: str | None = None,
    hours: int = 24,
    limit: int = 200,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {
        "created_at": {
            "$gte": datetime.now(timezone.utc)
            - timedelta(hours=max(1, min(hours, 720)))
        }
    }
    if agent_id:
        query["agent_id"] = agent_id
    if run_id:
        query["run_id"] = run_id
    if event_type:
        query["event_type"] = event_type
    if status:
        query["status"] = status
    return list(
        collection.find(query).sort("created_at", -1).limit(max(1, min(limit, 1000)))
    )
