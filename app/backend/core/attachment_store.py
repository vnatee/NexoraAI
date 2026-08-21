from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol


DEFAULT_ATTACHMENT_TTL = timedelta(hours=24)
DEFAULT_MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
_SAFE_FILENAME_CHARACTER = re.compile(r"[^\w.() -]+", re.UNICODE)


class AttachmentStoreError(ValueError):
    pass


class AttachmentAccessError(AttachmentStoreError):
    pass


class AttachmentNotFoundError(AttachmentStoreError):
    pass


class AttachmentExpiredError(AttachmentNotFoundError):
    pass


class AttachmentIntegrityError(AttachmentStoreError):
    pass


@dataclass(frozen=True)
class AttachmentRecord:
    attachment_id: str
    owner_id: str
    conversation_id: str
    filename: str
    content_type: str
    size: int
    sha256: str
    created_at: str
    expires_at: str


@dataclass(frozen=True)
class StoredAttachment:
    record: AttachmentRecord
    content: bytes


class AttachmentStore(Protocol):
    async def put(
        self,
        *,
        owner_id: str,
        conversation_id: str,
        filename: str,
        content_type: str,
        content: bytes,
        ttl: timedelta | None = None,
    ) -> AttachmentRecord: ...

    async def get(
        self, attachment_id: str, *, owner_id: str, conversation_id: str
    ) -> StoredAttachment: ...

    async def delete(
        self, attachment_id: str, *, owner_id: str, conversation_id: str
    ) -> None: ...

    async def delete_expired(self, *, now: datetime | None = None) -> int: ...


def normalize_attachment_filename(value: str) -> str:
    filename = Path(str(value or "").replace("\\", "/")).name.strip().strip(".")
    filename = _SAFE_FILENAME_CHARACTER.sub("_", filename)
    filename = re.sub(r"\s+", " ", filename).strip()
    if not filename:
        filename = "attachment"
    return filename[:255]


