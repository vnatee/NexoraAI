from __future__ import annotations

import asyncio
import io
import mimetypes
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, BinaryIO, Literal
from urllib.parse import urlparse

from azure.core.exceptions import ResourceNotFoundError

KnowledgeScope = Literal["personal", "team", "global", "web_global", "web_team"]


class KnowledgeObjectNotFound(FileNotFoundError):
    pass


@dataclass(frozen=True)
class KnowledgeObjectInfo:
    key: str
    size: int
    last_modified: datetime | None
    tags: dict[str, str]


@dataclass(frozen=True)
class KnowledgeObjectContent:
    data: bytes
    content_type: str
    url: str


class KnowledgeObjectStore(ABC):
    @abstractmethod
    async def ensure_ready(self) -> None: ...

    @abstractmethod
    async def put(
        self,
        scope: KnowledgeScope,
        key: str,
        content: BinaryIO | bytes,
        *,
        size: int | None = None,
        metadata: Mapping[str, str] | None = None,
        tags: Mapping[str, str] | None = None,
        content_type: str | None = None,
    ) -> str: ...

    @abstractmethod
    async def read(self, scope: KnowledgeScope, key: str) -> KnowledgeObjectContent: ...

    @abstractmethod
    async def delete(self, scope: KnowledgeScope, key: str) -> None: ...

    @abstractmethod
    async def list(self, scope: KnowledgeScope, *, prefix: str = "") -> list[KnowledgeObjectInfo]: ...

    @abstractmethod
    async def get_tags(self, scope: KnowledgeScope, key: str) -> dict[str, str]: ...

    @abstractmethod
    async def set_tags(self, scope: KnowledgeScope, key: str, tags: Mapping[str, str]) -> None: ...

    async def close(self) -> None:
        return None


class AzureKnowledgeObjectStore(KnowledgeObjectStore):
    def __init__(self, clients: Mapping[KnowledgeScope, Any]):
        self._clients = dict(clients)

    def _client(self, scope: KnowledgeScope) -> Any:
        client = self._clients.get(scope)
        if client is None:
            raise RuntimeError(f"Azure Knowledge storage is not configured for {scope}")
        return client

    def matches_clients(self, clients: Mapping[KnowledgeScope, Any]) -> bool:
        return all(self._clients.get(scope) is client for scope, client in clients.items())

    async def ensure_ready(self) -> None:
        return None

    async def put(
        self,
        scope: KnowledgeScope,
        key: str,
        content: BinaryIO | bytes,
        *,
        size: int | None = None,
        metadata: Mapping[str, str] | None = None,
        tags: Mapping[str, str] | None = None,
        content_type: str | None = None,
    ) -> str:
        client = self._client(scope)
        if scope == "personal":
            directory_name, _, filename = key.partition("/")
            if not directory_name or not filename:
                raise ValueError("Personal Knowledge object keys must include the owner directory")
            directory = client.get_directory_client(directory_name)
            try:
                await directory.get_directory_properties()
            except ResourceNotFoundError:
                await directory.create_directory()
            await directory.set_access_control(owner=directory_name)
            object_client = directory.get_file_client(filename)
            await object_client.upload_data(content, overwrite=True, metadata=dict(metadata or {}))
        else:
            object_client = client.get_blob_client(key)
            await object_client.upload_blob(content, overwrite=True, metadata=dict(metadata or {}))
            if tags:
                await object_client.set_blob_tags(tags=dict(tags))
        return str(object_client.url)

    async def read(self, scope: KnowledgeScope, key: str) -> KnowledgeObjectContent:
        client = self._client(scope)
        try:
            if scope == "personal":
                directory_name, _, filename = key.partition("/")
                if not directory_name or not filename:
                    raise ValueError("Personal Knowledge object keys must include the owner directory")
                object_client = client.get_file_client(key)
                downloader = await object_client.download_file()
            else:
                object_client = client.get_blob_client(key)
                downloader = await object_client.download_blob()
            data = await downloader.readall()
        except ResourceNotFoundError as error:
            raise KnowledgeObjectNotFound(key) from error
        properties = getattr(downloader, "properties", None)
        content_settings = properties.get("content_settings") if properties else None
        if isinstance(content_settings, Mapping):
            content_type = content_settings.get("content_type")
        else:
            content_type = getattr(content_settings, "content_type", None)
        guessed_content_type = mimetypes.guess_type(key)[0]
        if not content_type or content_type == "application/octet-stream":
            content_type = guessed_content_type or "application/octet-stream"
        return KnowledgeObjectContent(data=data, content_type=content_type, url=str(object_client.url))

    async def delete(self, scope: KnowledgeScope, key: str) -> None:
        client = self._client(scope)
        try:
            if scope == "personal":
                directory_name, _, filename = key.partition("/")
                if not directory_name or not filename:
                    raise ValueError("Personal Knowledge object keys must include the owner directory")
                await client.get_file_client(key).delete_file()
            else:
                await client.get_blob_client(key).delete_blob()
        except ResourceNotFoundError as error:
            raise KnowledgeObjectNotFound(key) from error

    async def list(self, scope: KnowledgeScope, *, prefix: str = "") -> list[KnowledgeObjectInfo]:
        client = self._client(scope)
        objects: list[KnowledgeObjectInfo] = []
        try:
            if scope == "personal":
                directory_prefix = prefix.rstrip("/")
                async for item in client.get_paths(path=directory_prefix or None, recursive=True):
                    if getattr(item, "is_directory", False):
                        continue
                    objects.append(
                        KnowledgeObjectInfo(
                            key=str(item.name),
                            size=int(item.content_length or 0),
                            last_modified=getattr(item, "last_modified", None),
                            tags={},
                        )
                    )
            else:
                async for item in client.list_blobs(name_starts_with=prefix or None):
                    key = str(item.name)
                    tags = await self.get_tags(scope, key)
                    objects.append(
                        KnowledgeObjectInfo(
                            key=key,
                            size=int(item.size or 0),
                            last_modified=getattr(item, "last_modified", None),
                            tags=tags,
                        )
                    )
        except ResourceNotFoundError:
            return []
        return objects

    async def get_tags(self, scope: KnowledgeScope, key: str) -> dict[str, str]:
        if scope == "personal":
            return {}
        try:
            return dict(await self._client(scope).get_blob_client(key).get_blob_tags())
        except ResourceNotFoundError as error:
            raise KnowledgeObjectNotFound(key) from error

    async def set_tags(self, scope: KnowledgeScope, key: str, tags: Mapping[str, str]) -> None:
        if scope == "personal":
            return
        try:
            await self._client(scope).get_blob_client(key).set_blob_tags(tags=dict(tags))
        except ResourceNotFoundError as error:
            raise KnowledgeObjectNotFound(key) from error

    async def close(self) -> None:
        seen: set[int] = set()
        for client in self._clients.values():
            if client is None or id(client) in seen:
                continue
            seen.add(id(client))
            await client.close()


