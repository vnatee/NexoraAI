from urllib.parse import quote_plus
from pymongo import MongoClient
from load_azd_env import load_azd_env
import os

#load_azd_env()
username = os.environ["MONGO_USERNAME"]
password = os.environ["MONGO_PASSWORD"]
url = os.environ["MONGO_URL"]
DB_NAME = os.environ["MONGO_DB_NAME"]
# escape username และ password
username = quote_plus(username)
password = quote_plus(password)
MONGO_URI = f"mongodb+srv://{username}:{password}@{url}"

# ฟังก์ชันสำหรับเชื่อมต่อ MongoDB


def get_database():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]
