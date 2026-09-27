from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import app as backend_app
from core.effective_access import AccessControlError
from mongo_table_connecters import web_source_scans


class FakeKnowledgeStore:
    def __init__(self, objects=None, contents=None):
        self.objects = list(objects or [])
        self.contents = dict(contents or {})
        self.puts = []
        self.deleted = []

    async def list(self, scope, *, prefix=""):
        return [item for item in self.objects if item.key.startswith(prefix)]

    async def put(self, scope, key, content, **kwargs):
        data = bytes(content)
        self.contents[(scope, key)] = data
        self.puts.append((scope, key, data, kwargs))
        return key

    async def read(self, scope, key):
        data = self.contents[(scope, key)]
        return SimpleNamespace(data=data, content_type="text/plain", url=key)

    async def delete(self, scope, key):
        self.deleted.append((scope, key))
        self.contents.pop((scope, key), None)


@pytest.mark.asyncio
async def test_web_source_scan_stages_manifest_without_indexing(client, monkeypatch):
    store = FakeKnowledgeStore()
    monkeypatch.setattr(backend_app, "_knowledge_store", lambda: store)
    monkeypatch.setattr(
        backend_app,
        "_require_system_permission",
        lambda *_args, **_kwargs: {"_id": "admin-1", "is_sys_admin": True},
    )
    captured = {}

    def crawler(_url, **kwargs):
        captured.update(kwargs)
        return (
            {
                "status": "success",
                "message": "scan complete",
                "source_url": "https://docs.example.com/",
                "pages_indexed": 1,
                "pages_skipped": 0,
                "bytes_indexed": 8,
                "truncated": False,
                "limit_reason": None,
                "issues": [],
            },
            [{
                "storage_name": "page.txt",
                "text": "evidence",
                "source_url": "https://docs.example.com/",
                "title": "Docs",
                "content_hash": "content-hash",
                "retrieved_at": "2026-09-26T00:00:00+00:00",
            }],
        )

    monkeypatch.setattr(backend_app, "run_scraping_job", crawler)
    monkeypatch.setattr(
        backend_app,
        "create_web_source_scan",
        lambda document: {**document, "status": "ready"},
    )
    indexed = False

    async def should_not_index(*_args, **_kwargs):
        nonlocal indexed
        indexed = True
        return []

    monkeypatch.setattr(backend_app, "upload_many", should_not_index)
    response = await client.post(
        "/web-source-scans",
        json={
            "url": "https://docs.example.com/",
            "crawl_depth": 2,
            "limit_profile": "extended",
        },
    )

    payload = await response.get_json()
    assert response.status_code == 201
    assert payload["pages_found"] == 1
    assert payload["status"] == "ready"
    assert captured == {
        "max_depth": 2,
        "max_pages": 250,
        "max_total_bytes": 100 * 1024 * 1024,
    }
    assert indexed is False
    assert len(store.puts) == 1
    assert "/__staging__/" not in store.puts[0][1]
    assert store.puts[0][1].startswith("__staging__/")


