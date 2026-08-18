from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
roles_collection = db["roles"]

def insert_role(name: str,permission_id: list[str],team_id: str):
    role_data = {
        "_id": str(uuid.uuid4()),         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "name": name,                  
        "permission_id": permission_id,                  
        "team_id": team_id         
    }

    result = roles_collection.insert_one(role_data)
    return result

def get_role_by_id(role_id: str):
    role = roles_collection.find_one({"_id": role_id, "delete_at": None})
    return role

def get_all_roles():
    roles = list(roles_collection.find({"delete_at": None}))
    return roles

def get_all_roles_by_team(team_id):
    roles = list(roles_collection.find({"team_id": team_id,"delete_at": None}))
    return roles

def update_role(role_id: str, name: str = None,permission_id: list[str] = None,team_id: str = None):
    update_data = {
        "update_at": datetime.utcnow()
    }
    if name is not None:
        update_data["name"] = name
    if permission_id is not None:
        update_data["permission_id"] = permission_id
    if team_id is not None:
        update_data["team_id"] = team_id

    result = roles_collection.update_one(
        {"_id": role_id}, {"$set": update_data})
    return result.modified_count > 0

def delete_role_by_id(role_id: str):
    result = roles_collection.delete_one({"_id": role_id})
    return result

def soft_delete_role_by_id(role_id: str):
    result = roles_collection.update_one(
        {"_id": role_id},
        {"$set": {"delete_at": datetime.utcnow()}}
    )
    return result.modified_count > 0
