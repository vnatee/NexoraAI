from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import math
import os
import re
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol

from azure.core.exceptions import ResourceNotFoundError


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
    backend_name: str

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


def _build_record(
    *,
    owner_id: str,
    conversation_id: str,
    filename: str,
    content_type: str,
    content: bytes,
    ttl: timedelta | None,
    default_ttl: timedelta,
    max_bytes: int,
    now: datetime,
) -> AttachmentRecord:
    owner = _required_identifier(owner_id, "owner_id")
    conversation = _required_identifier(conversation_id, "conversation_id")
    media_type = str(content_type or "").strip().lower()
    if not media_type or len(media_type) > 255:
        raise AttachmentStoreError("content_type is required")
    if not isinstance(content, bytes):
        raise AttachmentStoreError("Attachment content must be bytes")
    if not content or len(content) > max_bytes:
        raise AttachmentStoreError(f"Attachment must contain 1 to {max_bytes} bytes")
    retention = ttl or default_ttl
    if retention <= timedelta(0):
        raise AttachmentStoreError("Attachment TTL must be greater than zero")
    created_at = _utc(now)
    return AttachmentRecord(
        attachment_id=str(uuid.uuid4()),
        owner_id=owner,
        conversation_id=conversation,
        filename=normalize_attachment_filename(filename),
        content_type=media_type,
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        created_at=created_at.isoformat(),
        expires_at=(created_at + retention).isoformat(),
    )


def _authorize(record: AttachmentRecord, owner_id: str, conversation_id: str) -> None:
    owner_matches = hmac.compare_digest(record.owner_id, _required_identifier(owner_id, "owner_id"))
    conversation_matches = hmac.compare_digest(
        record.conversation_id,
        _required_identifier(conversation_id, "conversation_id"),
    )
    if not owner_matches or not conversation_matches:
        raise AttachmentAccessError("Attachment does not belong to this owner and conversation")


class LocalAttachmentStore:
    """Private filesystem adapter for local/container deployments.

    Metadata sidecars are an adapter detail for this first storage slice. The
    public contract keeps callers independent from the later Mongo metadata and
    Azure/S3 object-store adapters.
    """

    backend_name = "local"

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
        record = _build_record(
            owner_id=owner_id,
            conversation_id=conversation_id,
            filename=filename,
            content_type=content_type,
            content=content,
            ttl=ttl,
            default_ttl=self.default_ttl,
            max_bytes=self.max_bytes,
            now=self._clock(),
        )
        payload_path, metadata_path = self._paths(record.attachment_id)
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
        record, payload_path, metadata_path = self._load_record(attachment_id)
        _authorize(record, owner_id, conversation_id)
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
        record, payload_path, metadata_path = self._load_record(attachment_id)
        _authorize(record, owner_id, conversation_id)
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