@pytest.mark.asyncio
async def test_confirm_web_source_scan_queues_background_job(client, monkeypatch):
    content = b"verified staged evidence"
    staging_key = "__staging__/scan-1/page.txt"
    scan = {
        "_id": "scan-1",
        "status": "ready",
        "created_by": "admin-1",
        "team_id": None,
        "data_group_ids": [],
        "source_url": "https://docs.example.com/",
        "crawl_depth": 1,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "result": {"status": "success", "message": "verified", "truncated": False},
        "pages": [{
            "staging_key": staging_key,
            "storage_name": "page.txt",
            "source_url": "https://docs.example.com/",
            "title": "Docs",
            "content_hash": "content-hash",
            "staged_hash": hashlib.sha256(content).hexdigest(),
            "retrieved_at": "2026-09-26T00:00:00+00:00",
            "size": len(content),
        }],
    }
    monkeypatch.setattr(
        backend_app,
        "_require_system_permission",
        lambda *_args, **_kwargs: {"_id": "admin-1", "is_sys_admin": True},
    )
    monkeypatch.setattr(backend_app, "get_web_source_scan", lambda _id: scan)
    queued = {
        **scan,
        "status": "queued",
        "attempt": 1,
        "page_progress": [{
            "url": "https://docs.example.com/",
            "status": "queued",
            "attempt": 0,
            "error": None,
        }],
    }
    captured = {}

    def queue(scan_id, selected_urls, *, requested_by):
        captured.update({
            "scan_id": scan_id,
            "selected_urls": selected_urls,
            "requested_by": requested_by,
        })
        return queued

    scheduled = []
    monkeypatch.setattr(backend_app, "queue_web_source_scan", queue)
    monkeypatch.setattr(
        backend_app,
        "_schedule_web_source_index_job",
        lambda scan_id: scheduled.append(scan_id),
    )

    response = await client.post(
        "/web-source-scans/scan-1/confirm",
        json={"selected_urls": ["https://docs.example.com/"]},
    )

    payload = await response.get_json()
    assert response.status_code == 202
    assert payload["status"] == "queued"
    assert payload["pages_selected"] == 1
    assert payload["pages_completed"] == 0
    assert captured == {
        "scan_id": "scan-1",
        "selected_urls": ["https://docs.example.com/"],
        "requested_by": "admin-1",
    }
    assert scheduled == ["scan-1"]


@pytest.mark.asyncio
async def test_confirm_web_source_scan_rejects_url_outside_manifest(client, monkeypatch):
    scan = {
        "_id": "scan-1",
        "status": "ready",
        "team_id": None,
        "data_group_ids": [],
        "pages": [{"source_url": "https://docs.example.com/"}],
    }
    monkeypatch.setattr(backend_app, "get_web_source_scan", lambda _id: scan)
    claimed = False

    def should_not_claim(_id):
        nonlocal claimed
        claimed = True
        return scan

    monkeypatch.setattr(backend_app, "claim_web_source_scan", should_not_claim)

    response = await client.post(
        "/web-source-scans/scan-1/confirm",
        json={"selected_urls": ["https://attacker.example/"]},
    )

    assert response.status_code == 400
    assert "not part of this scan manifest" in (await response.get_json())["error"]
    assert claimed is False


@pytest.mark.asyncio
async def test_confirm_web_source_scan_does_not_read_staging_in_request(client, monkeypatch):
    scan = {
        "_id": "scan-1",
        "status": "ready",
        "created_by": "admin-1",
        "team_id": None,
        "data_group_ids": [],
        "source_url": "https://docs.example.com/",
        "crawl_depth": 1,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "result": {"status": "success", "truncated": False},
        "pages": [{
            "staging_key": "__staging__/scan-1/page.txt",
            "storage_name": "page.txt",
            "source_url": "https://docs.example.com/",
            "title": "Docs",
            "content_hash": "content-hash",
            "staged_hash": "reviewed-hash",
            "retrieved_at": "2026-09-26T00:00:00+00:00",
            "size": 8,
        }],
    }
    monkeypatch.setattr(
        backend_app,
        "_require_system_permission",
        lambda *_args, **_kwargs: {"_id": "admin-1", "is_sys_admin": True},
    )
    monkeypatch.setattr(backend_app, "get_web_source_scan", lambda _id: scan)
    monkeypatch.setattr(
        backend_app,
        "queue_web_source_scan",
        lambda *_args, **_kwargs: {
            **scan,
            "status": "queued",
            "page_progress": [{
                "url": "https://docs.example.com/",
                "status": "queued",
                "attempt": 0,
                "error": None,
            }],
        },
    )
    monkeypatch.setattr(backend_app, "_schedule_web_source_index_job", lambda _id: None)

    response = await client.post("/web-source-scans/scan-1/confirm")

    assert response.status_code == 202
    assert (await response.get_json())["status"] == "queued"


