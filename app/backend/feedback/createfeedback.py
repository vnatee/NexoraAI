import json
import uuid
from datetime import datetime
from mongo_table_connecters.mongo_connector import get_database
import base64

db = get_database()
usage_collection = db["feedbacks"]

def insert_feedback(user,feedback,images):
    files = []
    for image in images.getlist("file"):
        content_type = image.content_type
        file_bytes = image.read()
        file_base64 = base64.b64encode(file_bytes).decode("utf-8")
        files.append({"file_type":content_type,"image":file_base64})
    user_dict = json.loads(user)
    usage_data = {
        "_id": str(uuid.uuid4()),       
        "create_at": datetime.utcnow(), 
        "update_at": datetime.utcnow(),  
        "delete_at": None,
        "user":  {
            "_id": user_dict["_id"],
            "name": user_dict["name"]
        },             
        "feedback": feedback,                                          
        "images": files,                  
    }
    usage_collection.insert_one(usage_data)