import os
from urllib.parse import quote_plus

from pymongo import MongoClient
from pymongo.database import Database

from load_azd_env import load_azd_env

# Local/container deployments can provide a standard MongoDB URI and do not
# need an azd environment. Legacy Azure deployments keep using the existing
# username/password/SRV settings.
if not os.getenv("MONGO_URI") or not os.getenv("MONGO_DB_NAME"):
    load_azd_env()

DB_NAME = os.environ["MONGO_DB_NAME"]
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    username = quote_plus(os.environ["MONGO_USERNAME"])
    password = quote_plus(os.environ["MONGO_PASSWORD"])
    url = os.environ["MONGO_URL"]
    MONGO_URI = f"mongodb+srv://{username}:{password}@{url}"

_client: MongoClient | None = None


def get_database() -> Database:
    """Return the application database backed by one process-wide client.

    Connector modules import this function and keep collection references at
    module scope. Reusing a lazy client avoids starting a separate MongoDB
    monitor thread for every connector merely by importing the application.
    """
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, connect=False)
    return _client[DB_NAME]
