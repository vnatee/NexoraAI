import asyncio
from copy import deepcopy
from io import BytesIO

import pytest

import app as app_module
from mongo_table_connecters import ingestion_jobs as storage
from prepdocslib.fileprocessor import FileProcessor
from prepdocslib.filestrategy import UploadUserFileStrategy
from prepdocslib.listfilestrategy import File
from prepdocslib.page import Page
from prepdocslib.parser import Parser
from prepdocslib.textsplitter import SplitPage


class Result:
    def __init__(self, modified_count=0):
        self.modified_count = modified_count


class Cursor:
    def __init__(self, items):
        self.items = items

    def sort(self, key, direction):
        self.items.sort(key=lambda item: item[key], reverse=direction < 0)
        return self

    def limit(self, count):
        self.items = self.items[:count]
        return self

    def __iter__(self):
        return iter(self.items)


class MemoryCollection:
    def __init__(self):
        self.items = {}

    def insert_one(self, item):
        self.items[item["_id"]] = deepcopy(item)

    def _matches(self, item, query):
        for key, value in query.items():
            if key == "$or":
                if not any(self._matches(item, candidate) for candidate in value):
                    return False
            elif isinstance(value, dict) and "$in" in value:
                if item.get(key) not in value["$in"]:
                    return False
            elif isinstance(value, dict) and "$lte" in value:
                if item.get(key) is None or item.get(key) > value["$lte"]:
                    return False
            elif isinstance(value, dict) and "$gte" in value:
                if item.get(key) is None or item.get(key) < value["$gte"]:
                    return False
            elif isinstance(value, dict) and "$ne" in value:
                if item.get(key) == value["$ne"]:
                    return False
            elif item.get(key) != value:
                return False
        return True

    def find_one(self, query):
        return next((deepcopy(item) for item in self.items.values() if self._matches(item, query)), None)

    def find(self, query):
        return Cursor([deepcopy(item) for item in self.items.values() if self._matches(item, query)])

    def update_one(self, query, update):
        item = next((item for item in self.items.values() if self._matches(item, query)), None)
        if not item:
            return Result()
        item.update(update.get("$set") or {})
        for key, value in (update.get("$inc") or {}).items():
            item[key] = item.get(key, 0) + value
        for key, value in (update.get("$push") or {}).items():
            item.setdefault(key, []).append(value)
        return Result(1)

    def find_one_and_update(self, query, update, return_document=None):
        item = next((item for item in self.items.values() if self._matches(item, query)), None)
        if not item:
            return None
        item.update(update.get("$set") or {})
        for key, value in (update.get("$push") or {}).items():
            item.setdefault(key, []).append(value)
        return deepcopy(item)


def create_job(**overrides):
    return storage.create_ingestion_job(
        owner_id=overrides.get("owner_id", "owner-1"),
        owner_name="owner@example.com",
        scope=overrides.get("scope", "personal"),
        team_id=overrides.get("team_id", ""),
        filename="invoice.pdf",
        storage_path="owner-1/invoice.pdf",
        file_size=123,
        routing_context={"scope": "personal"},
        route={
            "source": "routing_rule",
            "profile": {"_id": "profile-1", "name": "Invoices"},
            "provider": {"_id": "provider-1", "name": "Docling"},
            "rule": {"_id": "rule-1", "name": "PDFs"},
        },
    )


def test_ingestion_job_lifecycle_retry_and_safe_serialization(monkeypatch):
    collection = MemoryCollection()
    monkeypatch.setattr(storage, "collection", collection)
    job = create_job()
    claimed = storage.claim_ingestion_job(job["_id"], "worker-1")
    assert claimed["worker_id"] == "worker-1"
    assert claimed["status"] == "extracting"
    assert storage.claim_ingestion_job(job["_id"], "worker-2") is None
    storage.update_ingestion_job_status(job["_id"], "extracting", worker_id="worker-1")
    storage.update_ingestion_job_status(
        job["_id"],
        "failed",
        error=ValueError("OCR API returned HTTP 400: {'document_text': 'private invoice'} Bearer=secret-token"),
        worker_id="worker-1",
    )

    serialized = storage.serialize_ingestion_job(storage.get_ingestion_job(job["_id"]))
    assert serialized["status"] == "failed"
    assert serialized["provider_name"] == "Docling"
    assert "secret-token" not in serialized["error"]["message"]
    assert "private invoice" not in serialized["error"]["message"]
    assert "storage_path" not in serialized
    assert "routing_context" not in serialized
    assert all(isinstance(stage["at"], str) for stage in serialized["stage_history"])

    assert storage.restart_failed_ingestion_job(job["_id"], "another-owner") is None
    restarted = storage.restart_failed_ingestion_job(job["_id"], "owner-1")
    assert restarted["status"] == "uploaded"
    assert restarted["attempt"] == 2
    assert restarted["error"] is None


def test_release_ingestion_job_requires_owner_worker_and_is_recoverable(monkeypatch):
    collection = MemoryCollection()
    monkeypatch.setattr(storage, "collection", collection)
    job = create_job()
    storage.claim_ingestion_job(job["_id"], "worker-1")

    assert storage.release_ingestion_job(job["_id"], "worker-2") is None
    released = storage.release_ingestion_job(job["_id"], "worker-1")
    assert released["status"] == "uploaded"
    assert released["worker_id"] is None
    assert released["lease_expires_at"] is None
    assert [item["_id"] for item in storage.list_recoverable_ingestion_jobs()] == [job["_id"]]


