from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
mail_collection = db["mail_template"]

def insert_mail_template(template_name: str,subject: str,body: str):
    template_data = {
        "_id": str(uuid.uuid4()),         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "template_name": template_name,                  
        "subject": subject,                  
        "body": body        
    }

    result = mail_collection.insert_one(template_data)
    return result

def get_all_mail_template():
    template = list(mail_collection.find({"delete_at": None}))
    return template

def get_mail_template_by_name(template_name: str):
    template = mail_collection.find_one({"template_name": template_name, "delete_at": None})
    return template