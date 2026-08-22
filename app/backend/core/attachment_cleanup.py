from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from core.attachment_store import AttachmentStore
from core.attachment_index import AttachmentIndex


@dataclass(frozen=True)
class AttachmentCleanupResult:
    deleted_objects: int
    deleted_chunks: int
    deleted_metadata: int


async def cleanup_expired_attachments(
    store: AttachmentStore,
    delete_expired_metadata: Callable[..., int],
    *,
    index: AttachmentIndex | None = None,
    now: datetime | None = None,
) -> AttachmentCleanupResult:
    """Delete private objects first, then their independently retained metadata."""
    deleted_objects = await store.delete_expired(now=now)
    deleted_chunks = await index.delete_expired(now=now) if index else 0
    deleted_metadata = await asyncio.to_thread(delete_expired_metadata, now=now)
    return AttachmentCleanupResult(
        deleted_objects=deleted_objects,
        deleted_chunks=deleted_chunks,
        deleted_metadata=deleted_metadata,
    )