class AzureBlobAttachmentStore:
    """Private Azure Blob adapter; the container itself must disallow public access."""

    _PREFIX = "chat-attachments/"
    backend_name = "azure"

    def __init__(
        self,
        container: Any,
        *,
        default_ttl: timedelta = DEFAULT_ATTACHMENT_TTL,
        max_bytes: int = DEFAULT_MAX_ATTACHMENT_BYTES,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if container is None:
            raise AttachmentStoreError("Azure attachment container is required")
        if default_ttl <= timedelta(0) or max_bytes <= 0:
            raise AttachmentStoreError("Attachment TTL and size limit must be greater than zero")
        self.container = container
        self.default_ttl = default_ttl
        self.max_bytes = max_bytes
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @classmethod
    def _blob_names(cls, attachment_id: str) -> tuple[str, str]:
        try:
            normalized_id = str(uuid.UUID(str(attachment_id)))
        except (ValueError, AttributeError, TypeError) as error:
            raise AttachmentNotFoundError("Attachment not found") from error
        base = f"{cls._PREFIX}{normalized_id[:2]}/{normalized_id}"
        return f"{base}.bin", f"{base}.json"

    async def _download(self, name: str) -> bytes:
        try:
            stream = await self.container.get_blob_client(name).download_blob()
            return await stream.readall()
        except ResourceNotFoundError as error:
            raise AttachmentNotFoundError("Attachment not found") from error

    async def _delete_names(self, payload_name: str, metadata_name: str) -> None:
        for name in (payload_name, metadata_name):
            try:
                await self.container.get_blob_client(name).delete_blob(delete_snapshots="include")
            except ResourceNotFoundError:
                pass

    async def _load_record(self, attachment_id: str) -> tuple[AttachmentRecord, str, str]:
        payload_name, metadata_name = self._blob_names(attachment_id)
        try:
            document = json.loads((await self._download(metadata_name)).decode("utf-8"))
            record = AttachmentRecord(**document)
        except AttachmentNotFoundError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
            raise AttachmentIntegrityError("Attachment metadata is invalid") from error
        if record.attachment_id != str(uuid.UUID(str(attachment_id))):
            raise AttachmentIntegrityError("Attachment metadata ID does not match its storage key")
        return record, payload_name, metadata_name

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
        record = _build_record(
            owner_id=owner_id,
            conversation_id=conversation_id,
            filename=filename,
            content_type=content_type,
            content=content,
            ttl=ttl,
            default_ttl=self.default_ttl,
            max_bytes=self.max_bytes,
            now=self._clock(),
        )
        payload_name, metadata_name = self._blob_names(record.attachment_id)
        payload_client = self.container.get_blob_client(payload_name)
        metadata_client = self.container.get_blob_client(metadata_name)
        try:
            await payload_client.upload_blob(content, overwrite=False)
            await metadata_client.upload_blob(
                json.dumps(asdict(record), ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                overwrite=False,
            )
        except Exception:
            try:
                await self._delete_names(payload_name, metadata_name)
            except Exception:
                # Periodic orphan cleanup is the fallback when storage is also
                # unavailable during this best-effort rollback.
                pass
            raise
        return record

    async def get(self, attachment_id: str, *, owner_id: str, conversation_id: str) -> StoredAttachment:
        record, payload_name, metadata_name = await self._load_record(attachment_id)
        _authorize(record, owner_id, conversation_id)
        if _parse_timestamp(record.expires_at) <= _utc(self._clock()):
            await self._delete_names(payload_name, metadata_name)
            raise AttachmentExpiredError("Attachment has expired")
        content = await self._download(payload_name)
        if len(content) != record.size or not hmac.compare_digest(hashlib.sha256(content).hexdigest(), record.sha256):
            raise AttachmentIntegrityError("Attachment payload failed its integrity check")
        return StoredAttachment(record=record, content=content)

    async def delete(self, attachment_id: str, *, owner_id: str, conversation_id: str) -> None:
        record, payload_name, metadata_name = await self._load_record(attachment_id)
        _authorize(record, owner_id, conversation_id)
        await self._delete_names(payload_name, metadata_name)

    async def delete_expired(self, *, now: datetime | None = None) -> int:
        cutoff = _utc(now or self._clock())
        deleted = 0
        blobs = [item async for item in self.container.list_blobs(name_starts_with=self._PREFIX)]
        names = {str(item.name) for item in blobs}
        for metadata_name in sorted(name for name in names if name.endswith(".json")):
            payload_name = f"{metadata_name[:-5]}.bin"
            try:
                document = json.loads((await self._download(metadata_name)).decode("utf-8"))
                record = AttachmentRecord(**document)
                expected_payload, expected_metadata = self._blob_names(record.attachment_id)
                if expected_metadata != metadata_name or _parse_timestamp(record.expires_at) <= cutoff:
                    await self._delete_names(payload_name, metadata_name)
                    deleted += 1
            except (AttachmentStoreError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                await self._delete_names(payload_name, metadata_name)
                deleted += 1
        orphan_cutoff = cutoff - self.default_ttl
        for item in blobs:
            name = str(item.name)
            if not name.endswith(".bin") or f"{name[:-4]}.json" in names:
                continue
            modified_at = getattr(item, "last_modified", None)
            if modified_at and _utc(modified_at) <= orphan_cutoff:
                await self._delete_names(name, f"{name[:-4]}.json")
                deleted += 1
        return deleted


def create_attachment_store(
    env: Mapping[str, str],
    *,
    azure_container: Any = None,
    clock: Callable[[], datetime] | None = None,
) -> AttachmentStore | None:
    backend = str(env.get("CHAT_ATTACHMENT_STORE") or "disabled").strip().lower()
    if backend == "disabled":
        return None
    try:
        ttl_hours = float(env.get("CHAT_ATTACHMENT_TTL_HOURS") or 24)
        max_megabytes = float(env.get("CHAT_ATTACHMENT_MAX_MB") or 25)
        if not math.isfinite(ttl_hours) or not math.isfinite(max_megabytes):
            raise ValueError
        ttl = timedelta(hours=ttl_hours)
        max_bytes = int(max_megabytes * 1024 * 1024)
    except (OverflowError, ValueError) as error:
        raise AttachmentStoreError("Attachment TTL and size settings must be numeric") from error
    if backend == "local":
        root = str(env.get("CHAT_ATTACHMENT_LOCAL_PATH") or "").strip()
        if not root:
            raise AttachmentStoreError("CHAT_ATTACHMENT_LOCAL_PATH is required for local attachment storage")
        return LocalAttachmentStore(root, default_ttl=ttl, max_bytes=max_bytes, clock=clock)
    if backend == "azure":
        return AzureBlobAttachmentStore(
            azure_container,
            default_ttl=ttl,
            max_bytes=max_bytes,
            clock=clock,
        )
    raise AttachmentStoreError("CHAT_ATTACHMENT_STORE must be disabled, local, or azure")
