from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone

from pymongo.errors import PyMongoError

from core.attachment_extraction import MAX_CHUNK_CHARACTERS, ExtractedChunk
from core.attachment_index import AttachmentIndex, AttachmentSearchResult
from core.attachment_store import AttachmentRecord
from mongo_table_connecters.mongo_connector import get_database

collection = get_database()["chat_attachment_chunks"]

MAX_INDEX_CHUNKS = 2_000
MAX_SEARCH_CANDIDATES = 2_000
MAX_SEARCH_QUERY_CHARACTERS = 2_000
_WORD = re.compile(r"\w+", re.UNICODE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_attachment_index_indexes() -> bool:
    try:
        collection.create_index(
            [("owner_id", 1), ("conversation_id", 1), ("expires_at", 1)],
            name="attachment_chunk_scope",
        )
        collection.create_index(
            [("attachment_id", 1), ("position", 1)],
            name="attachment_chunk_position",
        )
        collection.create_index("expires_at", expireAfterSeconds=0, name="attachment_chunk_expiry")
        return True
    except PyMongoError:
        logging.warning(
            "Attachment chunk indexes are unavailable; scoped queries and explicit cleanup remain active",
            exc_info=True,
        )
        return False


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Attachment chunk expiry must include a timezone")
    return parsed.astimezone(timezone.utc)


def replace_attachment_chunks(record: AttachmentRecord, chunks: list[ExtractedChunk]) -> int:
    if not chunks or len(chunks) > MAX_INDEX_CHUNKS:
        raise ValueError(f"Attachment index requires 1 to {MAX_INDEX_CHUNKS} chunks")
    expires_at = _timestamp(record.expires_at)
    documents = []
    for expected_position, chunk in enumerate(chunks):
        if (
            chunk.position != expected_position
            or not isinstance(chunk.text, str)
            or not chunk.text.strip()
            or len(chunk.text) > MAX_CHUNK_CHARACTERS
        ):
            raise ValueError("Attachment chunks must be ordered and contain text")
        documents.append(
            {
                "_id": f"{record.attachment_id}:{expected_position:04d}",
                "attachment_id": record.attachment_id,
                "owner_id": record.owner_id,
                "conversation_id": record.conversation_id,
                "filename": record.filename,
                "position": expected_position,
                "page_number": chunk.page_number,
                "page_label": str(chunk.page_label or "")[:100],
                "text": chunk.text,
                "created_at": _timestamp(record.created_at),
                "expires_at": expires_at,
            }
        )
    scope = {
        "attachment_id": record.attachment_id,
        "owner_id": record.owner_id,
        "conversation_id": record.conversation_id,
    }
    collection.delete_many(scope)
    try:
        collection.insert_many(documents, ordered=True)
    except Exception:
        collection.delete_many(scope)
        raise
    return len(documents)


def _score(query: str, query_terms: set[str], text: str) -> float:
    normalized = text.casefold()
    text_terms = set(_WORD.findall(normalized))
    overlap = len(query_terms & text_terms)
    exact_bonus = 2.0 if query.casefold() in normalized else 0.0
    return exact_bonus + overlap / max(1, len(query_terms))


def search_attachment_chunks(
    *,
    owner_id: str,
    conversation_id: str,
    query: str,
    attachment_ids: list[str] | None = None,
    limit: int = 8,
    now: datetime | None = None,
) -> list[AttachmentSearchResult]:
    normalized_query = str(query or "").strip()[:MAX_SEARCH_QUERY_CHARACTERS]
    if not normalized_query:
        return []
    query_terms = set(_WORD.findall(normalized_query.casefold()))
    if not query_terms:
        return []
    scope: dict = {
        "owner_id": owner_id,
        "conversation_id": conversation_id,
        "expires_at": {"$gt": now or _now()},
    }
    if attachment_ids:
        scope["attachment_id"] = {"$in": list(dict.fromkeys(attachment_ids))[:100]}
    candidates = list(collection.find(scope).limit(MAX_SEARCH_CANDIDATES))
    ranked = []
    fallback = []
    for item in candidates:
        score = _score(normalized_query, query_terms, str(item.get("text") or ""))
        result = AttachmentSearchResult(
            attachment_id=str(item.get("attachment_id") or ""),
            filename=str(item.get("filename") or ""),
            page_number=item.get("page_number"),
            page_label=str(item.get("page_label") or ""),
            text=str(item.get("text") or ""),
            score=score,
        )
        fallback.append(result)
        if score > 0:
            ranked.append(result)
    if not ranked:
        ranked = fallback
    ranked.sort(
        key=lambda item: (
            -item.score,
            item.filename,
            item.page_number if item.page_number is not None else 1_000_000,
            item.page_label,
        )
    )
    return ranked[: max(1, min(int(limit), 20))]


def delete_attachment_chunks(
    attachment_id: str,
    *,
    owner_id: str,
    conversation_id: str,
) -> int:
    result = collection.delete_many(
        {
            "attachment_id": attachment_id,
            "owner_id": owner_id,
            "conversation_id": conversation_id,
        }
    )
    return int(result.deleted_count)


def delete_conversation_attachment_chunks(*, owner_id: str, conversation_id: str) -> int:
    result = collection.delete_many(
        {"owner_id": owner_id, "conversation_id": conversation_id}
    )
    return int(result.deleted_count)


def delete_expired_attachment_chunks(*, now: datetime | None = None) -> int:
    result = collection.delete_many({"expires_at": {"$lte": now or _now()}})
    return int(result.deleted_count)


class MongoAttachmentIndex(AttachmentIndex):
    async def replace_attachment(self, record: AttachmentRecord, chunks: list[ExtractedChunk]) -> int:
        return await asyncio.to_thread(replace_attachment_chunks, record, chunks)

    async def search(
        self,
        *,
        owner_id: str,
        conversation_id: str,
        query: str,
        attachment_ids: list[str] | None = None,
        limit: int = 8,
    ) -> list[AttachmentSearchResult]:
        return await asyncio.to_thread(
            search_attachment_chunks,
            owner_id=owner_id,
            conversation_id=conversation_id,
            query=query,
            attachment_ids=attachment_ids,
            limit=limit,
        )

    async def delete_attachment(
        self,
        attachment_id: str,
        *,
        owner_id: str,
        conversation_id: str,
    ) -> int:
        return await asyncio.to_thread(
            delete_attachment_chunks,
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )

    async def delete_expired(self, *, now: datetime | None = None) -> int:
        return await asyncio.to_thread(delete_expired_attachment_chunks, now=now)