@pytest.mark.asyncio
async def test_cancelled_ingestion_releases_owned_job(monkeypatch):
    released = []
    job = {
        "_id": "job-1",
        "scope": "personal",
        "owner_id": "owner-1",
        "storage_path": "owner-1/invoice.pdf",
    }

    class CancelledFileClient:
        async def download_file(self):
            raise asyncio.CancelledError

    class FileSystem:
        def get_file_client(self, path):
            assert path == "owner-1/invoice.pdf"
            return CancelledFileClient()

    monkeypatch.setattr(app_module, "claim_ingestion_job", lambda *args, **kwargs: job)
    monkeypatch.setattr(app_module, "check_document_quota", lambda *_args: None)
    monkeypatch.setattr(
        app_module,
        "release_ingestion_job",
        lambda job_id, worker_id: released.append((job_id, worker_id)) or job,
    )
    quart_app = app_module.create_app()
    quart_app.config[app_module.CONFIG_USER_BLOB_CONTAINER_CLIENT] = FileSystem()
    async with quart_app.app_context():
        with pytest.raises(asyncio.CancelledError):
            await app_module._run_ingestion_job("job-1")

    assert released == [("job-1", app_module.INGESTION_WORKER_ID)]


def test_ingestion_jobs_are_filtered_by_owner_scope_and_team(monkeypatch):
    collection = MemoryCollection()
    monkeypatch.setattr(storage, "collection", collection)
    create_job(owner_id="owner-1", scope="team", team_id="team-1")
    create_job(owner_id="owner-2", scope="team", team_id="team-1")
    create_job(owner_id="owner-1", scope="global")
    jobs = storage.list_ingestion_jobs("owner-1", scope="team", team_id="team-1")
    assert len(jobs) == 1
    assert jobs[0]["owner_id"] == "owner-1"


def test_completed_job_leaves_recent_list_but_keeps_indexed_time(monkeypatch):
    collection = MemoryCollection()
    monkeypatch.setattr(storage, "collection", collection)
    job = create_job()
    storage.update_ingestion_job_status(job["_id"], "indexed")
    assert storage.list_ingestion_jobs("owner-1", indexed_visibility_seconds=0) == []
    indexed = storage.latest_indexed_times("personal", ["owner-1/invoice.pdf"], owner_id="owner-1")
    assert indexed["owner-1/invoice.pdf"]


def test_upload_route_pins_resolved_profile_for_background_processing(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "resolve_processing_route",
        lambda **kwargs: {
            "status": "matched",
            "source": "routing_rule",
            "profile": {"_id": "profile-1"},
        },
    )
    context = {"scope": "personal", "team_id": "", "explicit_profile_id": ""}
    app_module._resolve_upload_route("invoice.pdf", context)
    assert context["resolved_profile_id"] == "profile-1"


class StubParser(Parser):
    async def parse(self, content):
        yield Page(0, 0, "searchable text")


class StubSplitter:
    def split_pages(self, pages):
        return [SplitPage(page.page_num, page.text) for page in pages]


class StubSearchManager:
    def __init__(self):
        self.setup_calls = 0

    async def create_index(self):
        self.setup_calls += 1

    async def update_content(self, sections, url=None):
        assert sections


@pytest.mark.asyncio
async def test_upload_strategy_reports_pipeline_stages_in_order():
    stream = BytesIO(b"pdf")
    stream.name = "sample.pdf"
    strategy = object.__new__(UploadUserFileStrategy)
    strategy.image_embeddings = None
    strategy.file_processors = {".pdf": FileProcessor(parser=StubParser(), splitter=StubSplitter())}
    strategy.search_manager = StubSearchManager()
    strategy._search_index_ready = False
    strategy._search_index_lock = asyncio.Lock()
    stages = []

    async def status_callback(status):
        stages.append(status)

    await strategy.add_file(File(stream, acls={"oids": ["owner-1"]}), status_callback=status_callback)
    assert stages == ["extracting", "chunking", "embedding"]
    assert strategy.search_manager.setup_calls == 1


@pytest.mark.asyncio
async def test_ingestion_job_api_uses_authenticated_owner(auth_client, monkeypatch):
    captured = {}

    def fake_list(owner_id, **filters):
        captured.update({"owner_id": owner_id, **filters})
        return []

    monkeypatch.setattr(app_module, "list_ingestion_jobs", fake_list)
    response = await auth_client.get(
        "/ingestion-jobs?scope=team&team_id=team-1&limit=5",
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 200
    assert captured == {"owner_id": "OID_X", "scope": "team", "team_id": "team-1", "limit": 5}
    assert await response.get_json() == {"jobs": []}


@pytest.mark.asyncio
async def test_ingestion_retry_is_scoped_to_authenticated_owner(auth_client, monkeypatch):
    captured = {}

    def fake_restart(job_id, owner_id):
        captured.update({"job_id": job_id, "owner_id": owner_id})
        return None

    monkeypatch.setattr(app_module, "restart_failed_ingestion_job", fake_restart)
    response = await auth_client.post(
        "/ingestion-jobs/job-1/retry",
        headers={"Authorization": "Bearer test"},
    )
    assert response.status_code == 404
    assert captured == {"job_id": "job-1", "owner_id": "OID_X"}
