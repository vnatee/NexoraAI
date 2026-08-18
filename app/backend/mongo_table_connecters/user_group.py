from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
user_groups_collection = db["user_group"]

def insert_user_group(name: str,permission_id: list[str],user_id: list[str]):
    user_group_data = {
        "_id": str(uuid.uuid4()),         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "name": name,                  
        "permission_id": permission_id,                  
        "user_id": user_id       
    }

    result = user_groups_collection.insert_one(user_group_data)
    return result

def get_user_group_by_id(user_group_id: str):
    user_group = user_groups_collection.find_one({"_id": user_group_id, "delete_at": None})
    return user_group

def get_all_user_groups():
    user_groups = list(user_groups_collection.find({"delete_at": None}))
    return user_groups


def update_user_group(user_group_id: str, name: str = None,permission_id: str = None,user_id: str = None):
    update_data = {
        "update_at": datetime.utcnow()
    }
    if name is not None:
        update_data["name"] = name
    if permission_id is not None:
        update_data["permission_id"] = permission_id
    if user_id is not None:
        update_data["user_id"] = user_id

    result = user_groups_collection.update_one(
        {"_id": user_group_id}, {"$set": update_data})
    return result.modified_count > 0

def delete_user_group_by_id(user_group_id: str):
    result = user_groups_collection.delete_one({"_id": user_group_id})
    return result

def soft_delete_user_group_by_id(user_group_id: str):
    result = user_groups_collection.update_one(
        {"_id": user_group_id},
        {"$set": {"delete_at": datetime.utcnow()}}
    )
    return result.modified_count > 0
