from typing import Any, Optional

import pytest

from core.knowledge_search import QdrantKnowledgeSearchClient, _odata_filter_to_qdrant


class RecordingQdrantClient(QdrantKnowledgeSearchClient):
    def __init__(self, responses: Optional[list[dict[str, Any]]] = None):
        super().__init__(
            endpoint="http://qdrant:6333",
            collection_name="knowledge",
            vector_size=3,
            vector_field="embedding",
        )
        self.responses = list(responses or [])
        self.requests: list[tuple[str, str, Optional[dict[str, Any]], bool]] = []

    async def _request(self, method, path, *, json_body=None, allow_not_found=False):
        self.requests.append((method, path, json_body, allow_not_found))
        return self.responses.pop(0) if self.responses else {"result": {}}


def test_qdrant_filter_translates_personal_team_and_global_acl():
    translated = _odata_filter_to_qdrant(
        "(oids/any(g:search.in(g, 'user-1')) or "
        "(not oids/any() and groups/any(g:search.in(g, 'group-1, group-2'))) or "
        "(not oids/any() and not groups/any()))"
    )

    assert len(translated["should"]) == 3
    assert translated["should"][0] == {"key": "oids", "match": {"any": ["user-1"]}}
    assert translated["should"][1]["must"][1] == {
        "key": "groups",
        "match": {"any": ["group-1", "group-2"]},
    }
    assert translated["should"][2]["must"] == [
        {"is_empty": {"key": "oids"}},
        {"is_empty": {"key": "groups"}},
    ]


def test_qdrant_filter_rejects_unknown_filter_instead_of_bypassing_acl():
    with pytest.raises(ValueError, match="Unsupported Knowledge search filter"):
        _odata_filter_to_qdrant("tenantId eq 'tenant-1' or true")


def test_qdrant_filter_translates_category_and_citation_path():
    translated = _odata_filter_to_qdrant(
        "category eq 'policy' and (oids/any(g:search.in(g, 'user-1')) and "
        "((sourcefile eq 'manual.pdf') or (sourcepage eq 'manual.pdf')))"
    )

    assert translated["must"][0] == {"key": "category", "match": {"value": "policy"}}
    citation_filter = translated["must"][1]["must"][1]
    assert citation_filter["should"] == [
        {"key": "sourcefile", "match": {"value": "manual.pdf"}},
        {"key": "sourcepage", "match": {"value": "manual.pdf"}},
    ]


@pytest.mark.asyncio
async def test_qdrant_upload_uses_stable_point_id_and_preserves_acl_payload():
    client = RecordingQdrantClient()
    document = {
        "id": "document-page-1",
        "content": "hello",
        "sourcefile": "document.pdf",
        "oids": ["user-1"],
        "groups": ["group-1"],
        "embedding": [0.1, 0.2, 0.3],
    }

    first = await client.upload_documents([document])
    first_point = client.requests[-1][2]["points"][0]
    await client.upload_documents([document])
    second_point = client.requests[-1][2]["points"][0]

    assert first[0].succeeded is True
    assert first_point["id"] == second_point["id"]
    assert first_point["payload"]["oids"] == ["user-1"]
    assert first_point["payload"]["groups"] == ["group-1"]
    assert "embedding" not in first_point["payload"]


@pytest.mark.asyncio
async def test_qdrant_vector_search_applies_filter_and_maps_score():
    client = RecordingQdrantClient(
        [
            {
                "result": [
                    {
                        "id": "point-id",
                        "score": 0.91,
                        "payload": {"id": "doc-1", "content": "answer", "oids": ["user-1"]},
                    }
                ]
            }
        ]
    )

    results = await client.search(
        top=5,
        search_text="answer",
        filter="oids/any(g:search.in(g, 'user-1'))",
        vector_queries=[{"vector": [0.1, 0.2, 0.3]}],
    )
    documents = [document async for document in results]
    request_body = client.requests[0][2]

    assert documents[0]["id"] == "doc-1"
    assert documents[0]["@search.score"] == pytest.approx(0.91)
    assert request_body["filter"] == {
        "must": [{"key": "oids", "match": {"any": ["user-1"]}}]
    }


@pytest.mark.asyncio
async def test_qdrant_collection_dimension_mismatch_fails_startup():
    client = RecordingQdrantClient(
        [
            {
                "result": {
                    "config": {"params": {"vectors": {"embedding": {"size": 4, "distance": "Cosine"}}}}
                }
            }
        ]
    )

    with pytest.raises(ValueError, match="uses vector size 4"):
        await client.ensure_ready()


@pytest.mark.asyncio
async def test_qdrant_new_collection_creates_acl_payload_indexes():
    client = RecordingQdrantClient([{"status": "not_found"}])

    await client.ensure_ready()

    assert client.requests[1][0:2] == ("PUT", "/collections/knowledge")
    indexed_fields = [request[2]["field_name"] for request in client.requests[2:]]
    assert indexed_fields == ["category", "sourcefile", "sourcepage", "oids", "groups"]
