import uuid
from datetime import datetime

from mongo_table_connecters.mongo_connector import get_database

db = get_database()
database_binding_collection = db["database_bindings"]


def normalize_query_profile(profile: object) -> dict:
    if profile is None:
        profile = {}
    if not isinstance(profile, dict):
        raise ValueError("Database query profile must be an object")

    allowed_objects = profile.get("allowed_objects") or []
    if not isinstance(allowed_objects, list):
        raise ValueError("allowed_objects must be a list")
    normalized_objects = []
    for value in allowed_objects[:100]:
        item = str(value or "").strip()
        if item and item not in normalized_objects:
            normalized_objects.append(item)

    examples = profile.get("query_examples") or []
    if not isinstance(examples, list):
        raise ValueError("query_examples must be a list")
    normalized_examples = []
    for example in examples[:20]:
        if not isinstance(example, dict):
            raise ValueError("Each query example must be an object")
        question = str(example.get("question") or "").strip()
        query = str(example.get("query") or "").strip()
        if question and query:
            normalized_examples.append(
                {"question": question[:1000], "query": query[:8000]}
            )

    return {
        "business_context": str(profile.get("business_context") or "").strip()[:8000],
        "business_rules": str(profile.get("business_rules") or "").strip()[:12000],
        "glossary": str(profile.get("glossary") or "").strip()[:12000],
        "allowed_objects": normalized_objects,
        "query_examples": normalized_examples,
    }


def insert_database_binding(
    agent_id: str,
    integration_id: str,
    alias: str = None,
    trigger_keywords: list = None,
    enabled: bool = True,
    query_profile: dict = None,
):
    binding_id = str(uuid.uuid4())
    binding_data = {
        "_id": binding_id,
        "agent_id": agent_id,
        "integration_id": integration_id,
        "alias": alias,
        "trigger_keywords": trigger_keywords or [],
        "query_profile": normalize_query_profile(query_profile),
        "enabled": enabled,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "delete_at": None,
    }

    result = database_binding_collection.insert_one(binding_data)
    return result


def get_database_binding_by_id(binding_id: str):
    return database_binding_collection.find_one({"_id": binding_id})


def get_database_bindings_by_agent_id(agent_id: str):
    return list(database_binding_collection.find({"agent_id": agent_id}))


def get_enabled_database_bindings_by_agent_id(agent_id: str):
    return list(
        database_binding_collection.find(
            {"agent_id": agent_id, "enabled": True, "delete_at": None}
        )
    )


def get_all_database_bindings():
    return list(database_binding_collection.find({}))


def update_database_binding(
    binding_id: str,
    agent_id: str = None,
    integration_id: str = None,
    alias: str = None,
    trigger_keywords: list = None,
    enabled: bool = None,
    query_profile: dict = None,
):
    update_data = {"updated_at": datetime.utcnow()}

    if agent_id is not None:
        update_data["agent_id"] = agent_id
    if integration_id is not None:
        update_data["integration_id"] = integration_id
    if alias is not None:
        update_data["alias"] = alias
    if trigger_keywords is not None:
        update_data["trigger_keywords"] = trigger_keywords
    if enabled is not None:
        update_data["enabled"] = enabled
    if query_profile is not None:
        update_data["query_profile"] = normalize_query_profile(query_profile)

    result = database_binding_collection.update_one(
        {"_id": binding_id}, {"$set": update_data}
    )
    return result.modified_count > 0


def delete_database_binding_by_id(binding_id: str):
    result = database_binding_collection.delete_one({"_id": binding_id})
    return result
