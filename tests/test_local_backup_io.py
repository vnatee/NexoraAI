import io
import json
import tarfile
from types import SimpleNamespace

from minio.deleteobjects import DeleteObject

from core import local_backup_io


def _stream_archive(index: dict, member_name: str, payload: bytes) -> io.BytesIO:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        index_payload = json.dumps(index).encode("utf-8")
        index_info = tarfile.TarInfo("index.json")
        index_info.size = len(index_payload)
        archive.addfile(index_info, io.BytesIO(index_payload))
        payload_info = tarfile.TarInfo(member_name)
        payload_info.size = len(payload)
        archive.addfile(payload_info, io.BytesIO(payload))
    output.seek(0)
    return output


def test_import_minio_restores_metadata_tags_and_removes_stale_objects(monkeypatch):
    class FakeMinio:
        removed = []
        uploaded = []

        def bucket_exists(self, _bucket):
            return True

        def list_objects(self, _bucket, recursive):
            assert recursive is True
            return [SimpleNamespace(object_name="stale.txt")]

        def remove_objects(self, _bucket, objects):
            self.removed = list(objects)
            return iter(())

        def put_object(self, bucket, key, payload, size, **kwargs):
            self.uploaded.append((bucket, key, payload.read(size), kwargs))

    client = FakeMinio()
    monkeypatch.setattr(local_backup_io, "_minio_client", lambda: client)
    monkeypatch.setenv("MINIO_KNOWLEDGE_BUCKET", "knowledge")
    archive = _stream_archive(
        {
            "format_version": 1,
            "bucket": "knowledge",
            "objects": [{
                "key": "team/report.pdf",
                "blob": "objects/blob-1",
                "size": 3,
                "content_type": "application/pdf",
                "metadata": {"uploadedby": "user-1"},
                "tags": {"status": "Pass"},
            }],
        },
        "objects/blob-1",
        b"pdf",
    )

    local_backup_io.import_minio(archive)

    assert len(client.removed) == 1
    assert isinstance(client.removed[0], DeleteObject)
    assert client.removed[0].name == "stale.txt"
    bucket, key, payload, kwargs = client.uploaded[0]
    assert (bucket, key, payload) == ("knowledge", "team/report.pdf", b"pdf")
    assert kwargs["metadata"] == {"uploadedby": "user-1"}
    assert dict(kwargs["tags"]) == {"status": "Pass"}


def test_import_qdrant_replaces_existing_collections_from_snapshot(monkeypatch):
    calls = []

    class Response:
        def __init__(self, payload=None):
            self.payload = payload or {}

        def json(self):
            return self.payload

        def close(self):
            return None

    def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if method == "GET" and path == "/collections":
            return Response({"result": {"collections": [{"name": "nexora-knowledge"}, {"name": "shared-other"}]}})
        return Response()

    monkeypatch.setattr(local_backup_io, "_qdrant_request", request)
    uploaded = []
    monkeypatch.setattr(
        local_backup_io,
        "_upload_qdrant_snapshot",
        lambda collection, name, source, size: uploaded.append((collection, name, source.read(size))),
    )
    archive = _stream_archive(
        {
            "format_version": 1,
            "collections": [{
                "collection": "nexora-knowledge",
                "snapshot": "snapshot-1.snapshot",
                "blob": "snapshots/blob-1.snapshot",
            }],
        },
        "snapshots/blob-1.snapshot",
        b"snapshot",
    )

    local_backup_io.import_qdrant(archive)

    assert any(method == "DELETE" and path == "/collections/nexora-knowledge" for method, path, _kwargs in calls)
    assert not any(method == "DELETE" and path == "/collections/shared-other" for method, path, _kwargs in calls)
    assert uploaded == [("nexora-knowledge", "snapshot-1.snapshot", b"snapshot")]


def test_qdrant_snapshot_upload_streams_with_bounded_reads(monkeypatch):
    connections = []

    class Response:
        status = 200

        def read(self):
            return b"ok"

    class Connection:
        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.headers = {}
            self.sent = []
            connections.append(self)

        def putrequest(self, method, path):
            self.method = method
            self.path = path

        def putheader(self, key, value):
            self.headers[key] = value

        def endheaders(self):
            return None

        def send(self, value):
            self.sent.append(value)

        def getresponse(self):
            return Response()

        def close(self):
            return None

    monkeypatch.setattr(local_backup_io.http.client, "HTTPConnection", Connection)
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setenv("QDRANT_API_KEY", "test-key")

    local_backup_io._upload_qdrant_snapshot("knowledge", "snapshot.bin", io.BytesIO(b"payload"), 7)

    connection = connections[0]
    assert connection.path == "/collections/knowledge/snapshots/upload?priority=snapshot"
    assert connection.headers["api-key"] == "test-key"
    assert b"payload" in connection.sent
    assert int(connection.headers["Content-Length"]) == sum(len(item) for item in connection.sent)