@pytest.mark.asyncio
async def test_team_web_source_rejects_data_group_from_another_team(client, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_require_team_access",
        lambda *_args, **_kwargs: ({"_id": "user-1"}, {"_id": "team-1", "data_group_id": ["group-1"]}),
    )
    monkeypatch.setattr(backend_app, "get_data_group_by_id", lambda _id: {"_id": _id})
    called = False

    def crawler(_url, **_kwargs):
        nonlocal called
        called = True
        return {}, []

    monkeypatch.setattr(backend_app, "run_scraping_job", crawler)
    response = await client.post(
        "/web-source-scans",
        json={"url": "https://docs.example.com/", "team_id": "team-1", "data_groups_id": ["group-2"]},
    )

    assert response.status_code == 403
    assert called is False


@pytest.mark.asyncio
async def test_global_web_source_list_enforces_management_permission(client, monkeypatch):
    def deny(*_args, **_kwargs):
        raise AccessControlError("Manage global uploads permission is required")

    monkeypatch.setattr(backend_app, "_require_system_permission", deny)
    response = await client.get("/list_web_contents")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_legacy_direct_index_route_is_disabled(client):
    response = await client.post(
        "/scrape",
        json={"url": "https://docs.example.com/", "crawl_depth": 1},
    )

    assert response.status_code == 410
    assert "Scan & Verify" in (await response.get_json())["message"]


