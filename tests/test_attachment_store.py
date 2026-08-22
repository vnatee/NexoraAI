import json
import os
import stat
from datetime import datetime, timedelta, timezone

import pytest

from core.attachment_store import (
    AttachmentAccessError,
    AttachmentExpiredError,
    AttachmentIntegrityError,
    AttachmentNotFoundError,
    AttachmentStoreError,
    AzureBlobAttachmentStore,
    LocalAttachmentStore,
    create_attachment_store,
    normalize_attachment_filename,
)


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


class FakeDownloader:
    def __init__(self, content):
        self.content = content

    async def readall(self):
        return self.content


class FakeBlobClient:
    def __init__(self, container, name):
        self.container = container
        self.name = name

    async def upload_blob(self, content, *, overwrite):
        assert overwrite is False
        if self.name in self.container.blobs:
            raise RuntimeError("blob already exists")
        self.container.blobs[self.name] = bytes(content)
        self.container.modified[self.name] = NOW

    async def download_blob(self):
        from azure.core.exceptions import ResourceNotFoundError

        if self.name not in self.container.blobs:
            raise ResourceNotFoundError("missing")
        return FakeDownloader(self.container.blobs[self.name])

    async def delete_blob(self, *, delete_snapshots):
        from azure.core.exceptions import ResourceNotFoundError

        assert delete_snapshots == "include"
        if self.name not in self.container.blobs:
            raise ResourceNotFoundError("missing")
        del self.container.blobs[self.name]
        self.container.modified.pop(self.name, None)


class FakeBlobItem:
    def __init__(self, name, last_modified):
        self.name = name
        self.last_modified = last_modified


class FakeContainer:
    def __init__(self):
        self.blobs = {}
        self.modified = {}

    def get_blob_client(self, name):
        return FakeBlobClient(self, name)

    async def list_blobs(self, *, name_starts_with):
        for name in sorted(self.blobs):
            if name.startswith(name_starts_with):
                yield FakeBlobItem(name, self.modified[name])


@pytest.fixture
def store(tmp_path):
    return LocalAttachmentStore(tmp_path / "attachments", clock=lambda: NOW)


@pytest.mark.asyncio
async def test_local_store_round_trip_is_private_and_normalizes_filename(store):
    record = await store.put(
        owner_id="user-1",
        conversation_id="conversation-1",
        filename="../../ Specs: Q3?.pdf",
        content_type="Application/PDF",
        content=b"document bytes",
    )

    stored = await store.get(
        record.attachment_id,
        owner_id="user-1",
        conversation_id="conversation-1",
    )

    assert stored.content == b"document bytes"
    assert stored.record.filename == "Specs_ Q3_.pdf"
    assert stored.record.content_type == "application/pdf"
    payload_path, metadata_path = store._paths(record.attachment_id)
    assert stat.S_IMODE(payload_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(metadata_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.root.stat().st_mode) == 0o700


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("owner_id", "conversation_id"),
    [("user-2", "conversation-1"), ("user-1", "conversation-2")],
)
async def test_local_store_enforces_owner_and_conversation_acl(store, owner_id, conversation_id):
    record = await store.put(
        owner_id="user-1",
        conversation_id="conversation-1",
        filename="private.pdf",
        content_type="application/pdf",
        content=b"private",
    )

    with pytest.raises(AttachmentAccessError):
        await store.get(record.attachment_id, owner_id=owner_id, conversation_id=conversation_id)
    with pytest.raises(AttachmentAccessError):
        await store.delete(record.attachment_id, owner_id=owner_id, conversation_id=conversation_id)


@pytest.mark.asyncio
async def test_local_store_expires_on_read_and_removes_files(tmp_path):
    current = NOW
    store = LocalAttachmentStore(tmp_path / "attachments", clock=lambda: current)
    record = await store.put(
        owner_id="user-1",
        conversation_id="conversation-1",
        filename="short-lived.txt",
        content_type="text/plain",
        content=b"temporary",
        ttl=timedelta(minutes=5),
    )
    current = NOW + timedelta(minutes=6)

    with pytest.raises(AttachmentExpiredError):
        await store.get(record.attachment_id, owner_id="user-1", conversation_id="conversation-1")
    with pytest.raises(AttachmentNotFoundError):
        await store.get(record.attachment_id, owner_id="user-1", conversation_id="conversation-1")


