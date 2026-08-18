from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
data_groups_collection = db["data_group"]

def insert_data_group(name: str,user_id: list[str]):
    data_group_id = str(uuid.uuid4())
    data_group_data = {
        "_id": data_group_id,         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "name": name,                  
        "user_id": user_id,                          
    }

    result = data_groups_collection.insert_one(data_group_data)
    return result,data_group_id

def get_data_group_by_id(data_group_id: str):
    data_group = data_groups_collection.find_one({"_id": data_group_id, "delete_at": None})
    return data_group

def get_all_data_groups():
    data_groups = list(data_groups_collection.find({"delete_at": None}))
    return data_groups

def get_all_data_groups_by_user_id(user_id: str):
    data_groups = list(data_groups_collection.find({"user_id": user_id,"delete_at": None}))
    return data_groups

def update_data_group(data_group_id: str, name: str = None,user_id: list[str] = None):
    update_data = {
        "update_at": datetime.utcnow()
    }
    if name is not None:
        update_data["name"] = name
    if user_id is not None:
        update_data["user_id"] = user_id

    result = data_groups_collection.update_one(
        {"_id": data_group_id}, {"$set": update_data})
    return result.modified_count > 0

def delete_data_group_by_id(data_group_id: str):
    result = data_groups_collection.delete_one({"_id": data_group_id})
    return result

def soft_delete_data_group_by_id(data_group_id: str):
    result = data_groups_collection.update_one(
        {"_id": data_group_id},
        {"$set": {"delete_at": datetime.utcnow()}}
    )
    return result.modified_count > 0
