from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
database_binding_collection = db["database_bindings"]

def insert_database_binding(agent_id: str, integration_id: str, alias: str = None, trigger_keywords: list = None, enabled: bool = True):
    binding_id = str(uuid.uuid4())
    binding_data = {
        "_id": binding_id,
        "agent_id": agent_id,
        "integration_id": integration_id,
        "alias": alias,
        "trigger_keywords": trigger_keywords or [],
        "enabled": enabled,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "delete_at": None
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

def update_database_binding(binding_id: str, agent_id: str = None, integration_id: str = None, alias: str = None, trigger_keywords: list = None, enabled: bool = None):
    update_data = {
        "updated_at": datetime.utcnow()
    }
    
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

    result = database_binding_collection.update_one(
        {"_id": binding_id}, {"$set": update_data}
    )
    return result.modified_count > 0

def delete_database_binding_by_id(binding_id: str):
    result = database_binding_collection.delete_one({"_id": binding_id})
    return result