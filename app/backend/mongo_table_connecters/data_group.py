import uuid
from datetime import datetime

from mongo_table_connecters.mongo_connector import get_database

db = get_database()
data_groups_collection = db["data_group"]

EXPOSURE_INTERNAL = "internal"
EXPOSURE_EXTERNAL = "external"
EXTERNAL_PUBLICATION_STATUSES = {"draft", "published", "retired"}

def insert_data_group(name: str,user_id: list[str], access_mode: str = "team"):
    data_group_id = str(uuid.uuid4())
    data_group_data = {
        "_id": data_group_id,         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "name": name,                  
        "user_id": user_id,
        "access_mode": access_mode,
        "exposure": EXPOSURE_INTERNAL,
        "publication_status": "not_applicable",
        "publication_version": 0,
        "published_at": None,
        "published_by": None,
        "publication_history": [],
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

def update_data_group(data_group_id: str, name: str = None,user_id: list[str] = None, access_mode: str = None):
    update_data = {
        "update_at": datetime.utcnow()
    }
    if name is not None:
        update_data["name"] = name
    if user_id is not None:
        update_data["user_id"] = user_id
    if access_mode is not None:
        update_data["access_mode"] = access_mode

    result = data_groups_collection.update_one(
        {"_id": data_group_id}, {"$set": update_data})
    return result.modified_count > 0


def update_data_group_publication(
    data_group_id: str,
    *,
    exposure: str,
    publication_status: str,
    actor_id: str,
):
    normalized_exposure = str(exposure or "").strip().lower()
    normalized_status = str(publication_status or "").strip().lower()
    if normalized_exposure not in {EXPOSURE_INTERNAL, EXPOSURE_EXTERNAL}:
        raise ValueError("Unsupported Data Group exposure")
    if normalized_exposure == EXPOSURE_INTERNAL:
        normalized_status = "not_applicable"
    elif normalized_status not in EXTERNAL_PUBLICATION_STATUSES:
        raise ValueError("Unsupported external publication status")

    current = get_data_group_by_id(data_group_id)
    if not current:
        return False
    now = datetime.utcnow()
    previous_status = str(current.get("publication_status") or "not_applicable")
    version = int(current.get("publication_version") or 0)
    update_data = {
        "exposure": normalized_exposure,
        "publication_status": normalized_status,
        "update_at": now,
    }
    if normalized_status == "published" and previous_status != "published":
        version += 1
        update_data.update(
            {
                "publication_version": version,
                "published_at": now,
                "published_by": str(actor_id or ""),
            }
        )
    elif normalized_status != "published":
        update_data.update({"published_at": None, "published_by": None})
    event = {
        "exposure": normalized_exposure,
        "status": normalized_status,
        "actor_id": str(actor_id or ""),
        "created_at": now,
        "version": version,
    }
    result = data_groups_collection.update_one(
        {"_id": data_group_id, "delete_at": None},
        {
            "$set": update_data,
            "$push": {
                "publication_history": {"$each": [event], "$slice": -100}
            },
        },
    )
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
