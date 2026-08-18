from mongo_table_connecters.mongo_connector import get_database

db = get_database()
feedback_collection = db["feedbacks"]

def get_all_feedback():
    cursor = feedback_collection.find({})         
    feedbacks = [feedback for feedback in cursor]
    return feedbacks
