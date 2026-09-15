from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["chat_history_sessions"]
settings = get_database()["application_settings"]
audit_collection = get_database()["chat_history_audit_events"]
SYSTEM_SETTINGS_ID = "chat_history_retention:system"
DEFAULT_RETENTION_DAYS = 90
MAX_HISTORY_BYTES = 8 * 1024 * 1024
ALLOWED_RETENTION_DAYS = {0, 30, 90, 180, 365}
AUDIT_RETENTION_DAYS = 365


def ensure_indexes() -> None:
    collection.create_index(
        [("owner_id", 1), ("updated_at", -1)], name="history_owner_updated"
    )
    # Conversation cleanup must cascade to attachments before the history row
    # disappears, so a worker owns deletion instead of a Mongo TTL index.
    if "history_expiry" in collection.index_information():
        collection.drop_index("history_expiry")
    collection.create_index("expires_at", name="history_expiry_scan")
    audit_collection.create_index("expires_at", expireAfterSeconds=0, name="history_audit_expiry")


def _settings_id(team_id: str | None = None) -> str:
    return f"chat_history_retention:team:{team_id}" if team_id else SYSTEM_SETTINGS_ID


def configured_retention_days(team_id: str | None = None) -> int | None:
    document = settings.find_one({"_id": _settings_id(team_id)}) or {}
    value = document.get("retention_days")
    return int(value) if value is not None else None


def retention_days(team_id: str | None = None) -> int:
    document = settings.find_one({"_id": SYSTEM_SETTINGS_ID}) or {}
    value = document.get("retention_days", os.getenv("CHAT_HISTORY_RETENTION_DAYS", DEFAULT_RETENTION_DAYS))
    # Read legacy numeric policies safely; new writes are restricted to the
    # supported Portal choices below.
    system_days = max(0, min(int(value), 3650))
    team_days = configured_retention_days(team_id) if team_id else None
    if team_days is not None:
        team_days = max(0, min(int(team_days), 3650))
    if team_days is None:
        return system_days
    if system_days == 0:
        return team_days
    if team_days == 0:
        return system_days
    return min(system_days, team_days)


