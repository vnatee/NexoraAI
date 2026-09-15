import io
from datetime import datetime

import pytest
from pypdf import PdfWriter
from quart.datastructures import FileStorage

import app as app_module
from core.attachment_store import LocalAttachmentStore
from core.document_attachments import DisabledMalwareScanner, MalwareDetectedError


CONVERSATION_ID = "9aee2161-d67f-45a1-b4a5-7d2042dd1c26"
UPLOAD_ID = "00ec4e94-1e98-4bc5-8a7a-982f33c6b7af"
HEADERS = {"Authorization": "Bearer test"}


def _pdf_bytes():
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(output)
    return output.getvalue()


class MemoryMetadata:
    def __init__(self):
        self.items = {}

    def create(self, record, **values):
        item = {
            "_id": record.attachment_id,
            "owner_id": record.owner_id,
            "conversation_id": record.conversation_id,
            "filename": record.filename,
            "content_type": record.content_type,
            "size": record.size,
            "status": "stored",
            "error_code": None,
            "page_count": values["page_count"],
            "scan_status": values["scan_status"],
            "upload_id": values["upload_id"],
            "created_at": datetime.fromisoformat(record.created_at),
            "expires_at": datetime.fromisoformat(record.expires_at),
            "delete_at": None,
        }
        self.items[record.attachment_id] = item
        return item

    def by_upload(self, upload_id, *, owner_id, conversation_id):
        return next(
            (
                item
                for item in self.items.values()
                if item["upload_id"] == upload_id
                and item["owner_id"] == owner_id
                and item["conversation_id"] == conversation_id
                and item["delete_at"] is None
            ),
            None,
        )

    def get(self, attachment_id, *, owner_id, conversation_id):
        item = self.items.get(attachment_id)
        if (
            not item
            or item["owner_id"] != owner_id
            or item["conversation_id"] != conversation_id
            or item["delete_at"] is not None
        ):
            return None
        return item

    def list(self, *, owner_id, conversation_id, limit):
        return [
            item
            for item in self.items.values()
            if item["owner_id"] == owner_id
            and item["conversation_id"] == conversation_id
            and item["delete_at"] is None
        ][:limit]

    def delete(self, attachment_id, *, owner_id, conversation_id):
        item = self.get(attachment_id, owner_id=owner_id, conversation_id=conversation_id)
        if not item:
            return False
        item["delete_at"] = item["created_at"]
        return True


def _install_private_attachment_services(auth_client, monkeypatch, tmp_path):
    store = LocalAttachmentStore(tmp_path / "chat-documents")
    metadata = MemoryMetadata()
    auth_client.app.config[app_module.CONFIG_CHAT_ATTACHMENT_STORE] = store
    auth_client.app.config[app_module.CONFIG_CHAT_ATTACHMENT_SCANNER] = DisabledMalwareScanner()
    monkeypatch.setattr(app_module, "create_attachment_metadata", metadata.create)
    monkeypatch.setattr(app_module, "get_attachment_metadata_by_upload_id", metadata.by_upload)
    monkeypatch.setattr(app_module, "get_attachment_metadata", metadata.get)
    monkeypatch.setattr(app_module, "list_attachment_metadata", metadata.list)
    monkeypatch.setattr(app_module, "soft_delete_attachment_metadata", metadata.delete)
    monkeypatch.setattr(app_module, "_schedule_chat_attachment_extraction", lambda *args, **kwargs: None)
    return store, metadata


def _upload_file(content=None, *, filename="requirements.pdf", content_type="application/pdf"):
    return FileStorage(
        io.BytesIO(content if content is not None else _pdf_bytes()),
        filename=filename,
        content_type=content_type,
    )


@pytest.mark.asyncio
async def test_chat_document_upload_requires_configured_private_store(auth_client):
    response = await auth_client.post(
        "/chat/attachments",
        headers=HEADERS,
        form={"conversation_id": CONVERSATION_ID, "upload_id": UPLOAD_ID},
        files={"file": _upload_file()},
    )

    assert response.status_code == 503
    assert "not enabled" in (await response.get_json())["error"]


@pytest.mark.asyncio
async def test_chat_document_upload_is_idempotent_and_listed(auth_client, monkeypatch, tmp_path):
    store, metadata = _install_private_attachment_services(auth_client, monkeypatch, tmp_path)

    first = await auth_client.post(
        "/chat/attachments",
        headers=HEADERS,
        form={"conversation_id": CONVERSATION_ID, "upload_id": UPLOAD_ID},
        files={"file": _upload_file()},
    )
    second = await auth_client.post(
        "/chat/attachments",
        headers=HEADERS,
        form={"conversation_id": CONVERSATION_ID, "upload_id": UPLOAD_ID},
        files={"file": _upload_file()},
    )

    assert first.status_code == 201
    assert second.status_code == 200
    first_body = await first.get_json()
    second_body = await second.get_json()
    assert first_body["duplicate"] is False
    assert second_body == {"attachment": first_body["attachment"], "duplicate": True}
    assert first_body["attachment"]["page_count"] == 1
    assert first_body["attachment"]["scan_status"] == "not_configured"
    assert len(metadata.items) == 1
    assert len(list(store.root.glob("*/*.bin"))) == 1

    listed = await auth_client.get(
        f"/chat/attachments?conversation_id={CONVERSATION_ID}",
        headers=HEADERS,
    )
    assert listed.status_code == 200
    assert (await listed.get_json())["attachments"] == [first_body["attachment"]]


