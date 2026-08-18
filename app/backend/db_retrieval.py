import logging
import re
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote_plus

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from mongo_table_connecters.database_binding import get_enabled_database_bindings_by_agent_id
from mongo_table_connecters.external_database import get_external_database_by_id

logger = logging.getLogger(__name__)


def is_mongodb_database(external_db: Dict[str, Any]) -> bool:
    return external_db is not None and str(external_db.get("db_type", "")).lower() == "mongodb"


def build_mongodb_uri(external_db: Dict[str, Any]) -> str:
    host = str(external_db.get("host", "")).strip()
    port = external_db.get("port")
    username = external_db.get("username")
    password = external_db.get("password")
    database = str(external_db.get("database", "")).strip()

    # Handle full connection string with mongodb:// or mongodb+srv:// prefix
    if host.startswith("mongodb://") or host.startswith("mongodb+srv://"):
        return host

    # For simple host:port format (no protocol prefix)
    credentials = ""
    if username and password:
        credentials = f"{quote_plus(username)}:{quote_plus(password)}@"

    if port:
        return f"mongodb+srv://{credentials}{host}:{port}/{database}?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"
    else:
        return f"mongodb+srv://{credentials}{host}/{database}?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"


def connect_to_external_mongodb(external_db: Dict[str, Any], server_selection_timeout_ms: int = 5000) -> MongoClient:
    uri = build_mongodb_uri(external_db)
    return MongoClient(uri, serverSelectionTimeoutMS=server_selection_timeout_ms)


def close_external_mongodb_client(client: MongoClient) -> None:
    try:
        client.close()
    except Exception:
        logger.exception("Failed to close external MongoDB client")


def _get_database_from_client(client: MongoClient, external_db: Dict[str, Any]):
    return client[external_db["database"]]


def list_mongodb_collections(
    external_db: Dict[str, Any],
    collection_name: Optional[str] = None,
    max_collections: int = 3,
) -> list[str]:
    client = connect_to_external_mongodb(external_db)
    try:
        db = _get_database_from_client(client, external_db)
        if collection_name:
            return [collection_name]

        collection_names = [
            name
            for name in db.list_collection_names()
            if not name.startswith("system.")
        ]
        return collection_names[:max_collections]
    finally:
        close_external_mongodb_client(client)


def _collection_has_text_index(collection: Collection) -> bool:
    try:
        index_information = collection.index_information()
        for index in index_information.values():
            if any(field_type == "text" for _, field_type in index.get("key", [])):
                return True
    except PyMongoError:
        logger.exception("Unable to check text index information")
    return False


def _format_document_as_text(document: Any, prefix: str = "") -> str:
    lines: List[str] = []

    def _walk(value: Any, current_path: str) -> None:
        if isinstance(value, dict):
            for key, sub_value in value.items():
                if key == "_id":
                    continue
                _walk(sub_value, f"{current_path}{key}.")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                _walk(item, f"{current_path}[{index}].")
        else:
            lines.append(f"{current_path.rstrip('.')}: {value}")

    _walk(document, prefix)
    return "\n".join(lines)


def _build_source_text(
    external_db: Dict[str, Any],
    binding: Dict[str, Any],
    collection_name: str,
    document_text: str,
    document_index: int,
) -> str:
    alias = binding.get("alias") or ""
    return (
        f"===== External MongoDB Source =====\n"
        f"Database connection name: {external_db.get('name', 'unknown')}\n"
        f"Alias: {alias}\n"
        f"Host: {external_db.get('host', 'unknown')}\n"
        f"Database: {external_db.get('database', 'unknown')}\n"
        f"Collection: {collection_name}\n"
        f"Document: {document_index + 1}\n"
        f"Content:\n{document_text}\n"
    )


def retrieve_documents_from_external_mongodb(
    external_db: Dict[str, Any],
    query: Optional[str] = None,
    collection_name: Optional[str] = None,
    max_docs_per_collection: int = 5,
    max_collections: int = 3,
) -> list[Dict[str, Any]]:
    client = connect_to_external_mongodb(external_db)
    try:
        db = _get_database_from_client(client, external_db)
        collection_names = list_mongodb_collections(external_db, collection_name, max_collections)
        documents: List[Dict[str, Any]] = []

        for collection_name in collection_names:
            if not collection_name:
                continue
            collection = db[collection_name]
            query_filter: Dict[str, Any] = {}

            if query and _collection_has_text_index(collection):
                query_filter = {"$text": {"$search": query}}
                projection = {"score": {"$meta": "textScore"}}
                cursor = collection.find(query_filter, projection).sort(
                    [("score", {"$meta": "textScore"})]
                )
            else:
                cursor = collection.find({})

            try:
                for item in cursor.limit(max_docs_per_collection):
                    documents.append({
                        "collection": collection_name,
                        "document": item,
                    })
            except PyMongoError:
                logger.exception(
                    "Failed to fetch documents from collection %s", collection_name
                )

        return documents
    finally:
        close_external_mongodb_client(client)


def get_agent_mongodb_sources(
    agent_id: str,
    query: Optional[str] = None,
    max_collections: int = 3,
    max_documents_per_collection: int = 5,
) -> list[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    bindings = get_enabled_database_bindings_by_agent_id(agent_id)
    for binding in bindings:
        external_db = get_external_database_by_id(binding["integration_id"])
        if not external_db or not is_mongodb_database(external_db):
            continue

        for document_payload in retrieve_documents_from_external_mongodb(
            external_db,
            query=query,
            collection_name=None,  # Query all collections instead of using alias
            max_docs_per_collection=max_documents_per_collection,
            max_collections=max_collections,
        ):
            document = document_payload["document"]
            collection_name = document_payload["collection"]
            document_text = _format_document_as_text(document)
            source_text = _build_source_text(
                external_db,
                binding,
                collection_name,
                document_text,
                len(sources),
            )
            sources.append(
                {
                    "binding_id": binding.get("_id"),
                    "database_id": external_db.get("_id"),
                    "database_name": external_db.get("name"),
                    "db_type": external_db.get("db_type"),
                    "host": external_db.get("host"),
                    "database": external_db.get("database"),
                    "collection": collection_name,
                    "alias": binding.get("alias"),
                    "content": document_text,
                    "source_text": source_text,
                }
            )

    return sources
