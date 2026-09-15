from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
permissions_collection = db["permissions"]

def insert_permission(name: str,type: str):
    permission_data = {
        "_id": str(uuid.uuid4()),         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "name": name,
        "type": type        
    }

    result = permissions_collection.insert_one(permission_data)
    return result

def get_permission_by_id(permission_id: str):
    permission = permissions_collection.find_one({"_id": permission_id, "delete_at": None})
    return permission

def get_permission_by_name(name: str):
    permission = permissions_collection.find_one({"name": name, "delete_at": None})
    return permission

def get_all_permissions():
    permissions = list(permissions_collection.find({"delete_at": None}))
    return permissions


def update_permission(permission_id: str, name: str = None, type: str = None):
    update_data = {
        "update_at": datetime.utcnow()
    }
    if name is not None:
        update_data["name"] = name
    if type is not None:
        update_data["type"] = type

    result = permissions_collection.update_one(
        {"_id": permission_id}, {"$set": update_data})
    return result.modified_count > 0

def delete_permission_by_id(permission_id: str):
    result = permissions_collection.delete_one({"_id": permission_id})
    return result

def soft_delete_permission_by_id(permission_id: str):
    result = permissions_collection.update_one(
        {"_id": permission_id},
        {"$set": {"delete_at": datetime.utcnow()}}
    )
    return result.modified_count > 0