@pytest.mark.asyncio
async def test_chat_document_upload_respects_agent_policy(auth_client, monkeypatch, tmp_path):
    _install_private_attachment_services(auth_client, monkeypatch, tmp_path)
    monkeypatch.setattr(
        app_module,
        "get_agent_by_id",
        lambda agent_id: {"_id": agent_id, "config": {"document_attachments_enabled": False}},
    )

    response = await auth_client.post(
        "/chat/attachments",
        headers=HEADERS,
        form={"conversation_id": CONVERSATION_ID, "upload_id": UPLOAD_ID, "agent_id": "agent-1"},
        files={"file": _upload_file()},
    )

    assert response.status_code == 403
    assert await response.get_json() == {"error": "Document attachments are disabled for this agent"}


@pytest.mark.asyncio
async def test_chat_document_upload_rejects_invalid_content_without_storing(auth_client, monkeypatch, tmp_path):
    store, metadata = _install_private_attachment_services(auth_client, monkeypatch, tmp_path)

    response = await auth_client.post(
        "/chat/attachments",
        headers=HEADERS,
        form={"conversation_id": CONVERSATION_ID, "upload_id": UPLOAD_ID},
        files={"file": _upload_file(b"not-pdf")},
    )

    assert response.status_code == 400
    assert metadata.items == {}
    assert list(store.root.glob("*/*.bin")) == []


@pytest.mark.asyncio
async def test_chat_document_upload_rolls_back_when_metadata_write_fails(auth_client, monkeypatch, tmp_path):
    store, metadata = _install_private_attachment_services(auth_client, monkeypatch, tmp_path)

    def fail_create(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(app_module, "create_attachment_metadata", fail_create)
    response = await auth_client.post(
        "/chat/attachments",
        headers=HEADERS,
        form={"conversation_id": CONVERSATION_ID, "upload_id": UPLOAD_ID},
        files={"file": _upload_file()},
    )

    assert response.status_code == 500
    assert metadata.items == {}
    assert list(store.root.glob("*/*.bin")) == []


@pytest.mark.asyncio
async def test_chat_document_delete_is_conversation_scoped(auth_client, monkeypatch, tmp_path):
    store, metadata = _install_private_attachment_services(auth_client, monkeypatch, tmp_path)
    uploaded = await auth_client.post(
        "/chat/attachments",
        headers=HEADERS,
        form={"conversation_id": CONVERSATION_ID, "upload_id": UPLOAD_ID},
        files={"file": _upload_file()},
    )
    attachment_id = (await uploaded.get_json())["attachment"]["id"]

    wrong_conversation = await auth_client.delete(
        f"/chat/attachments/{attachment_id}",
        headers=HEADERS,
        json={"conversation_id": "cf675f64-292b-462a-bc48-0e66d2944a93"},
    )
    deleted = await auth_client.delete(
        f"/chat/attachments/{attachment_id}",
        headers=HEADERS,
        json={"conversation_id": CONVERSATION_ID},
    )

    assert wrong_conversation.status_code == 404
    assert deleted.status_code == 204
    assert metadata.items[attachment_id]["delete_at"] is not None
    assert list(store.root.glob("*/*.bin")) == []


@pytest.mark.asyncio
async def test_chat_document_content_is_ready_and_conversation_scoped(auth_client, monkeypatch, tmp_path):
    _, metadata = _install_private_attachment_services(auth_client, monkeypatch, tmp_path)
    content = _pdf_bytes()
    uploaded = await auth_client.post(
        "/chat/attachments",
        headers=HEADERS,
        form={"conversation_id": CONVERSATION_ID, "upload_id": UPLOAD_ID},
        files={"file": _upload_file(content)},
    )
    attachment_id = (await uploaded.get_json())["attachment"]["id"]

    unavailable = await auth_client.get(
        f"/chat/attachments/{attachment_id}/content?conversation_id={CONVERSATION_ID}",
        headers=HEADERS,
    )
    assert unavailable.status_code == 404

    metadata.items[attachment_id]["status"] = "ready"
    wrong_conversation = await auth_client.get(
        f"/chat/attachments/{attachment_id}/content?conversation_id=cf675f64-292b-462a-bc48-0e66d2944a93",
        headers=HEADERS,
    )
    opened = await auth_client.get(
        f"/chat/attachments/{attachment_id}/content?conversation_id={CONVERSATION_ID}",
        headers=HEADERS,
    )

    assert wrong_conversation.status_code == 404
    assert opened.status_code == 200
    assert await opened.get_data() == content
    assert opened.headers["Cache-Control"] == "private, no-store"
    assert opened.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.asyncio
async def test_chat_document_upload_blocks_malware(auth_client, monkeypatch, tmp_path):
    store, metadata = _install_private_attachment_services(auth_client, monkeypatch, tmp_path)

    class BlockingScanner:
        async def scan(self, **kwargs):
            raise MalwareDetectedError("Document failed the security scan")

    auth_client.app.config[app_module.CONFIG_CHAT_ATTACHMENT_SCANNER] = BlockingScanner()
    response = await auth_client.post(
        "/chat/attachments",
        headers=HEADERS,
        form={"conversation_id": CONVERSATION_ID, "upload_id": UPLOAD_ID},
        files={"file": _upload_file()},
    )

    assert response.status_code == 422
    assert metadata.items == {}
    assert list(store.root.glob("*/*.bin")) == []
