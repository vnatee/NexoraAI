from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
limit_size_configs_collection = db["limit_size_config"]

def insert_limit_size_config(size_limit_personal: int,size_limit_group: int,size_limit_global: int):
    limit_size_config_data = {
        "_id": str(uuid.uuid4()),         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "size_limit_personal": size_limit_personal,                  
        "size_limit_group": size_limit_group,                  
        "size_limit_global": size_limit_global,                      
    }

    result = limit_size_configs_collection.insert_one(limit_size_config_data)
    return result

def get_limit_size_config_by_id(limit_size_config_id: str):
    limit_size_config = limit_size_configs_collection.find_one({"_id": limit_size_config_id, "delete_at": None})
    return limit_size_config

def get_all_limit_size_configs():
    limit_size_configs = list(limit_size_configs_collection.find({"delete_at": None}))
    return limit_size_configs


def update_limit_size_config(limit_size_config_id: str, size_limit_personal: int = None,size_limit_group: int = None,size_limit_global: int = None):
    update_data = {
        "update_at": datetime.utcnow()
    }
    if size_limit_personal is not None:
        update_data["size_limit_personal"] = size_limit_personal
    if size_limit_group is not None:
        update_data["size_limit_group"] = size_limit_group
    if size_limit_global is not None:
        update_data["size_limit_global"] = size_limit_global

    result = limit_size_configs_collection.update_one(
        {"_id": limit_size_config_id}, {"$set": update_data})
    return result.modified_count > 0

def delete_limit_size_config_by_id(limit_size_config_id: str):
    result = limit_size_configs_collection.delete_one({"_id": limit_size_config_id})
    return result

def soft_delete_limit_size_config_by_id(limit_size_config_id: str):
    result = limit_size_configs_collection.update_one(
        {"_id": limit_size_config_id},
        {"$set": {"delete_at": datetime.utcnow()}}
    )
    return result.modified_count > 0
