from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
teams_collection = db["teams"]

def insert_team(name: str,data_group_id: list[str],agent_id: list[str],user_id: list[str],waiting_approve: list[object]):
    team_data = {
        "_id": str(uuid.uuid4()),         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "name": name,                  
        "data_group_id": data_group_id,                  
        "agent_id": agent_id,              
        "user_id": user_id,
        "waiting_approve": waiting_approve       
    }

    result = teams_collection.insert_one(team_data)
    return result

def get_team_by_id(team_id: str):
    team = teams_collection.find_one({"_id": team_id, "delete_at": None})
    return team

def get_all_teams():
    teams = list(teams_collection.find({"delete_at": None}))
    return teams

def get_team_by_user_id(user_id: str):
    teams = list(teams_collection.find({"user_id": user_id,"delete_at": None}))
    return teams

def update_team(team_id: str, name: str = None,data_group_id: list[str] = None,agent_id: list[str] = None,user_id: list[str] = None,waiting_approve: list[object] = None):
    update_data = {
        "update_at": datetime.utcnow()
    }
    if name is not None:
        update_data["name"] = name
    if data_group_id is not None:
        update_data["data_group_id"] = data_group_id
    if agent_id is not None:
        update_data["agent_id"] = agent_id
    if user_id is not None:
        update_data["user_id"] = user_id
    if waiting_approve is not None:
        update_data["waiting_approve"] = waiting_approve

    result = teams_collection.update_one(
        {"_id": team_id}, {"$set": update_data})
    return result.modified_count > 0

def delete_team_by_id(team_id: str):
    result = teams_collection.delete_one({"_id": team_id})
    return result

def soft_delete_team_by_id(team_id: str):
    result = teams_collection.update_one(
        {"_id": team_id},
        {"$set": {"delete_at": datetime.utcnow()}}
    )
    return result.modified_count > 0