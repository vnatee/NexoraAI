from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


EXPECTED_PATHS = {
    "/api/v1/agents/{agent_id}/invoke",
    "/api/v1/agents/{agent_id}/invoke/stream",
    "/api/v1/agents/{agent_id}/jobs",
    "/api/v1/agent-jobs/{job_id}",
    "/api/v1/agent-jobs/{job_id}/retry",
}


@pytest.mark.asyncio
async def test_agent_invocation_openapi_is_public_and_matches_routes(client):
    response = await client.get("/api/v1/openapi.yaml")

    assert response.status_code == 200
    assert response.mimetype == "application/yaml"
    assert response.headers["X-Content-Type-Options"] == "nosniff"

    document = yaml.safe_load(await response.get_data(as_text=True))
    assert document["openapi"] == "3.0.3"
    assert set(document["paths"]) == EXPECTED_PATHS
    assert document["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"

    operation_ids = [
        operation["operationId"]
        for path in document["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(operation_ids) == len(set(operation_ids))


def test_agent_invocation_postman_collection_is_safe_and_complete():
    path = (
        Path(__file__).parents[1]
        / "docs"
        / "NexoraAI-Agent-Invocation-API.postman_collection.json"
    )
    raw = path.read_text(encoding="utf-8")
    collection = json.loads(raw)

    assert collection["info"]["name"] == "NexoraAI Agent Invocation API"
    variables = {item["key"]: item["value"] for item in collection["variable"]}
    assert variables["apiKey"] == ""
    assert variables["agentId"] == ""
    assert "nxai_REDACTED" not in raw
    assert "replace-with-key" not in raw

    requests = [
        item["request"]
        for folder in collection["item"]
        for item in folder.get("item", [])
        if "request" in item
    ]
    assert len(requests) == 7
    assert any(
        request["url"]["raw"].endswith("/api/v1/openapi.yaml")
        for request in requests
    )