@pytest.mark.asyncio
async def test_list_web_sources_returns_provenance_summary(client, monkeypatch):
    from datetime import datetime, timezone

    source_url = "https://docs.example.com/product/"
    folder = backend_app.source_folder(source_url)
    objects = [
        SimpleNamespace(
            key=f"{folder}/page-1.txt",
            tags={"status": "indexed", "crawl_depth": "2", "crawl_truncated": "true", "crawl_limit_reason": "total_size"},
            last_modified=datetime(2026, 9, 25, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            key=f"{folder}/page-2.txt",
            tags={"status": "indexed", "crawl_depth": "2", "crawl_truncated": "true", "crawl_limit_reason": "total_size"},
            last_modified=datetime(2026, 9, 25, 1, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            key=f"{folder}/incomplete.txt",
            tags={"status": "processing"},
            last_modified=datetime(2026, 9, 25, 2, tzinfo=timezone.utc),
        ),
    ]
    monkeypatch.setattr(backend_app, "_knowledge_store", lambda: FakeKnowledgeStore(objects))
    monkeypatch.setattr(
        backend_app,
        "_require_system_permission",
        lambda *_args, **_kwargs: {"_id": "admin-1", "is_sys_admin": True},
    )

    response = await client.get("/list_web_contents")

    assert response.status_code == 200
    assert await response.get_json() == [[source_url, [], "2026-09-25T01:00:00+00:00", 2, 2, True, "total_size"]]


@pytest.mark.asyncio
@pytest.mark.parametrize("crawl_depth", [-1, 3, True, "deep"])
async def test_web_source_rejects_invalid_crawl_depth(client, crawl_depth):
    response = await client.post(
        "/web-source-scans",
        json={"url": "https://docs.example.com/", "crawl_depth": crawl_depth},
    )

    assert response.status_code == 400
    assert "crawl_depth must be 0, 1, or 2" in (await response.get_json())["message"]



def test_cleanup_can_reclaim_expired_stale_indexing_scan(monkeypatch):
    captured = {}

    class FakeCollection:
        def find_one_and_update(self, query, update, **_kwargs):
            captured["query"] = query
            captured["update"] = update
            return {"_id": "scan-stale", "status": "deleting"}

    monkeypatch.setattr(web_source_scans, "collection", FakeCollection())
    now = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)

    claimed = web_source_scans.claim_web_source_scan_for_cleanup(
        "scan-stale",
        at=now,
    )

    assert claimed["status"] == "deleting"
    stale_branch = captured["query"]["$or"][1]
    assert stale_branch["status"]["$in"] == ["queued", "indexed", "indexing", "deleting"]
    assert stale_branch["expires_at"]["$lte"] == now
    assert {"lease_expires_at": {"$lte": now}} in stale_branch["$or"]
    assert captured["update"]["$set"]["updated_at"] == now


@pytest.mark.asyncio
async def test_background_web_source_job_tracks_each_page_and_completes(client, monkeypatch):
    del client
    content = b"verified evidence"
    staging_key = "__staging__/scan-worker/page.txt"
    progress = [{
        "url": "https://docs.example.com/",
        "status": "queued",
        "attempt": 0,
        "error": None,
    }]
    scan = {
        "_id": "scan-worker",
        "status": "indexing",
        "worker_id": backend_app.WEB_SOURCE_INDEX_WORKER_ID,
        "created_by": "admin-1",
        "team_id": None,
        "data_group_ids": [],
        "source_url": "https://docs.example.com/",
        "crawl_depth": 1,
        "result": {"truncated": False},
        "pages": [{
            "staging_key": staging_key,
            "storage_name": "page.txt",
            "source_url": "https://docs.example.com/",
            "title": "Docs",
            "content_hash": "content-hash",
            "staged_hash": hashlib.sha256(content).hexdigest(),
            "retrieved_at": "2026-09-26T00:00:00+00:00",
            "size": len(content),
        }],
        "page_progress": progress,
    }
    store = FakeKnowledgeStore(contents={("web_global", staging_key): content})
    monkeypatch.setattr(backend_app, "_knowledge_store", lambda: store)
    monkeypatch.setattr(backend_app, "claim_web_source_scan", lambda *_args: scan)
    monkeypatch.setattr(backend_app, "get_web_source_scan", lambda _id: scan)
    monkeypatch.setattr(backend_app, "heartbeat_web_source_scan", lambda *_args: True)

    def update_page(_scan_id, _worker_id, index, status, **kwargs):
        progress[index]["status"] = status
        progress[index]["error"] = kwargs.get("error")
        if kwargs.get("storage_key"):
            progress[index]["storage_key"] = kwargs["storage_key"]
        return True

    completed = []
    monkeypatch.setattr(backend_app, "update_web_source_page", update_page)
    monkeypatch.setattr(
        backend_app,
        "complete_web_source_scan",
        lambda _scan_id, _worker_id, status, **_kwargs: completed.append(status),
    )
    monkeypatch.setattr(backend_app, "upload_path", lambda *_args, **_kwargs: _async(True))
    monkeypatch.setattr(backend_app, "delete_many", lambda *_args, **_kwargs: _async([]))

    await backend_app._run_web_source_index_job("scan-worker")

    assert progress[0]["status"] == "indexed"
    assert progress[0]["storage_key"].endswith("/page.txt")
    assert completed == ["indexed"]
    assert store.deleted == [("web_global", staging_key)]


@pytest.mark.asyncio
async def test_retry_web_source_job_queues_only_failed_job(client, monkeypatch):
    scan = {
        "_id": "scan-failed",
        "status": "failed",
        "team_id": None,
        "data_group_ids": [],
        "source_url": "https://docs.example.com/",
        "pages": [],
        "page_progress": [],
    }
    monkeypatch.setattr(
        backend_app,
        "_require_system_permission",
        lambda *_args, **_kwargs: {"_id": "admin-1", "is_sys_admin": True},
    )
    monkeypatch.setattr(backend_app, "get_web_source_scan", lambda _id: scan)
    monkeypatch.setattr(
        backend_app,
        "retry_web_source_scan",
        lambda _id: {**scan, "status": "queued", "attempt": 2},
    )
    scheduled = []
    monkeypatch.setattr(
        backend_app,
        "_schedule_web_source_index_job",
        lambda scan_id: scheduled.append(scan_id),
    )

    response = await client.post("/web-source-scans/scan-failed/retry")

    assert response.status_code == 202
    assert (await response.get_json())["status"] == "queued"
    assert scheduled == ["scan-failed"]


async def _async(value):
    return value


async def _capture_async(target, values):
    target.extend(values)
    return [(value, True) for value in values]