def _required_identifier(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > 256 or any(ord(char) < 32 for char in normalized):
        raise AttachmentStoreError(f"{label} must be a non-empty identifier of at most 256 characters")
    return normalized


def _utc(value: datetime | None = None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None:
        raise AttachmentStoreError("Attachment timestamps must include a timezone")
    return result.astimezone(timezone.utc)


def _parse_timestamp(value: str) -> datetime:
    try:
        return _utc(datetime.fromisoformat(value))
    except (TypeError, ValueError) as error:
        raise AttachmentIntegrityError("Attachment metadata contains an invalid timestamp") from error


class LocalAttachmentStore:
    """Private filesystem adapter for local/container deployments.

    Metadata sidecars are an adapter detail for this first storage slice. The
    public contract keeps callers independent from the later Mongo metadata and
    Azure/S3 object-store adapters.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        default_ttl: timedelta = DEFAULT_ATTACHMENT_TTL,
        max_bytes: int = DEFAULT_MAX_ATTACHMENT_BYTES,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if default_ttl <= timedelta(0):
            raise AttachmentStoreError("Attachment TTL must be greater than zero")
        if max_bytes <= 0:
            raise AttachmentStoreError("Attachment size limit must be greater than zero")
        self.root = Path(root).resolve()
        self.default_ttl = default_ttl
        self.max_bytes = max_bytes
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)

    def _paths(self, attachment_id: str) -> tuple[Path, Path]:
        try:
            normalized_id = str(uuid.UUID(str(attachment_id)))
        except (ValueError, AttributeError, TypeError) as error:
            raise AttachmentNotFoundError("Attachment not found") from error
        directory = self.root / normalized_id[:2]
        return directory / f"{normalized_id}.bin", directory / f"{normalized_id}.json"

    @staticmethod
    def _authorize(record: AttachmentRecord, owner_id: str, conversation_id: str) -> None:
        owner_matches = hmac.compare_digest(record.owner_id, owner_id)
        conversation_matches = hmac.compare_digest(record.conversation_id, conversation_id)
        if not owner_matches or not conversation_matches:
            raise AttachmentAccessError("Attachment does not belong to this owner and conversation")

    @staticmethod
    def _write_private(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path.parent, 0o700)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".attachment-", dir=path.parent)
        temporary_path = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
            os.chmod(path, 0o600)
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
            temporary_path.unlink(missing_ok=True)
            raise

    def _put_sync(
        self,
        *,
        owner_id: str,
        conversation_id: str,
        filename: str,
        content_type: str,
        content: bytes,
        ttl: timedelta | None,
    ) -> AttachmentRecord:
        owner = _required_identifier(owner_id, "owner_id")
        conversation = _required_identifier(conversation_id, "conversation_id")
        media_type = str(content_type or "").strip().lower()
        if not media_type or len(media_type) > 255:
            raise AttachmentStoreError("content_type is required")
        if not isinstance(content, bytes):
            raise AttachmentStoreError("Attachment content must be bytes")
        if not content or len(content) > self.max_bytes:
            raise AttachmentStoreError(f"Attachment must contain 1 to {self.max_bytes} bytes")
        retention = ttl or self.default_ttl
        if retention <= timedelta(0):
            raise AttachmentStoreError("Attachment TTL must be greater than zero")

        now = _utc(self._clock())
        attachment_id = str(uuid.uuid4())
        record = AttachmentRecord(
            attachment_id=attachment_id,
            owner_id=owner,
            conversation_id=conversation,
            filename=normalize_attachment_filename(filename),
            content_type=media_type,
            size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            created_at=now.isoformat(),
            expires_at=(now + retention).isoformat(),
        )
        payload_path, metadata_path = self._paths(attachment_id)
        try:
            self._write_private(payload_path, content)
            self._write_private(
                metadata_path,
                json.dumps(asdict(record), ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            )
        except Exception:
            payload_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            raise
        return record

    def _load_record(self, attachment_id: str) -> tuple[AttachmentRecord, Path, Path]:
        payload_path, metadata_path = self._paths(attachment_id)
        try:
            document = json.loads(metadata_path.read_text(encoding="utf-8"))
            record = AttachmentRecord(**document)
        except FileNotFoundError as error:
            raise AttachmentNotFoundError("Attachment not found") from error
        except (json.JSONDecodeError, TypeError) as error:
            raise AttachmentIntegrityError("Attachment metadata is invalid") from error
        if record.attachment_id != str(uuid.UUID(str(attachment_id))):
            raise AttachmentIntegrityError("Attachment metadata ID does not match its storage key")
        return record, payload_path, metadata_path

    @staticmethod
    def _remove(payload_path: Path, metadata_path: Path) -> None:
        payload_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        try:
            payload_path.parent.rmdir()
        except OSError:
            pass

    def _get_sync(self, attachment_id: str, *, owner_id: str, conversation_id: str) -> StoredAttachment:
        owner = _required_identifier(owner_id, "owner_id")
        conversation = _required_identifier(conversation_id, "conversation_id")
        record, payload_path, metadata_path = self._load_record(attachment_id)
        self._authorize(record, owner, conversation)
        if _parse_timestamp(record.expires_at) <= _utc(self._clock()):
            self._remove(payload_path, metadata_path)
            raise AttachmentExpiredError("Attachment has expired")
        try:
            content = payload_path.read_bytes()
        except FileNotFoundError as error:
            raise AttachmentIntegrityError("Attachment payload is missing") from error
        if len(content) != record.size or not hmac.compare_digest(hashlib.sha256(content).hexdigest(), record.sha256):
            raise AttachmentIntegrityError("Attachment payload failed its integrity check")
        return StoredAttachment(record=record, content=content)

    def _delete_sync(self, attachment_id: str, *, owner_id: str, conversation_id: str) -> None:
        owner = _required_identifier(owner_id, "owner_id")
        conversation = _required_identifier(conversation_id, "conversation_id")
        record, payload_path, metadata_path = self._load_record(attachment_id)
        self._authorize(record, owner, conversation)
        self._remove(payload_path, metadata_path)

    def _delete_expired_sync(self, now: datetime | None) -> int:
        cutoff = _utc(now or self._clock())
        deleted = 0
        for metadata_path in self.root.glob("*/*.json"):
            try:
                document = json.loads(metadata_path.read_text(encoding="utf-8"))
                record = AttachmentRecord(**document)
                if _parse_timestamp(record.expires_at) > cutoff:
                    continue
                payload_path, expected_metadata_path = self._paths(record.attachment_id)
                if expected_metadata_path != metadata_path:
                    continue
                self._remove(payload_path, metadata_path)
                deleted += 1
            except (AttachmentStoreError, json.JSONDecodeError, OSError, TypeError, ValueError):
                # Corrupt metadata cannot safely authorize or calculate retention.
                # Fail closed so its payload cannot remain indefinitely.
                self._remove(metadata_path.with_suffix(".bin"), metadata_path)
                deleted += 1
        orphan_cutoff = cutoff - self.default_ttl
        for payload_path in self.root.glob("*/*.bin"):
            if payload_path.with_suffix(".json").exists():
                continue
            try:
                modified_at = datetime.fromtimestamp(payload_path.stat().st_mtime, timezone.utc)
                if modified_at <= orphan_cutoff:
                    self._remove(payload_path, payload_path.with_suffix(".json"))
                    deleted += 1
            except OSError:
                continue
        return deleted

    async def put(
        self,
        *,
        owner_id: str,
        conversation_id: str,
        filename: str,
        content_type: str,
        content: bytes,
        ttl: timedelta | None = None,
    ) -> AttachmentRecord:
        return await asyncio.to_thread(
            self._put_sync,
            owner_id=owner_id,
            conversation_id=conversation_id,
            filename=filename,
            content_type=content_type,
            content=content,
            ttl=ttl,
        )

    async def get(self, attachment_id: str, *, owner_id: str, conversation_id: str) -> StoredAttachment:
        return await asyncio.to_thread(
            self._get_sync,
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )

    async def delete(self, attachment_id: str, *, owner_id: str, conversation_id: str) -> None:
        await asyncio.to_thread(
            self._delete_sync,
            attachment_id,
            owner_id=owner_id,
            conversation_id=conversation_id,
        )

    async def delete_expired(self, *, now: datetime | None = None) -> int:
        return await asyncio.to_thread(self._delete_expired_sync, now)
