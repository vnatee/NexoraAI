import uuid
from datetime import datetime
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
usage_collection = db["doc_intel_usage"]

def insert_docintel_usage(uid,tid,type,count):
    usage_data = {
        "_id": str(uuid.uuid4()),       
        "create_at": datetime.utcnow(), 
        "update_at": datetime.utcnow(),  
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
