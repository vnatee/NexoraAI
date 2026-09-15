from __future__ import annotations

import hashlib
import http.client
import io
import json
import os
import sys
import tarfile
import uuid
from typing import Any, BinaryIO
from urllib.parse import quote, urlencode, urlsplit

import requests
from minio import Minio
from minio.datatypes import Tags
from minio.deleteobjects import DeleteObject

FORMAT_VERSION = 1


def _add_json(archive: tarfile.TarFile, name: str, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = 0o600
    archive.addfile(info, io.BytesIO(payload))


def _minio_client() -> Minio:
    endpoint = os.environ["MINIO_ENDPOINT"]
    return Minio(
        endpoint,
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.environ.get("MINIO_SECURE", "false").strip().lower() == "true",
    )


def _object_metadata(stat: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_key, raw_value in dict(stat.metadata or {}).items():
        key = str(raw_key).lower()
        if key.startswith("x-amz-meta-"):
            result[key.removeprefix("x-amz-meta-")] = str(raw_value)
    return result


def export_minio(output: BinaryIO) -> None:
    client = _minio_client()
    bucket = os.environ.get("MINIO_KNOWLEDGE_BUCKET", "nexora-knowledge")
    objects = []
    for item in client.list_objects(bucket, recursive=True):
        stat = client.stat_object(bucket, item.object_name)
        try:
            tags = dict(client.get_object_tags(bucket, item.object_name))
        except Exception:
            tags = {}
        objects.append({
            "key": item.object_name,
            "blob": f"objects/{hashlib.sha256(item.object_name.encode('utf-8')).hexdigest()}",
            "size": int(stat.size),
            "content_type": str(stat.content_type or "application/octet-stream"),
            "metadata": _object_metadata(stat),
            "tags": {str(key): str(value) for key, value in tags.items()},
        })

    with tarfile.open(fileobj=output, mode="w|gz") as archive:
        _add_json(archive, "index.json", {"format_version": FORMAT_VERSION, "bucket": bucket, "objects": objects})
        for item in objects:
            response = client.get_object(bucket, item["key"])
            try:
                info = tarfile.TarInfo(item["blob"])
                info.size = item["size"]
                info.mode = 0o600
                archive.addfile(info, response)
            finally:
                response.close()
                response.release_conn()


def import_minio(source: BinaryIO) -> None:
    client = _minio_client()
    with tarfile.open(fileobj=source, mode="r|gz") as archive:
        first = archive.next()
        if first is None or first.name != "index.json" or not first.isfile():
            raise ValueError("MinIO backup is missing index.json")
        index_file = archive.extractfile(first)
        if index_file is None:
            raise ValueError("Unable to read MinIO backup index")
        index = json.load(index_file)
        if index.get("format_version") != FORMAT_VERSION:
            raise ValueError("Unsupported MinIO backup format")
        bucket = os.environ.get("MINIO_KNOWLEDGE_BUCKET", "nexora-knowledge")
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        entries = {item["blob"]: item for item in index.get("objects", [])}
        expected_keys = {item["key"] for item in entries.values()}
        stale_keys = [item.object_name for item in client.list_objects(bucket, recursive=True) if item.object_name not in expected_keys]
        if stale_keys:
            errors = list(client.remove_objects(bucket, [DeleteObject(key) for key in stale_keys]))
            if errors:
                raise RuntimeError(f"Unable to remove {len(errors)} stale MinIO objects")

        while (member := archive.next()) is not None:
            if member.name.startswith("/") or ".." in member.name.split("/") or not member.isfile():
                raise ValueError(f"Unsafe MinIO backup member: {member.name}")
            entry = entries.get(member.name)
            if entry is None or int(entry.get("size", -1)) != member.size:
                raise ValueError(f"Unexpected MinIO backup member: {member.name}")
            payload = archive.extractfile(member)
            if payload is None:
                raise ValueError(f"Unable to read MinIO backup member: {member.name}")
            tags = Tags.new_object_tags()
            for key, value in (entry.get("tags") or {}).items():
                tags[key] = value
            client.put_object(
                bucket,
                entry["key"],
                payload,
                member.size,
                content_type=entry.get("content_type") or "application/octet-stream",
                metadata=entry.get("metadata") or None,
                tags=tags if entry.get("tags") else None,
            )


def _qdrant_request(method: str, path: str, **kwargs: Any) -> requests.Response:
    base_url = os.environ.get("QDRANT_URL", "http://qdrant:6333").rstrip("/")
    headers = dict(kwargs.pop("headers", {}) or {})
    api_key = os.environ.get("QDRANT_API_KEY", "")
    if api_key:
        headers["api-key"] = api_key
    response = requests.request(method, f"{base_url}{path}", headers=headers, timeout=300, **kwargs)
    response.raise_for_status()
    return response


def _upload_qdrant_snapshot(collection: str, snapshot_name: str, source: BinaryIO, size: int) -> None:
    base_url = os.environ.get("QDRANT_URL", "http://qdrant:6333").rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("QDRANT_URL must be an absolute HTTP(S) URL")
    boundary = f"nexora-{uuid.uuid4().hex}"
    preamble = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="snapshot"; filename="{snapshot_name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    epilogue = f"\r\n--{boundary}--\r\n".encode()
    path_prefix = parsed.path.rstrip("/")
    request_path = (
        f"{path_prefix}/collections/{quote(collection, safe='')}/snapshots/upload?"
        f"{urlencode({'priority': 'snapshot'})}"
    )
    connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_class(parsed.hostname, parsed.port, timeout=300)
    try:
        connection.putrequest("POST", request_path)
        connection.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        connection.putheader("Content-Length", str(len(preamble) + size + len(epilogue)))
        api_key = os.environ.get("QDRANT_API_KEY", "")
        if api_key:
            connection.putheader("api-key", api_key)
        connection.endheaders()
        connection.send(preamble)
        remaining = size
        while remaining:
            chunk = source.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError(f"Qdrant snapshot {snapshot_name} ended before its declared size")
            connection.send(chunk)
            remaining -= len(chunk)
        connection.send(epilogue)
        response = connection.getresponse()
        detail = response.read()
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"Qdrant snapshot restore failed with HTTP {response.status}: {detail[:500]!r}")
    finally:
        connection.close()


def export_qdrant(output: BinaryIO) -> None:
    collections_payload = _qdrant_request("GET", "/collections").json()
    collection_names = [item["name"] for item in collections_payload.get("result", {}).get("collections", [])]
    snapshots = []
    for collection in collection_names:
        encoded_collection = quote(collection, safe="")
        created = _qdrant_request("POST", f"/collections/{encoded_collection}/snapshots").json()
        snapshot_name = created["result"]["name"]
        snapshots.append({
            "collection": collection,
            "snapshot": snapshot_name,
            "blob": f"snapshots/{hashlib.sha256(collection.encode('utf-8')).hexdigest()}.snapshot",
        })

    with tarfile.open(fileobj=output, mode="w|gz") as archive:
        _add_json(archive, "index.json", {"format_version": FORMAT_VERSION, "collections": snapshots})
        for item in snapshots:
            response = _qdrant_request(
                "GET",
                f"/collections/{quote(item['collection'], safe='')}/snapshots/{quote(item['snapshot'], safe='')}",
                stream=True,
            )
            try:
                length = int(response.headers.get("content-length") or 0)
                if length <= 0:
                    payload = response.content
                    stream: BinaryIO = io.BytesIO(payload)
                    length = len(payload)
                else:
                    stream = response.raw
                info = tarfile.TarInfo(item["blob"])
                info.size = length
                info.mode = 0o600
                archive.addfile(info, stream)
            finally:
                response.close()
                _qdrant_request(
                    "DELETE",
                    f"/collections/{quote(item['collection'], safe='')}/snapshots/{quote(item['snapshot'], safe='')}",
                )


def import_qdrant(source: BinaryIO) -> None:
    with tarfile.open(fileobj=source, mode="r|gz") as archive:
        first = archive.next()
        if first is None or first.name != "index.json" or not first.isfile():
            raise ValueError("Qdrant backup is missing index.json")
        index_file = archive.extractfile(first)
        if index_file is None:
            raise ValueError("Unable to read Qdrant backup index")
        index = json.load(index_file)
        if index.get("format_version") != FORMAT_VERSION:
            raise ValueError("Unsupported Qdrant backup format")
        entries = {item["blob"]: item for item in index.get("collections", [])}
        existing = _qdrant_request("GET", "/collections").json().get("result", {}).get("collections", [])
        existing_names = {str(entry.get("name") or "") for entry in existing}

        restored: set[str] = set()
        while (member := archive.next()) is not None:
            if member.name.startswith("/") or ".." in member.name.split("/") or not member.isfile():
                raise ValueError(f"Unsafe Qdrant backup member: {member.name}")
            item = entries.get(member.name)
            if item is None:
                raise ValueError(f"Unexpected Qdrant backup member: {member.name}")
            collection = str(item["collection"])
            snapshot = archive.extractfile(member)
            if snapshot is None:
                raise ValueError(f"Qdrant snapshot is missing for {collection}")
            if collection in existing_names:
                _qdrant_request("DELETE", f"/collections/{quote(collection, safe='')}")
            _upload_qdrant_snapshot(collection, str(item["snapshot"]), snapshot, member.size)
            restored.add(member.name)
        missing = set(entries) - restored
        if missing:
            raise ValueError(f"Qdrant backup is missing {len(missing)} snapshot file(s)")


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in {"export", "import"} or sys.argv[2] not in {"minio", "qdrant"}:
        raise SystemExit("Usage: python -m core.local_backup_io export|import minio|qdrant")
    operation, component = sys.argv[1:]
    if operation == "export" and component == "minio":
        export_minio(sys.stdout.buffer)
    elif operation == "import" and component == "minio":
        import_minio(sys.stdin.buffer)
    elif operation == "export" and component == "qdrant":
        export_qdrant(sys.stdout.buffer)
    else:
        import_qdrant(sys.stdin.buffer)


if __name__ == "__main__":
    main()