def _normalize_retention_days(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("Retention period must be 30, 90, 180, 365, or 0 for no expiry")
    try:
        days = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Retention period must be 30, 90, 180, 365, or 0 for no expiry") from error
    if days not in ALLOWED_RETENTION_DAYS:
        raise ValueError("Retention period must be 30, 90, 180, 365, or 0 for no expiry")
    return days


def save_retention_days(value: object, team_id: str | None = None) -> int:
    days = _normalize_retention_days(value)
    if team_id:
        system_days = retention_days()
        if system_days and (days == 0 or days > system_days):
            raise ValueError(f"Team retention cannot exceed the System policy of {system_days} days")
    now = datetime.now(timezone.utc)
    settings.update_one(
        {"_id": _settings_id(team_id)},
        {
            "$set": {"retention_days": days, "team_id": team_id, "updated_at": now},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    if not team_id and days:
        settings.update_many(
            {
                "_id": {"$regex": "^chat_history_retention:team:"},
                "$or": [{"retention_days": 0}, {"retention_days": {"$gt": days}}],
            },
            {"$set": {"retention_days": days, "updated_at": now}},
        )
    policies = [(team_id, days)] if team_id else [(None, days)]
    if not team_id:
        policies.extend(
            (str(value), retention_days(str(value)))
            for value in collection.distinct("team_id", {"team_id": {"$nin": [None, ""]}})
        )
    for policy_team_id, policy_days in policies:
        query = {"team_id": policy_team_id} if policy_team_id else {"$or": [{"team_id": None}, {"team_id": ""}, {"team_id": {"$exists": False}}]}
        if policy_days == 0:
            collection.update_many(query, {"$set": {"expires_at": None}})
        else:
            collection.update_many(
                query,
                [
                    {
                        "$set": {
                            "expires_at": {
                                "$dateAdd": {
                                    "startDate": "$updated_at",
                                    "unit": "day",
                                    "amount": policy_days,
                                }
                            }
                        }
                    }
                ],
            )
    return days


def upsert_session(
    session_id: str,
    owner_id: str,
    answers: object,
    team_id: str | None = None,
    conversation_id: str | None = None,
) -> None:
    try:
        session_id = str(uuid.UUID(session_id))
    except (ValueError, AttributeError, TypeError) as error:
        raise ValueError("Chat history session id must be a valid UUID") from error
    if not isinstance(answers, list) or not answers:
        raise ValueError("answers must be a non-empty array")
    serialized = json.dumps(answers, ensure_ascii=False, default=str)
    if len(serialized.encode("utf-8")) > MAX_HISTORY_BYTES:
        raise ValueError("Chat history exceeds the per-conversation storage limit")
    first_question = str(answers[0][0] if isinstance(answers[0], list) and answers[0] else "Untitled")
    now = datetime.now(timezone.utc)
    days = retention_days(team_id)
    normalized_conversation_id = str(uuid.UUID(conversation_id or session_id))
    collection.update_one(
        {"_id": session_id, "owner_id": owner_id},
        {
            "$set": {
                "owner_id": owner_id,
                "team_id": team_id,
                "conversation_id": normalized_conversation_id,
                "title": first_question[:50] + ("..." if len(first_question) > 50 else ""),
                "answers": answers,
                "timestamp": int(now.timestamp() * 1000),
                "updated_at": now,
                "expires_at": now + timedelta(days=days) if days else None,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


def _decode_cursor(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        decoded = base64.urlsafe_b64decode(value.encode("ascii") + b"===").decode("utf-8")
        return datetime.fromisoformat(decoded)
    except (ValueError, UnicodeError):
        raise ValueError("Invalid continuation token") from None


def _encode_cursor(value: datetime) -> str:
    return base64.urlsafe_b64encode(value.isoformat().encode("utf-8")).decode("ascii").rstrip("=")


def list_sessions(owner_id: str, count: int, cursor: str | None = None) -> tuple[list[dict[str, Any]], str | None]:
    query: dict[str, Any] = {
        "owner_id": owner_id,
        "$or": [
            {"expires_at": {"$gt": datetime.now(timezone.utc)}},
            {"expires_at": None},
            {"expires_at": {"$exists": False}},
        ],
    }
    before = _decode_cursor(cursor)
    if before:
        query["updated_at"] = {"$lt": before}
    documents = list(collection.find(query, {"answers": 0}).sort("updated_at", -1).limit(count + 1))
    has_more = len(documents) > count
    documents = documents[:count]
    sessions = [
        {"id": item["_id"], "title": item.get("title", "Untitled"), "timestamp": item.get("timestamp", 0)}
        for item in documents
    ]
    token = _encode_cursor(documents[-1]["updated_at"]) if has_more and documents else None
    return sessions, token


def get_session(session_id: str, owner_id: str) -> dict[str, Any] | None:
    return collection.find_one(
        {
            "_id": session_id,
            "owner_id": owner_id,
            "$or": [
                {"expires_at": {"$gt": datetime.now(timezone.utc)}},
                {"expires_at": None},
                {"expires_at": {"$exists": False}},
            ],
        }
    )


def delete_session(session_id: str, owner_id: str) -> bool:
    return collection.delete_one({"_id": session_id, "owner_id": owner_id}).deleted_count == 1


def list_expired_sessions(now: datetime | None = None, limit: int = 100) -> list[dict[str, Any]]:
    return list(
        collection.find(
            {"expires_at": {"$type": "date", "$lte": now or datetime.now(timezone.utc)}},
            {"owner_id": 1, "conversation_id": 1},
        ).limit(max(1, min(limit, 500)))
    )


def insert_deletion_audit(
    *, actor_id: str, reason: str, conversation_count: int, attachment_count: int
) -> None:
    now = datetime.now(timezone.utc)
    audit_collection.insert_one(
        {
            "event_type": "chat_history_deleted",
            "actor_id": str(actor_id or "system")[:256],
            "reason": reason if reason in {"user", "retention"} else "retention",
            "conversation_count": max(0, int(conversation_count)),
            "attachment_count": max(0, int(attachment_count)),
            "created_at": now,
            "expires_at": now + timedelta(days=AUDIT_RETENTION_DAYS),
        }
    )
