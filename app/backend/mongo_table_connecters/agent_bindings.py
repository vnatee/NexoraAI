from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
agent_bindings_collection = db["agent_bindings"]

def insert_agent_binding(agent_id: str,integration_id: str,integration_type: str,endpoint_name: str,trigger_keywords: object,async_bool: bool,enabled: bool,request_fields: list[object],response_fields: list[object]):
    agent_binding_id = str(uuid.uuid4())
    agent_binding_data = {
        "_id": agent_binding_id,         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "agent_id": agent_id,                  
        "integration_id": integration_id,                  
        "integration_type": integration_type,
        "endpoint_name": endpoint_name,
        "trigger_keywords": trigger_keywords,
        "async": async_bool,
        "enabled": enabled,
        "request_fields": request_fields,
        "response_fields": response_fields        
    }

    result = agent_bindings_collection.insert_one(agent_binding_data)
    return result,agent_binding_id

def get_agent_binding_by_id(agent_binding_id: str):
    agent_binding = agent_bindings_collection.find_one({"_id": agent_binding_id, "delete_at": None})
    return agent_binding

def get_agent_binding_by_apisid_and_endpointname(api_id: str,endname:str):
    agent_binding = agent_bindings_collection.find_one({"integration_id": api_id,"endpoint_name": endname, "delete_at": None})
    return agent_binding

def get_all_agent_bindings():
    agent_bindings = list(agent_bindings_collection.find({"delete_at": None}))
    return agent_bindings

def get_all_agent_bindings_by_agent_id(agent_id: str):
    agent_bindings = list(agent_bindings_collection.find({"agent_id": agent_id,"delete_at": None}))
    return agent_bindings

def update_agent_binding(agent_binding_id: str, agent_id: str = None,integration_id: str = None,integration_type: str = None,endpoint_name: str = None,trigger_keywords: object = None,async_bool: bool = None,enabled: bool = None,request_fields: list[object] = None,response_fields: list[object] = None):
    update_data = {
        "update_at": datetime.utcnow()
    }
    if agent_id is not None:
        update_data["agent_id"] = agent_id
    if integration_id is not None:
        update_data["integration_id"] = integration_id
    if integration_type is not None:
        update_data["integration_type"] = integration_type
    if endpoint_name is not None:
        update_data["endpoint_name"] = endpoint_name
    if trigger_keywords is not None:
        update_data["trigger_keywords"] = trigger_keywords
    if async_bool is not None:
        update_data["async"] = async_bool
    if enabled is not None:
        update_data["enabled"] = enabled
    if request_fields is not None:
        update_data["request_fields"] = request_fields
    if response_fields is not None:
        update_data["response_fields"] = response_fields

    result = agent_bindings_collection.update_one(
        {"_id": agent_binding_id}, {"$set": update_data})
    return result.modified_count > 0

def delete_agent_binding_by_id(agent_binding_id: str):
    result = agent_bindings_collection.delete_one({"_id": agent_binding_id})
    return result

def soft_delete_agent_binding_by_id(agent_binding_id: str):
    result = agent_bindings_collection.update_one(
        {"_id": agent_binding_id},
        {"$set": {"delete_at": datetime.utcnow()}}
    )
    return result.modified_count > 0
