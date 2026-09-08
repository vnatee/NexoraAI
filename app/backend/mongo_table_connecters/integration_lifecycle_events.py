import logging
import os
import uuid
from datetime import datetime, timezone

from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["integration_lifecycle_events"]


def insert_integration_lifecycle_event(
    *,
    action: str,
    status: str,
    connection_id: str,
    team_id: str,
    actor_id: str,
    vendor: str,
    error_type: str = "",
) -> None:
    if os.getenv("DISABLE_INTEGRATION_AUDIT_PERSISTENCE", "").lower() == "true":
        return
    try:
        collection.insert_one(
            {
                "_id": str(uuid.uuid4()),
                "action": str(action)[:50],
                "status": str(status)[:20],
                "connection_id": str(connection_id)[:100],
                "team_id": str(team_id)[:100],
                "actor_id": str(actor_id)[:100],
                "vendor": str(vendor)[:50],
                "error_type": str(error_type)[:100],
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception:
        logging.warning("Unable to persist integration lifecycle event", exc_info=True)