class MinioKnowledgeObjectStore(KnowledgeObjectStore):
    def __init__(self, client: Any, bucket: str):
        self._client = client
        self._bucket = bucket

    @staticmethod
    def _object_name(scope: KnowledgeScope, key: str) -> str:
        if key.startswith(("/", "\\")):
            raise ValueError("Invalid Knowledge object key")
        normalized = key.replace("\\", "/")
        if not normalized or any(part in {"", ".", ".."} for part in normalized.split("/")):
            raise ValueError("Invalid Knowledge object key")
        return f"{scope}/{normalized}"

    @staticmethod
    def _key(scope: KnowledgeScope, object_name: str) -> str:
        return object_name.removeprefix(f"{scope}/")

    @staticmethod
    def _is_missing(error: Exception) -> bool:
        return getattr(error, "code", None) in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}

    async def ensure_ready(self) -> None:
        from minio.error import S3Error

        exists = await asyncio.to_thread(self._client.bucket_exists, self._bucket)
        if not exists:
            try:
                await asyncio.to_thread(self._client.make_bucket, self._bucket)
            except S3Error as error:
                if error.code not in {"BucketAlreadyExists", "BucketAlreadyOwnedByYou"}:
                    raise

    async def put(
        self,
        scope: KnowledgeScope,
        key: str,
        content: BinaryIO | bytes,
        *,
        size: int | None = None,
        metadata: Mapping[str, str] | None = None,
        tags: Mapping[str, str] | None = None,
        content_type: str | None = None,
    ) -> str:
        from minio.commonconfig import Tags

        if isinstance(content, bytes):
            stream: BinaryIO = io.BytesIO(content)
            length = len(content)
        else:
            stream = content
            if size is None:
                position = stream.tell()
                stream.seek(0, io.SEEK_END)
                length = stream.tell()
                stream.seek(position)
            else:
                length = size
        object_name = self._object_name(scope, key)
        object_tags = Tags.new_object_tags()
        for tag_key, value in (tags or {}).items():
            object_tags[str(tag_key)] = str(value)
        await asyncio.to_thread(
            self._client.put_object,
            self._bucket,
            object_name,
            stream,
            length,
            content_type=content_type or mimetypes.guess_type(key)[0] or "application/octet-stream",
            metadata=dict(metadata or {}),
            tags=object_tags,
        )
        return f"minio://{self._bucket}/{object_name}"

    async def read(self, scope: KnowledgeScope, key: str) -> KnowledgeObjectContent:
        from minio.error import S3Error

        object_name = self._object_name(scope, key)

        def get() -> KnowledgeObjectContent:
            response = None
            try:
                response = self._client.get_object(self._bucket, object_name)
                data = response.read()
                content_type = response.headers.get("content-type") or mimetypes.guess_type(key)[0] or "application/octet-stream"
                return KnowledgeObjectContent(data=data, content_type=content_type, url=f"minio://{self._bucket}/{object_name}")
            except S3Error as error:
                if self._is_missing(error):
                    raise KnowledgeObjectNotFound(key) from error
                raise
            finally:
                if response is not None:
                    response.close()
                    response.release_conn()

        return await asyncio.to_thread(get)

    async def delete(self, scope: KnowledgeScope, key: str) -> None:
        await asyncio.to_thread(self._client.remove_object, self._bucket, self._object_name(scope, key))

    async def list(self, scope: KnowledgeScope, *, prefix: str = "") -> list[KnowledgeObjectInfo]:
        object_prefix = f"{scope}/{prefix.lstrip('/')}"

        def collect() -> list[KnowledgeObjectInfo]:
            result = []
            for item in self._client.list_objects(self._bucket, prefix=object_prefix, recursive=True):
                tags = self._client.get_object_tags(self._bucket, item.object_name) or {}
                result.append(
                    KnowledgeObjectInfo(
                        key=self._key(scope, item.object_name),
                        size=int(item.size or 0),
                        last_modified=item.last_modified,
                        tags={str(key): str(value) for key, value in dict(tags).items()},
                    )
                )
            return result

        return await asyncio.to_thread(collect)

    async def get_tags(self, scope: KnowledgeScope, key: str) -> dict[str, str]:
        from minio.error import S3Error

        try:
            tags = await asyncio.to_thread(self._client.get_object_tags, self._bucket, self._object_name(scope, key))
        except S3Error as error:
            if self._is_missing(error):
                raise KnowledgeObjectNotFound(key) from error
            raise
        return {str(tag_key): str(value) for tag_key, value in dict(tags or {}).items()}

    async def set_tags(self, scope: KnowledgeScope, key: str, tags: Mapping[str, str]) -> None:
        from minio.commonconfig import Tags
        from minio.error import S3Error

        object_tags = Tags.new_object_tags()
        for tag_key, value in tags.items():
            object_tags[str(tag_key)] = str(value)
        try:
            await asyncio.to_thread(
                self._client.set_object_tags,
                self._bucket,
                self._object_name(scope, key),
                object_tags,
            )
        except S3Error as error:
            if self._is_missing(error):
                raise KnowledgeObjectNotFound(key) from error
            raise


def create_minio_knowledge_store(environ: Mapping[str, str]) -> MinioKnowledgeObjectStore:
    from minio import Minio

    raw_endpoint = environ.get("MINIO_ENDPOINT", "localhost:9000").strip()
    parsed = urlparse(raw_endpoint if "://" in raw_endpoint else f"//{raw_endpoint}")
    endpoint = parsed.netloc or parsed.path
    secure_default = parsed.scheme == "https"
    secure = environ.get("MINIO_SECURE", str(secure_default)).strip().lower() in {"1", "true", "yes", "on"}
    access_key = environ.get("MINIO_ACCESS_KEY", "").strip()
    secret_key = environ.get("MINIO_SECRET_KEY", "")
    bucket = environ.get("MINIO_KNOWLEDGE_BUCKET", "nexora-knowledge").strip()
    if not endpoint or not access_key or not secret_key or not bucket:
        raise ValueError(
            "MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY and MINIO_KNOWLEDGE_BUCKET are required "
            "when KNOWLEDGE_STORAGE_PROVIDER=minio"
        )
    return MinioKnowledgeObjectStore(Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure), bucket)
