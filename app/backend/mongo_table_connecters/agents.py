import copy
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


def create_or_resume_agent_revision(
    active_agent: dict,
    *,
    created_by: str,
    expires_at: datetime,
) -> tuple[dict, bool]:
    """Create an isolated editable copy of an active Agent and all native bindings."""
    active_id = str(active_agent.get("_id") or "")
    existing = agents_collection.find_one(
        {
            "revision_of": active_id,
            "lifecycle_status": "draft",
            "delete_at": None,
            "draft_expires_at": {"$gt": datetime.now(timezone.utc)},
        }
    )
    if existing:
        agents_collection.update_one(
            {"_id": existing["_id"]},
            {"$set": {"draft_expires_at": expires_at, "update_at": datetime.utcnow()}},
        )
        existing["draft_expires_at"] = expires_at
        return existing, False

    revision_id = str(uuid.uuid4())
    now = datetime.utcnow()
    revision = {
        "_id": revision_id,
        "create_at": now,
        "update_at": now,
        "delete_at": None,
        "agent_name": str(active_agent.get("agent_name") or ""),
        "prompt": copy.deepcopy(active_agent.get("prompt") or {}),
        "config": copy.deepcopy(active_agent.get("config") or {}),
        "lifecycle_status": "draft",
        "draft_kind": "revision",
        "revision_of": active_id,
        "revision_base_updated_at": active_agent.get("update_at"),
        "draft_expires_at": expires_at,
        "created_by": created_by,
    }
    agents_collection.insert_one(revision)
    try:
        for collection_name in AGENT_BINDING_COLLECTIONS:
            collection = db[collection_name]
            source_documents = list(
                collection.find({"agent_id": active_id, "delete_at": None})
            )
            if not source_documents:
                continue
            clones = []
            for source in source_documents:
                clone = copy.deepcopy(source)
                clone["_id"] = str(uuid.uuid4())
                clone["agent_id"] = revision_id
                if "create_at" in clone:
                    clone["create_at"] = now
                if "created_at" in clone:
                    clone["created_at"] = datetime.now(timezone.utc)
                if "update_at" in clone:
                    clone["update_at"] = now
                if "updated_at" in clone:
                    clone["updated_at"] = datetime.now(timezone.utc)
                clones.append(clone)
            collection.insert_many(clones)
    except Exception:
        for collection_name in AGENT_BINDING_COLLECTIONS:
            db[collection_name].delete_many({"agent_id": revision_id})
        agents_collection.delete_one({"_id": revision_id})
        raise
    return revision, True


def publish_agent_revision(revision: dict, active_agent: dict) -> dict:
    """Replace an active Agent from its private revision while retaining the active ID."""
    revision_id = str(revision.get("_id") or "")
    active_id = str(active_agent.get("_id") or "")
    if str(revision.get("revision_of") or "") != active_id:
        raise ValueError("Revision does not belong to the active Agent")
    base_updated_at = revision.get("revision_base_updated_at")
    lock_id = str(uuid.uuid4())
    lock_filter = {
        "_id": active_id,
        "delete_at": None,
        "lifecycle_status": "active",
        "update_at": base_updated_at,
        "publish_lock": {"$exists": False},
    }
    locked = agents_collection.update_one(
        lock_filter,
        {"$set": {"publish_lock": lock_id, "publish_started_at": datetime.now(timezone.utc)}},
    )
    if locked.modified_count != 1:
        raise ValueError(
            "The active Agent changed after this revision was created. Discard it and start a new revision."
        )

    snapshots: dict[str, tuple[list[dict], list[dict]]] = {}
    try:
        for collection_name in AGENT_BINDING_COLLECTIONS:
            collection = db[collection_name]
            active_bindings = list(collection.find({"agent_id": active_id}))
            revision_bindings = list(collection.find({"agent_id": revision_id}))
            snapshots[collection_name] = (
                copy.deepcopy(active_bindings),
                copy.deepcopy(revision_bindings),
            )
            collection.delete_many({"agent_id": {"$in": [active_id, revision_id]}})
            promoted = []
            for document in revision_bindings:
                promoted_document = copy.deepcopy(document)
                promoted_document["agent_id"] = active_id
                promoted.append(promoted_document)
            if promoted:
                collection.insert_many(promoted)

        now = datetime.utcnow()
        updated = agents_collection.update_one(
            {"_id": active_id, "publish_lock": lock_id},
            {
                "$set": {
                    "agent_name": revision.get("agent_name"),
                    "prompt": copy.deepcopy(revision.get("prompt") or {}),
                    "config": copy.deepcopy(revision.get("config") or {}),
                    "update_at": now,
                    "last_revision_id": revision_id,
                },
                "$unset": {"publish_lock": "", "publish_started_at": ""},
            },
        )
        if updated.modified_count != 1:
            raise RuntimeError("Active Agent revision publish lock was lost")
    except Exception:
        for collection_name, (active_bindings, revision_bindings) in snapshots.items():
            collection = db[collection_name]
            collection.delete_many({"agent_id": {"$in": [active_id, revision_id]}})
            if active_bindings:
                collection.insert_many(active_bindings)
            if revision_bindings:
                collection.insert_many(revision_bindings)
        agents_collection.update_one(
            {"_id": active_id, "publish_lock": lock_id},
            {"$unset": {"publish_lock": "", "publish_started_at": ""}},
        )
        raise

    agents_collection.delete_one({"_id": revision_id})
    return agents_collection.find_one({"_id": active_id, "delete_at": None}) or {
        **active_agent,
        "agent_name": revision.get("agent_name"),
        "prompt": revision.get("prompt") or {},
        "config": revision.get("config") or {},
        "update_at": now,
    }

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
    agents_collection.create_index(
        [("revision_of", 1), ("lifecycle_status", 1)],
        name="agent_revision_lookup",
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
    revision_ids = [
        str(document["_id"])
        for document in agents_collection.find(
            {"revision_of": agent_id, "delete_at": None}, {"_id": 1}
        )
    ]
    target_ids = [agent_id, *revision_ids]
    counts: dict[str, int] = {}
    for collection_name in AGENT_BINDING_COLLECTIONS:
        result = db[collection_name].delete_many({"agent_id": {"$in": target_ids}})
        counts[collection_name] = int(result.deleted_count)
    db["teams"].update_many(
        {"agent_id": {"$in": target_ids}},
        {"$pull": {"agent_id": {"$in": target_ids}}},
    )
    db["agents"].update_many(
        {"config.tool_settings.subagent_ids": {"$in": target_ids}},
        {"$pull": {"config.tool_settings.subagent_ids": {"$in": target_ids}}},
    )
    deleted = agents_collection.delete_many({"_id": {"$in": target_ids}})
    counts["agents"] = int(deleted.deleted_count)
    if deleted.deleted_count:
        db["agent_lifecycle_audit"].insert_one(
            {
                "_id": str(uuid.uuid4()),
                "event_type": "agent_deleted",
                "agent_id": agent_id,
                "revision_count": len(revision_ids),
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
