from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
external_db_collection = db["external_databases"]

def insert_external_database(team_id: str, name: str, db_type: str, host: str, port: int, database: str, username: str, password: str = None):
    db_id = str(uuid.uuid4())
    db_data = {
        "_id": db_id,
        "team_id": team_id,
        "name": name,
        "db_type": db_type,
        "host": host,
        "port": port,
        "database": database,
        "username": username,
        "password": password,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "delete_at": None
    }

    result = external_db_collection.insert_one(db_data)
    return result

def get_external_database_by_id(db_id: str):
    return external_db_collection.find_one({"_id": db_id})

def get_external_databases_by_ids(db_ids: list[str]):
    if not db_ids:
        return []
    return list(external_db_collection.find({"_id": {"$in": db_ids}, "delete_at": None}))

def get_external_databases_by_team_id(team_id: str):
    return list(external_db_collection.find({"team_id": team_id}))

def get_all_external_databases():
    return list(external_db_collection.find({}))

def update_external_database(db_id: str, team_id: str = None, name: str = None, db_type: str = None, host: str = None, port: int = None, database: str = None, username: str = None, password: str = None): 
    update_data = {
        "updated_at": datetime.utcnow()
    }
    
    if team_id is not None:
        update_data["team_id"] = team_id
    if name is not None:
        update_data["name"] = name
    if db_type is not None:
        update_data["db_type"] = db_type
    if host is not None:
        update_data["host"] = host
    if port is not None:
        update_data["port"] = port
    if database is not None:
        update_data["database"] = database
    if username is not None:
        update_data["username"] = username
    if password is not None:
        update_data["password"] = password

    result = external_db_collection.update_one(
        {"_id": db_id}, {"$set": update_data}
    )
    return result.modified_count > 0

def delete_external_database_by_id(db_id: str):
    result = external_db_collection.delete_one({"_id": db_id})
    return result
