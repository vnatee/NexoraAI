import io
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from core.knowledge_store import MinioKnowledgeObjectStore, create_minio_knowledge_store


class _Response(io.BytesIO):
    def __init__(self, data: bytes, content_type: str):
        super().__init__(data)
        self.headers = {"content-type": content_type}

    def release_conn(self):
        return None


class _FakeMinio:
    def __init__(self):
        self.buckets = set()
        self.objects = {}

    def bucket_exists(self, bucket):
        return bucket in self.buckets

    def make_bucket(self, bucket):
        self.buckets.add(bucket)

    def put_object(self, bucket, name, stream, length, **kwargs):
        self.objects[(bucket, name)] = {
            "data": stream.read(length),
            "content_type": kwargs["content_type"],
            "metadata": kwargs["metadata"],
            "tags": dict(kwargs["tags"]),
            "last_modified": datetime.now(timezone.utc),
        }

    def get_object(self, bucket, name):
        item = self.objects[(bucket, name)]
        return _Response(item["data"], item["content_type"])

    def remove_object(self, bucket, name):
        self.objects.pop((bucket, name), None)

    def list_objects(self, bucket, prefix, recursive):
        assert recursive is True
        return [
            SimpleNamespace(object_name=name, size=len(item["data"]), last_modified=item["last_modified"])
            for (item_bucket, name), item in self.objects.items()
            if item_bucket == bucket and name.startswith(prefix)
        ]

    def get_object_tags(self, bucket, name):
        return self.objects[(bucket, name)]["tags"]

    def set_object_tags(self, bucket, name, tags):
        self.objects[(bucket, name)]["tags"] = dict(tags)


@pytest.mark.asyncio
async def test_minio_knowledge_store_preserves_scope_content_and_tags():
    client = _FakeMinio()
    store = MinioKnowledgeObjectStore(client, "knowledge")

    await store.ensure_ready()
    url = await store.put(
        "team",
        "team-1/folder/report.pdf",
        io.BytesIO(b"report"),
        size=6,
        metadata={"UploadedBy": "user-1"},
        tags={"status": "Pending", "data_groups": "group-1"},
        content_type="application/pdf",
    )

    assert url == "minio://knowledge/team/team-1/folder/report.pdf"
    assert (await store.read("team", "team-1/folder/report.pdf")).data == b"report"
    objects = await store.list("team", prefix="team-1/")
    assert [(item.key, item.size, item.tags["status"]) for item in objects] == [
        ("team-1/folder/report.pdf", 6, "Pending")
    ]

    await store.set_tags("team", "team-1/folder/report.pdf", {"status": "Pass", "data_groups": "group-1"})
    assert (await store.get_tags("team", "team-1/folder/report.pdf"))["status"] == "Pass"

    await store.delete("team", "team-1/folder/report.pdf")
    assert await store.list("team", prefix="team-1/") == []


@pytest.mark.parametrize("key", ["", "../secret", "folder/../secret", "/absolute"])
def test_minio_knowledge_store_rejects_unsafe_keys(key):
    with pytest.raises(ValueError, match="Invalid Knowledge object key"):
        MinioKnowledgeObjectStore._object_name("global", key)


def test_minio_factory_requires_credentials():
    with pytest.raises(ValueError, match="MINIO_ENDPOINT"):
        create_minio_knowledge_store({"MINIO_ENDPOINT": "localhost:9000"})
