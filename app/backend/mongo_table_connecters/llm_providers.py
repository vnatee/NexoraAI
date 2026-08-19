import uuid
from datetime import datetime, timezone

from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["llm_providers"]


def list_llm_providers(*, include_deleted: bool = False):
    query = {} if include_deleted else {"delete_at": None}
    return list(collection.find(query).sort("name", 1))


def get_llm_provider(provider_id: str, *, include_deleted: bool = False):
    query = {"_id": provider_id}
    if not include_deleted:
        query["delete_at"] = None
    return collection.find_one(query)


def insert_llm_provider(data: dict):
    now = datetime.now(timezone.utc)
    provider_id = str(uuid.uuid4())
    document = {
        "_id": provider_id,
        "name": data["name"],
        "vendor": data.get("vendor"),
        "provider": data["provider"],
        "endpoint": data.get("endpoint"),
        "base_url": data.get("base_url"),
        "api_version": data.get("api_version"),
        "organization": data.get("organization"),
        "models": data["models"],
        "enabled": data.get("enabled", True),
        "api_key_ciphertext": data.get("api_key_ciphertext"),
        "create_at": now,
        "update_at": now,
        "delete_at": None,
    }
    collection.insert_one(document)
    return document


def update_llm_provider(provider_id: str, data: dict):
    updates = {**data, "update_at": datetime.now(timezone.utc)}
    collection.update_one({"_id": provider_id, "delete_at": None}, {"$set": updates})
    return get_llm_provider(provider_id)


def soft_delete_llm_provider(provider_id: str):
    return collection.update_one(
        {"_id": provider_id, "delete_at": None},
        {"$set": {"enabled": False, "delete_at": datetime.now(timezone.utc)}},
    ).modified_count > 0
