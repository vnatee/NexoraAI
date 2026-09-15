from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
prompt_collection = db["fixed_prompt"]

def insert_fixed_prompt(fixed_prompt: str):
    prompt_data = {
        "_id": str(uuid.uuid4()),         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "fixed_prompt": fixed_prompt       
    }

    result = prompt_collection.insert_one(prompt_data)
    return result

def get_all_fixed_prompt():
    fixed_prompt = list(prompt_collection.find({"delete_at": None}))
    return fixed_prompt