@pytest.mark.asyncio
async def test_local_store_cleanup_deletes_only_expired_records(tmp_path):
    store = LocalAttachmentStore(tmp_path / "attachments", clock=lambda: NOW)
    expired = await store.put(
        owner_id="user-1",
        conversation_id="conversation-1",
        filename="expired.txt",
        content_type="text/plain",
        content=b"old",
        ttl=timedelta(minutes=1),
    )
    active = await store.put(
        owner_id="user-1",
        conversation_id="conversation-1",
        filename="active.txt",
        content_type="text/plain",
        content=b"new",
        ttl=timedelta(hours=2),
    )

    assert await store.delete_expired(now=NOW + timedelta(minutes=2)) == 1
    with pytest.raises(AttachmentNotFoundError):
        await store.get(expired.attachment_id, owner_id="user-1", conversation_id="conversation-1")
    assert (await store.get(active.attachment_id, owner_id="user-1", conversation_id="conversation-1")).content == b"new"


@pytest.mark.asyncio
async def test_local_store_cleanup_removes_corrupt_metadata_and_old_orphans(tmp_path):
    store = LocalAttachmentStore(tmp_path / "attachments", clock=lambda: NOW)
    corrupt = await store.put(
        owner_id="user-1",
        conversation_id="conversation-1",
        filename="corrupt.txt",
        content_type="text/plain",
        content=b"corrupt",
    )
    corrupt_payload, corrupt_metadata = store._paths(corrupt.attachment_id)
    corrupt_metadata.write_text("not-json", encoding="utf-8")

    orphan_id = "9aee2161-d67f-45a1-b4a5-7d2042dd1c26"
    orphan_payload, _ = store._paths(orphan_id)
    orphan_payload.parent.mkdir(parents=True, exist_ok=True)
    orphan_payload.write_bytes(b"orphan")
    old_timestamp = (NOW - timedelta(hours=25)).timestamp()
    os.utime(orphan_payload, (old_timestamp, old_timestamp))

    assert await store.delete_expired(now=NOW) == 2
    assert not corrupt_payload.exists()
    assert not corrupt_metadata.exists()
    assert not orphan_payload.exists()


@pytest.mark.asyncio
async def test_local_store_detects_payload_tampering(store):
    record = await store.put(
        owner_id="user-1",
        conversation_id="conversation-1",
        filename="file.txt",
        content_type="text/plain",
        content=b"original",
    )
    payload_path, _ = store._paths(record.attachment_id)
    payload_path.write_bytes(b"modified")

    with pytest.raises(AttachmentIntegrityError):
        await store.get(record.attachment_id, owner_id="user-1", conversation_id="conversation-1")


@pytest.mark.asyncio
async def test_local_store_detects_metadata_id_tampering(store):
    record = await store.put(
        owner_id="user-1",
        conversation_id="conversation-1",
        filename="file.txt",
        content_type="text/plain",
        content=b"original",
    )
    _, metadata_path = store._paths(record.attachment_id)
    document = json.loads(metadata_path.read_text(encoding="utf-8"))
    document["attachment_id"] = "9aee2161-d67f-45a1-b4a5-7d2042dd1c26"
    metadata_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(AttachmentIntegrityError):
        await store.get(record.attachment_id, owner_id="user-1", conversation_id="conversation-1")


@pytest.mark.asyncio
async def test_local_store_rejects_invalid_or_oversized_input(tmp_path):
    store = LocalAttachmentStore(tmp_path / "attachments", max_bytes=4, clock=lambda: NOW)

    with pytest.raises(AttachmentStoreError):
        await store.put(
            owner_id="",
            conversation_id="conversation-1",
            filename="file.txt",
            content_type="text/plain",
            content=b"data",
        )
    with pytest.raises(AttachmentStoreError):
        await store.put(
            owner_id="user-1",
            conversation_id="conversation-1",
            filename="file.txt",
            content_type="text/plain",
            content=b"large",
        )


@pytest.mark.asyncio
async def test_local_store_rejects_non_uuid_lookup(store):
    with pytest.raises(AttachmentNotFoundError):
        await store.get("../../secret", owner_id="user-1", conversation_id="conversation-1")


def test_normalize_attachment_filename_handles_windows_paths_and_empty_values():
    assert normalize_attachment_filename(r"C:\Users\owner\report.docx") == "report.docx"
    assert normalize_attachment_filename("../..") == "attachment"


@pytest.mark.asyncio
async def test_azure_store_round_trip_acl_and_delete():
    container = FakeContainer()
    store = AzureBlobAttachmentStore(container, clock=lambda: NOW)
    record = await store.put(
        owner_id="user-1",
        conversation_id="conversation-1",
        filename="private.pdf",
        content_type="application/pdf",
        content=b"private document",
    )

    assert all(name.startswith("chat-attachments/") for name in container.blobs)
    assert not any(record.filename in name for name in container.blobs)
    assert (
        await store.get(record.attachment_id, owner_id="user-1", conversation_id="conversation-1")
    ).content == b"private document"
    with pytest.raises(AttachmentAccessError):
        await store.get(record.attachment_id, owner_id="user-2", conversation_id="conversation-1")

    await store.delete(record.attachment_id, owner_id="user-1", conversation_id="conversation-1")
    assert container.blobs == {}


