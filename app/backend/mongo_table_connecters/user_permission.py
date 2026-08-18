from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
user_permissions_collection = db["user_permission"]

def insert_user_permission(team_id: str,user_id: str,permission_id: list[str]):
    user_permission_data = {
        "_id": str(uuid.uuid4()),         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "team_id": team_id,                  
        "user_id": user_id,                  
        "permission_id": permission_id        
    }

    result = user_permissions_collection.insert_one(user_permission_data)
    return result

def get_user_permission_by_id(user_permission_id: str):
    user_permission = user_permissions_collection.find_one({"_id": user_permission_id, "delete_at": None})
    return user_permission

def get_all_user_permissions():
    user_permissions = list(user_permissions_collection.find({"delete_at": None}))
    return user_permissions

def get_user_permission_by_user_id(user_id: str):
    user_permissions = list(user_permissions_collection.find({"user_id": user_id,"delete_at": None}))
    return user_permissions

def get_user_permission_by_team_id(team_id: str):
    user_permissions = list(user_permissions_collection.find({"team_id": team_id,"delete_at": None}))
    return user_permissions

def get_user_permission_by_user_team_id(user_id: str,team_id: str):
    user_permissions = list(user_permissions_collection.find({"user_id": user_id,"team_id": team_id,"delete_at": None}))
    return user_permissions

def update_user_permission(user_permission_id: str, team_id: str = None,user_id: str = None,permission_id: list[str] = None):
    update_data = {
        "update_at": datetime.utcnow()
    }
    if team_id is not None:
        update_data["team_id"] = team_id
    if user_id is not None:
        update_data["user_id"] = user_id
    if permission_id is not None:
        update_data["permission_id"] = permission_id

    result = user_permissions_collection.update_one(
        {"_id": user_permission_id}, {"$set": update_data})
    return result.modified_count > 0

def delete_user_permission_by_id(user_permission_id: str):
    result = user_permissions_collection.delete_one({"_id": user_permission_id})
    return result

def soft_delete_user_permission_by_id(user_permission_id: str):
    result = user_permissions_collection.update_one(
        {"_id": user_permission_id},
        {"$set": {"delete_at": datetime.utcnow()}}
    )
    return result.modified_count > 0
