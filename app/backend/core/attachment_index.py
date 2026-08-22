from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from core.attachment_extraction import ExtractedChunk
from core.attachment_store import AttachmentRecord


@dataclass(frozen=True)
class AttachmentSearchResult:
    attachment_id: str
    filename: str
    page_number: int | None
    page_label: str
    text: str
    score: float


class AttachmentIndex(Protocol):
    async def replace_attachment(self, record: AttachmentRecord, chunks: list[ExtractedChunk]) -> int: ...

    async def search(
        self,
        *,
        owner_id: str,
        conversation_id: str,
        query: str,
        attachment_ids: list[str] | None = None,
        limit: int = 8,
    ) -> list[AttachmentSearchResult]: ...

    async def delete_attachment(
        self,
        attachment_id: str,
        *,
        owner_id: str,
        conversation_id: str,
    ) -> int: ...

    async def delete_expired(self, *, now: datetime | None = None) -> int: ...
