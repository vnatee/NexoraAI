import uuid
from datetime import datetime, timezone

from mongo_table_connecters.mongo_connector import get_database

db = get_database()
agents_collection = db["agents"]

AGENT_BINDING_COLLECTIONS = (
    "agent_bindings",
    "database_bindings",
    "mail_bindings",
    "business_document_bindings",
    "messaging_bindings",
    "chart_bindings",
)


def insert_agent(
    agent_name: str,
    prompt: object,
    config: object,
    *,
    lifecycle_status: str = "active",
    draft_expires_at: datetime | None = None,
    created_by: str | None = None,
):
    agent_id = str(uuid.uuid4())
    agent_data = {
        "_id": agent_id,         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "agent_name": agent_name,                  
        "prompt": prompt,                  
        "config": config,
        "lifecycle_status": lifecycle_status,
        "draft_expires_at": draft_expires_at,
        "created_by": created_by,
    }

    result = agents_collection.insert_one(agent_data)
    return result,agent_id

def get_agent_by_id(agent_id: str):
    agent = agents_collection.find_one({"_id": agent_id, "delete_at": None})
    return agent

def get_all_agents():
    agents = list(agents_collection.find({"delete_at": None}))
    return agents


def update_agent(
    agent_id: str,
    agent_name: str = None,
    prompt: object = None,
    config: object = None,
    *,
    draft_expires_at: datetime | None = None,
):
    update_data = {
        "update_at": datetime.utcnow()
    }
    if agent_name is not None:
        update_data["agent_name"] = agent_name
    if prompt is not None:
        update_data["prompt"] = prompt
    if config is not None:
        update_data["config"] = config
    if draft_expires_at is not None:
        update_data["draft_expires_at"] = draft_expires_at

    result = agents_collection.update_one(
        {"_id": agent_id}, {"$set": update_data})
    return result.modified_count > 0

def delete_agent_by_id(agent_id: str):
    result = agents_collection.delete_one({"_id": agent_id})
    return result


def activate_agent_by_id(agent_id: str, now: datetime | None = None):
    current = now or datetime.now(timezone.utc)
    result = agents_collection.update_one(
        {
            "_id": agent_id,
            "delete_at": None,
            "lifecycle_status": "draft",
            "draft_expires_at": {"$gt": current},
        },
        {
            "$set": {
                "lifecycle_status": "active",
                "draft_expires_at": None,
                "update_at": datetime.utcnow(),
            }
        },
    )
    return result.modified_count > 0


def is_active_agent(agent: dict | None) -> bool:
    # Records created before draft support have no lifecycle field and remain active.
    return bool(agent) and str(agent.get("lifecycle_status") or "active") == "active"


def is_expired_agent_draft(agent: dict | None, now: datetime | None = None) -> bool:
    if not agent or str(agent.get("lifecycle_status") or "active") != "draft":
        return False
    expires_at = agent.get("draft_expires_at")
    if not isinstance(expires_at, datetime):
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return expires_at <= current


def ensure_agent_indexes() -> None:
    agents_collection.create_index(
        [("lifecycle_status", 1), ("draft_expires_at", 1)],
        name="agent_draft_cleanup",
    )
    db["agent_lifecycle_audit"].create_index(
        [("created_at", -1)],
        name="agent_lifecycle_audit_created_at",
    )


def list_expired_agent_draft_ids(now: datetime | None = None, *, limit: int = 100) -> list[str]:
    current = now or datetime.now(timezone.utc)
    documents = agents_collection.find(
        {
            "delete_at": None,
            "lifecycle_status": "draft",
            "draft_expires_at": {"$lte": current},
        },
        {"_id": 1},
    ).limit(max(1, min(limit, 500)))
    return [str(document["_id"]) for document in documents]


def delete_agent_cascade(agent_id: str, *, reason: str, actor_id: str | None = None) -> dict[str, int]:
    """Hard-delete an Agent draft/live instance and its private binding records."""
    counts: dict[str, int] = {}
    for collection_name in AGENT_BINDING_COLLECTIONS:
        result = db[collection_name].delete_many({"agent_id": agent_id})
        counts[collection_name] = int(result.deleted_count)
    db["teams"].update_many({"agent_id": agent_id}, {"$pull": {"agent_id": agent_id}})
    db["agents"].update_many(
        {"config.tool_settings.subagent_ids": agent_id},
        {"$pull": {"config.tool_settings.subagent_ids": agent_id}},
    )
    deleted = agents_collection.delete_one({"_id": agent_id})
    counts["agents"] = int(deleted.deleted_count)
    if deleted.deleted_count:
        db["agent_lifecycle_audit"].insert_one(
            {
                "_id": str(uuid.uuid4()),
                "event_type": "agent_deleted",
                "agent_id": agent_id,
                "actor_id": actor_id,
                "reason": reason,
                "deleted_counts": counts,
                "created_at": datetime.now(timezone.utc),
            }
        )
    return counts

def soft_delete_agent_by_id(agent_id: str):
    result = agents_collection.update_one(
        {"_id": agent_id},
        {"$set": {"delete_at": datetime.utcnow()}}
    )
    return result.modified_count > 0