@pytest.mark.asyncio
async def test_azure_store_expires_on_read_and_detects_tampering():
    current = NOW
    container = FakeContainer()
    store = AzureBlobAttachmentStore(container, clock=lambda: current)
    expired = await store.put(
        owner_id="user-1",
        conversation_id="conversation-1",
        filename="temporary.txt",
        content_type="text/plain",
        content=b"temporary",
        ttl=timedelta(minutes=1),
    )
    current = NOW + timedelta(minutes=2)
    with pytest.raises(AttachmentExpiredError):
        await store.get(expired.attachment_id, owner_id="user-1", conversation_id="conversation-1")

    current = NOW
    tampered = await store.put(
        owner_id="user-1",
        conversation_id="conversation-1",
        filename="tampered.txt",
        content_type="text/plain",
        content=b"original",
    )
    payload_name, _ = store._blob_names(tampered.attachment_id)
    container.blobs[payload_name] = b"modified"
    with pytest.raises(AttachmentIntegrityError):
        await store.get(tampered.attachment_id, owner_id="user-1", conversation_id="conversation-1")


@pytest.mark.asyncio
async def test_azure_store_cleanup_removes_expired_corrupt_and_old_orphan_blobs():
    container = FakeContainer()
    store = AzureBlobAttachmentStore(container, clock=lambda: NOW)
    expired = await store.put(
        owner_id="user-1",
        conversation_id="conversation-1",
        filename="expired.txt",
        content_type="text/plain",
        content=b"expired",
        ttl=timedelta(minutes=1),
    )
    corrupt = await store.put(
        owner_id="user-1",
        conversation_id="conversation-1",
        filename="corrupt.txt",
        content_type="text/plain",
        content=b"corrupt",
    )
    _, corrupt_metadata = store._blob_names(corrupt.attachment_id)
    container.blobs[corrupt_metadata] = b"not-json"
    orphan_name = "chat-attachments/9a/9aee2161-d67f-45a1-b4a5-7d2042dd1c26.bin"
    container.blobs[orphan_name] = b"orphan"
    container.modified[orphan_name] = NOW - timedelta(hours=25)

    assert await store.delete_expired(now=NOW + timedelta(minutes=2)) == 3
    assert container.blobs == {}
    with pytest.raises(AttachmentNotFoundError):
        await store.get(expired.attachment_id, owner_id="user-1", conversation_id="conversation-1")


def test_attachment_store_factory_defaults_to_disabled_and_builds_backends(tmp_path):
    assert create_attachment_store({}) is None
    local = create_attachment_store(
        {
            "CHAT_ATTACHMENT_STORE": "local",
            "CHAT_ATTACHMENT_LOCAL_PATH": str(tmp_path / "attachments"),
            "CHAT_ATTACHMENT_TTL_HOURS": "2",
            "CHAT_ATTACHMENT_MAX_MB": "3",
        },
        clock=lambda: NOW,
    )
    assert isinstance(local, LocalAttachmentStore)
    assert local.default_ttl == timedelta(hours=2)
    assert local.max_bytes == 3 * 1024 * 1024

    container = FakeContainer()
    azure = create_attachment_store(
        {"CHAT_ATTACHMENT_STORE": "azure"},
        azure_container=container,
        clock=lambda: NOW,
    )
    assert isinstance(azure, AzureBlobAttachmentStore)
    assert azure.container is container


@pytest.mark.parametrize(
    "env",
    [
        {"CHAT_ATTACHMENT_STORE": "local"},
        {"CHAT_ATTACHMENT_STORE": "unknown"},
        {"CHAT_ATTACHMENT_STORE": "local", "CHAT_ATTACHMENT_LOCAL_PATH": "/tmp/x", "CHAT_ATTACHMENT_TTL_HOURS": "nope"},
        {"CHAT_ATTACHMENT_STORE": "local", "CHAT_ATTACHMENT_LOCAL_PATH": "/tmp/x", "CHAT_ATTACHMENT_MAX_MB": "nan"},
    ],
)
def test_attachment_store_factory_rejects_invalid_configuration(env):
    with pytest.raises(AttachmentStoreError):
        create_attachment_store(env)


def test_attachment_store_factory_requires_azure_container():
    with pytest.raises(AttachmentStoreError):
        create_attachment_store({"CHAT_ATTACHMENT_STORE": "azure"})
