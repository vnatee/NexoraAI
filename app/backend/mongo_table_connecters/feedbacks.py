from datetime import datetime
import uuid, json, base64
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
feedbacks_collection = db["feedbacks"]

def insert_feedback(user: str,feedback: str,images: list):
    files = []
    for image in images.getlist("file"):
        content_type = image.content_type
        file_bytes = image.read()
        file_base64 = base64.b64encode(file_bytes).decode("utf-8")
        files.append({"file_type":content_type,"image":file_base64})
    user_dict = json.loads(user)
    feedback_data = {
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

    result = feedbacks_collection.insert_one(feedback_data)
    return result

def get_feedback_by_id(feedback_id: str):
    feedback = feedbacks_collection.find_one({"_id": feedback_id, "delete_at": None})
    return feedback

def get_all_feedbacks():
    feedbacks = list(feedbacks_collection.find({"delete_at": None}))
    return feedbacks

def delete_feedback_by_id(feedback_id: str):
    result = feedbacks_collection.delete_one({"_id": feedback_id})
    return result

def soft_delete_feedback_by_id(feedback_id: str):
    result = feedbacks_collection.update_one(
        {"_id": feedback_id},
        {"$set": {"delete_at": datetime.utcnow()}}
    )
    return result.modified_count > 0
