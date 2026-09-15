from __future__ import annotations

import math
import re
import uuid
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import aiohttp


@runtime_checkable
class KnowledgeSearchClient(Protocol):
    """Small search-client contract shared by retrieval and ingestion."""

    async def search(self, **kwargs: Any) -> Any: ...

    async def upload_documents(self, documents: list[dict[str, Any]]) -> Any: ...

    async def delete_documents(self, documents: list[dict[str, Any]]) -> Any: ...

    async def get_document_count(self) -> int: ...

    async def close(self) -> None: ...


@dataclass(frozen=True)
class KnowledgeIndexingResult:
    key: str
    succeeded: bool = True
    error_message: str | None = None


class QdrantSearchResults:
    def __init__(self, documents: list[dict[str, Any]], count: int | None = None):
        self._documents = documents
        self._count = len(documents) if count is None else count

    def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        return self._iterate(self._documents)

    async def by_page(self) -> AsyncIterator[AsyncIterator[dict[str, Any]]]:
        yield self._iterate(self._documents)

    async def get_count(self) -> int:
        return self._count

    @staticmethod
    async def _iterate(items: Iterable[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
        for item in items:
            yield item


class QdrantKnowledgeSearchClient:
    """Qdrant implementation of the Knowledge search contract.

    Payloads retain the existing Knowledge field names so citation and ACL
    behavior remain identical across Azure AI Search and Qdrant.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        collection_name: str,
        vector_size: int,
        vector_field: str,
        api_key: str | None = None,
        timeout_seconds: float = 30,
    ):
        endpoint = endpoint.strip().rstrip("/")
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("QDRANT_URL must be an absolute HTTP(S) URL")
        if not collection_name.strip():
            raise ValueError("QDRANT_COLLECTION must not be empty")
        if vector_size <= 0:
            raise ValueError("QDRANT_VECTOR_SIZE must be greater than zero")
        self.endpoint = endpoint
        self.collection_name = collection_name.strip()
        self.vector_size = vector_size
        self.vector_field = vector_field
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def __aenter__(self) -> QdrantKnowledgeSearchClient:
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    async def close(self) -> None:
        return None

    def _headers(self) -> dict[str, str]:
        return {"api-key": self.api_key} if self.api_key else {}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        allow_not_found: bool = False,
    ) -> dict[str, Any]:
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout, headers=self._headers()) as session:
            async with session.request(method, f"{self.endpoint}{path}", json=json_body) as response:
                if allow_not_found and response.status == 404:
                    return {"status": "not_found"}
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    detail = payload.get("status", {}).get("error") if isinstance(payload, dict) else None
                    raise RuntimeError(f"Qdrant returned HTTP {response.status}: {detail or payload}")
                return payload

    async def ensure_ready(self) -> None:
        path = f"/collections/{self.collection_name}"
        existing = await self._request("GET", path, allow_not_found=True)
        if existing.get("status") == "not_found":
            await self._request(
                "PUT",
                path,
                json_body={
                    "vectors": {
                        self.vector_field: {
                            "size": self.vector_size,
                            "distance": "Cosine",
                            "on_disk": True,
                        }
                    },
                    "on_disk_payload": True,
                },
            )
        else:
            vectors = existing.get("result", {}).get("config", {}).get("params", {}).get("vectors", {})
            configured = vectors.get(self.vector_field, {}) if isinstance(vectors, dict) else {}
            existing_size = configured.get("size") if isinstance(configured, dict) else None
            if existing_size is not None and int(existing_size) != self.vector_size:
                raise ValueError(
                    f"Qdrant collection {self.collection_name!r} uses vector size {existing_size}; "
                    f"configured embedding size is {self.vector_size}"
                )
        for field in ("category", "sourcefile", "sourcepage", "oids", "groups"):
            await self._request(
                "PUT",
                f"/collections/{self.collection_name}/index?wait=true",
                json_body={"field_name": field, "field_schema": "keyword"},
            )

    @staticmethod
    def _point_id(document_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"nexora-knowledge:{document_id}"))

    async def upload_documents(self, documents: list[dict[str, Any]]) -> list[KnowledgeIndexingResult]:
        points = []
        results = []
        for document in documents:
            document_id = str(document.get("id") or "")
            vector = document.get(self.vector_field)
            if not document_id:
                results.append(KnowledgeIndexingResult(key="<missing>", succeeded=False, error_message="id is required"))
                continue
            if not isinstance(vector, list) or len(vector) != self.vector_size:
                results.append(
                    KnowledgeIndexingResult(
                        key=document_id,
                        succeeded=False,
                        error_message=f"{self.vector_field} must contain {self.vector_size} values",
                    )
                )
                continue
            if any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in vector):
                results.append(KnowledgeIndexingResult(key=document_id, succeeded=False, error_message="invalid vector"))
                continue
            payload = {key: value for key, value in document.items() if key != self.vector_field}
            points.append(
                {
                    "id": self._point_id(document_id),
                    "vector": {self.vector_field: vector},
                    "payload": payload,
                }
            )
            results.append(KnowledgeIndexingResult(key=document_id))
        if points:
            await self._request(
                "PUT",
                f"/collections/{self.collection_name}/points?wait=true",
                json_body={"points": points},
            )
        return results

    async def delete_documents(self, documents: list[dict[str, Any]]) -> list[KnowledgeIndexingResult]:
        ids = [str(document.get("id") or "") for document in documents]
        ids = [document_id for document_id in ids if document_id]
        if ids:
            await self._request(
                "POST",
                f"/collections/{self.collection_name}/points/delete?wait=true",
                json_body={"points": [self._point_id(document_id) for document_id in ids]},
            )
        return [KnowledgeIndexingResult(key=document_id) for document_id in ids]

    async def get_document_count(self) -> int:
        response = await self._request(
            "POST",
            f"/collections/{self.collection_name}/points/count",
            json_body={"exact": True},
        )
        return int(response.get("result", {}).get("count", 0))

    @staticmethod
    def _extract_vector(vector_queries: list[Any]) -> list[float] | None:
        for query in vector_queries:
            vector = getattr(query, "vector", None)
            if isinstance(vector, list):
                return [float(value) for value in vector]
            if isinstance(query, dict) and isinstance(query.get("vector"), list):
                return [float(value) for value in query["vector"]]
        return None

    async def search(self, **kwargs: Any) -> QdrantSearchResults:
        top = max(1, min(int(kwargs.get("top") or 50), 1000))
        filter_expression = kwargs.get("filter")
        qdrant_filter = _odata_filter_to_qdrant(filter_expression) if filter_expression else None
        vector = self._extract_vector(kwargs.get("vector_queries") or [])
        if vector is not None:
            body: dict[str, Any] = {
                "vector": {"name": self.vector_field, "vector": vector},
                "limit": top,
                "with_payload": True,
                "with_vector": False,
            }
            if qdrant_filter:
                body["filter"] = qdrant_filter
            response = await self._request(
                "POST", f"/collections/{self.collection_name}/points/search", json_body=body
            )
            documents = [self._search_hit_to_document(hit) for hit in response.get("result", [])]
            return QdrantSearchResults(documents, len(documents))

        candidate_limit = min(max(top * 20, 100), 1000)
        body = {"limit": candidate_limit, "with_payload": True, "with_vector": False}
        if qdrant_filter:
            body["filter"] = qdrant_filter
        response = await self._request(
            "POST", f"/collections/{self.collection_name}/points/scroll", json_body=body
        )
        documents = [self._scroll_hit_to_document(hit) for hit in response.get("result", {}).get("points", [])]
        query_text = str(kwargs.get("search_text") or "").strip()
        if query_text and query_text != "*":
            terms = {term for term in re.findall(r"\w+", query_text.lower()) if term}
            for document in documents:
                content_terms = set(re.findall(r"\w+", str(document.get("content") or "").lower()))
                document["@search.score"] = len(terms & content_terms) / max(len(terms), 1)
            documents.sort(key=lambda item: float(item.get("@search.score") or 0), reverse=True)
        return QdrantSearchResults(documents[:top], len(documents))

    @staticmethod
    def _search_hit_to_document(hit: dict[str, Any]) -> dict[str, Any]:
        document = dict(hit.get("payload") or {})
        document["@search.score"] = float(hit.get("score") or 0)
        return document

    @staticmethod
    def _scroll_hit_to_document(hit: dict[str, Any]) -> dict[str, Any]:
        document = dict(hit.get("payload") or {})
        document.setdefault("@search.score", 1.0)
        return document


_STRING = r"'((?:''|[^'])*)'"


def _unescape(value: str) -> str:
    return value.replace("''", "'")


def _odata_filter_to_qdrant(expression: str) -> dict[str, Any]:
    """Translate the deliberately small OData subset emitted by NexoraAI.

    Unknown expressions fail closed instead of returning unfiltered documents.
    """

    expression = expression.strip()
    if not expression:
        return {}

    def condition_for_atom(atom: str) -> dict[str, Any]:
        atom = atom.strip()
        while atom.startswith("(") and atom.endswith(")") and _outer_parentheses_wrap(atom):
            atom = atom[1:-1].strip()
        parts = _split_boolean(atom, "or")
        if len(parts) > 1:
            return {"should": [condition_for_atom(part) for part in parts]}
        parts = _split_boolean(atom, "and")
        if len(parts) > 1:
            return {"must": [condition_for_atom(part) for part in parts]}

        match = re.fullmatch(rf"([A-Za-z][A-Za-z0-9_]*)\s+(eq|ne)\s+{_STRING}", atom)
        if match:
            field, operator, raw_value = match.groups()
            condition = {"key": field, "match": {"value": _unescape(raw_value)}}
            return condition if operator == "eq" else {"must_not": [condition]}

        match = re.fullmatch(rf"(oids|groups)/any\(g:search\.in\(g,\s*{_STRING}\)\)", atom)
        if match:
            field, raw_values = match.groups()
            values = [value.strip() for value in _unescape(raw_values).split(",") if value.strip()]
            return {"key": field, "match": {"any": values}}

        match = re.fullmatch(r"(not\s+)?(oids|groups)/any\(\)", atom)
        if match:
            negated, field = match.groups()
            empty = {"is_empty": {"key": field}}
            return empty if negated else {"must_not": [empty]}

        raise ValueError("Unsupported Knowledge search filter expression")

    translated = condition_for_atom(expression)
    if "key" in translated or "is_empty" in translated:
        return {"must": [translated]}
    return translated


def _outer_parentheses_wrap(expression: str) -> bool:
    depth = 0
    quoted = False
    index = 0
    while index < len(expression):
        character = expression[index]
        if character == "'":
            if quoted and index + 1 < len(expression) and expression[index + 1] == "'":
                index += 2
                continue
            quoted = not quoted
        elif not quoted:
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0 and index != len(expression) - 1:
                    return False
        index += 1
    return depth == 0 and not quoted


def _split_boolean(expression: str, operator: str) -> list[str]:
    marker = f" {operator} "
    depth = 0
    quoted = False
    start = 0
    parts = []
    index = 0
    while index < len(expression):
        character = expression[index]
        if character == "'":
            if quoted and index + 1 < len(expression) and expression[index + 1] == "'":
                index += 2
                continue
            quoted = not quoted
        elif not quoted:
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
            elif depth == 0 and expression.startswith(marker, index):
                parts.append(expression[start:index])
                index += len(marker)
                start = index
                continue
        index += 1
    if parts:
        parts.append(expression[start:])
        return parts
    return [expression]
