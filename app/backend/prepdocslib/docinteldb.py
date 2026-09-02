import uuid
from datetime import datetime, timezone
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
usage_collection = db["doc_intel_usage"]
processing_usage_collection = db["document_processing_usage"]

def insert_docintel_usage(uid,tid,type,count):
    usage_data = {
        "_id": str(uuid.uuid4()),       
        "create_at": datetime.now(timezone.utc),
        "update_at": datetime.now(timezone.utc),
        "delete_at": None,
        "user": uid,               
        "team": tid,                                          
        "upload_type": type,             
        "ocr_pages": int(count)     
    }
    usage_collection.insert_one(usage_data)

def get_all_docintel_usage():
    cursor = usage_collection.find({})         
    usages = [usage for usage in cursor]
    return usages


def insert_document_processing_usage(
    *,
    owner_id: str,
    owner_name: str,
    team_id: str,
    scope: str,
    provider_id: str,
    provider_name: str,
    profile_id: str,
    profile_name: str,
    page_count: int,
    file_type: str,
    duration_ms: int,
) -> None:
    """Persist safe, provider-neutral document processing telemetry."""
    now = datetime.now(timezone.utc)
    processing_usage_collection.insert_one({
        "_id": str(uuid.uuid4()),
        "schema_version": 1,
        "create_at": now,
        "update_at": now,
        "delete_at": None,
        "user": {"_id": str(owner_id or ""), "name": str(owner_name or "")[:254]},
        "team": {"_id": str(team_id or "")} if team_id else None,
        "scope": str(scope or "personal")[:20],
        "provider_id": str(provider_id or "")[:100],
        "provider_name": str(provider_name or "System parser")[:200],
        "profile_id": str(profile_id or "")[:100],
        "profile_name": str(profile_name or "")[:200],
        "file_type": str(file_type or "unknown").lower()[:30],
        "page_count": max(0, int(page_count or 0)),
        "duration_ms": max(0, int(duration_ms or 0)),
        "status": "completed",
    })
