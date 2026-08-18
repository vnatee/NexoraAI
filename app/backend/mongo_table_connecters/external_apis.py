from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
apis_collection = db["external_apis"]

def insert_apis(team_id: str,name: str,type: str,base_url: str,auth: object,endpoints: list[object]):
    apis_id = str(uuid.uuid4())
    apis_data = {
        "_id": apis_id,         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "team_id": team_id,                  
        "name": name,                  
        "type": type,
        "base_url": base_url,
        "auth": auth,
        "endpoints": endpoints        
    }

    result = apis_collection.insert_one(apis_data)
    return result,apis_id

def get_apis_by_id(apis_id: str):
    apis = apis_collection.find_one({"_id": apis_id, "delete_at": None})
    return apis

def get_apis_by_team_id_and_name(team_id: str,name: str):
    apis = apis_collection.find_one({"team_id": team_id,"name": name, "delete_at": None})
    return apis

def get_all_apis():
    apis = list(apis_collection.find({"delete_at": None}))
    return apis

def get_all_apis_by_team_id(team_id: str):
    apis = list(apis_collection.find({"team_id":team_id, "delete_at": None}))
    return apis

def update_apis(apis_id: str, team_id: str = None,name: str= None ,type: str= None ,base_url: str= None ,auth: object= None ,endpoints: list[object]= None):
    update_data = {
        "update_at": datetime.utcnow()
    }
    if team_id is not None:
        update_data["team_id"] = team_id
    if name is not None:
        update_data["name"] = name
    if type is not None:
        update_data["type"] = type
    if base_url is not None:
        update_data["base_url"] = base_url
    if auth is not None:
        update_data["auth"] = auth
    if endpoints is not None:
        update_data["endpoints"] = endpoints

    result = apis_collection.update_one(
        {"_id": apis_id}, {"$set": update_data})
    return result.modified_count > 0

def delete_apis_by_id(apis_id: str):
    result = apis_collection.delete_one({"_id": apis_id})
    return result

def soft_delete_apis_by_id(apis_id: str):
    result = apis_collection.update_one(
        {"_id": apis_id},
        {"$set": {"delete_at": datetime.utcnow()}}
    )
    return result.modified_count > 0
