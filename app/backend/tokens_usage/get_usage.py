from mongo_table_connecters.mongo_connector import get_database

db = get_database()
usage_collection = db["users_usage"]

def get_all_usage():
    cursor = usage_collection.find({})         
    usages = [usage for usage in cursor]
    return usages
