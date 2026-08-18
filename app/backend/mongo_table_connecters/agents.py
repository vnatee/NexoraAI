from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
agents_collection = db["agents"]

def insert_agent(agent_name: str,prompt: object,config: object):
    agent_id = str(uuid.uuid4())
    agent_data = {
        "_id": agent_id,         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "agent_name": agent_name,                  
        "prompt": prompt,                  
        "config": config        
    }

    result = agents_collection.insert_one(agent_data)
    return result,agent_id

def get_agent_by_id(agent_id: str):
    agent = agents_collection.find_one({"_id": agent_id, "delete_at": None})
    return agent

def get_all_agents():
    agents = list(agents_collection.find({"delete_at": None}))
    return agents


def update_agent(agent_id: str, agent_name: str = None,prompt: object = None,config: object = None):
    update_data = {
        "update_at": datetime.utcnow()
    }
    if agent_name is not None:
        update_data["agent_name"] = agent_name
    if prompt is not None:
        update_data["prompt"] = prompt
    if config is not None:
        update_data["config"] = config

    result = agents_collection.update_one(
        {"_id": agent_id}, {"$set": update_data})
    return result.modified_count > 0

def delete_agent_by_id(agent_id: str):
    result = agents_collection.delete_one({"_id": agent_id})
    return result

def soft_delete_agent_by_id(agent_id: str):
    result = agents_collection.update_one(
        {"_id": agent_id},
        {"$set": {"delete_at": datetime.utcnow()}}
    )
    return result.modified_count > 0
