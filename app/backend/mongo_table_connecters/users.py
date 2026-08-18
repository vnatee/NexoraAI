from datetime import datetime
import uuid
from mongo_table_connecters.mongo_connector import get_database

db = get_database()
users_collection = db["users"]

def insert_user(email: str,ad_email: str,first_name: str,last_name: str,employee_id: str,tel: str,active: bool,is_sys_admin: bool):
    user_id = str(uuid.uuid4())
    user_data = {
        "_id": user_id,         
        "create_at": datetime.utcnow(),   
        "update_at": datetime.utcnow(),  
        "delete_at": None,              
        "email": email,                  
        "ad_email": ad_email,                  
        "first_name": first_name,              
        "last_name": last_name,
        "employee_id": employee_id,
        "tel": tel,
        "active": active,
        "is_sys_admin" : is_sys_admin          
    }

    result = users_collection.insert_one(user_data)
    return result,user_id

def get_user_by_id(user_id: str):
    user = users_collection.find_one({"_id": user_id, "delete_at": None})
    return user

def get_user_by_ad_email(user_email: str):
    user = users_collection.find_one({"ad_email": user_email, "delete_at": None})
    return user

def get_all_user_by_is_sys_admin(is_sys_admin: bool):
    user = list(users_collection.find({"is_sys_admin": is_sys_admin, "delete_at": None}))
    return user

def get_all_users():
    users = list(users_collection.find({"delete_at": None}))
    return users

def update_user(user_id: str, email: str = None,ad_email: str = None,first_name: str = None,last_name: str = None,employee_id: str = None,tel: str = None,active: bool = None,is_sys_admin: bool = None):
    update_data = {
        "update_at": datetime.utcnow()
    }
    if email is not None:
        update_data["email"] = email
    if ad_email is not None:
        update_data["ad_email"] = ad_email
    if first_name is not None:
        update_data["first_name"] = first_name
    if last_name is not None:
        update_data["last_name"] = last_name
    if employee_id is not None:
        update_data["employee_id"] = employee_id
    if tel is not None:
        update_data["tel"] = tel
    if active is not None:
        update_data["active"] = active
    if is_sys_admin is not None:
        update_data["is_sys_admin"] = is_sys_admin

    result = users_collection.update_one(
        {"_id": user_id}, {"$set": update_data})
    return result.modified_count > 0

def delete_user_by_id(user_id: str):
    result = users_collection.delete_one({"_id": user_id})
    return result

def soft_delete_user_by_id(user_id: str):
    result = users_collection.update_one(
        {"_id": user_id},
        {"$set": {"delete_at": datetime.utcnow()}}
    )
    return result.modified_count > 0
