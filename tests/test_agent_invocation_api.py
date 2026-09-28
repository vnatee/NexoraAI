from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

import app as backend_app
from mongo_table_connecters import agent_invocation_keys


class _Result:
    def __init__(self, modified_count=0):
        self.modified_count = modified_count


class _Cursor(list):
    def sort(self, key, direction):
        return _Cursor(
            sorted(
                self,
                key=lambda item: item.get(key) or datetime.min.replace(tzinfo=timezone.utc),
                reverse=direction < 0,
            )
        )


class _Collection:
    def __init__(self):
        self.documents: dict[str, dict] = {}

    def create_index(self, *_args, **_kwargs):
        return None

    @staticmethod
    def _matches(document, query):
        for key, expected in query.items():
            actual = document.get(key)
            if isinstance(expected, dict):
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
            elif actual != expected:
                return False
        return True

    def insert_one(self, document):
        self.documents[document["_id"]] = deepcopy(document)
        return _Result()

    def find_one(self, query):
        for document in self.documents.values():
            if self._matches(document, query):
                return deepcopy(document)
        return None

    def find(self, query):
        return _Cursor(
            deepcopy(document)
            for document in self.documents.values()
            if self._matches(document, query)
        )

    def update_one(self, query, update):
        for document in self.documents.values():
            if self._matches(document, query):
                document.update(deepcopy(update.get("$set") or {}))
                return _Result(1)
        return _Result()

    def find_one_and_update(
        self, query, update, *, upsert=False, return_document=None
    ):
        document = self.documents.get(query["_id"])
        if document is None and upsert:
            document = {"_id": query["_id"]}
            document.update(deepcopy(update.get("$setOnInsert") or {}))
            self.documents[query["_id"]] = document
        if document is not None:
            for key, value in (update.get("$inc") or {}).items():
                document[key] = int(document.get(key) or 0) + int(value)
        return deepcopy(document)


@pytest.fixture
def stores(monkeypatch):
    keys = _Collection()
    limits = _Collection()
    audits = _Collection()
    monkeypatch.setattr(agent_invocation_keys, "keys_collection", keys)
    monkeypatch.setattr(agent_invocation_keys, "rate_limits_collection", limits)
    monkeypatch.setattr(agent_invocation_keys, "audit_collection", audits)
    return keys, limits, audits


def _create(**overrides):
    values = {
        "team_id": "team-1",
        "name": "Operations client",
        "allowed_agent_ids": ["agent-1"],
        "allowed_data_group_ids": ["group-1"],
        "allow_global_knowledge": False,
        "expiry_days": 90,
        "rate_limit_per_minute": 2,
        "created_by": "user-1",
    }
    values.update(overrides)
    return agent_invocation_keys.create_agent_invocation_key(**values)


def test_api_key_is_shown_once_and_only_digest_is_stored(stores):
    keys, _limits, _audits = stores

    item, token = _create()

    assert token.startswith(f"{item['key_prefix']}.")
    assert "token_digest" not in item
    stored = keys.documents[item["_id"]]
    assert stored["token_digest"] != token
    assert token not in str(stored)
    assert agent_invocation_keys.authenticate_agent_invocation_key(token)["_id"] == item["_id"]
    assert "token_digest" not in agent_invocation_keys.list_agent_invocation_keys("team-1")[0]


def test_revoked_and_expired_keys_are_rejected(stores):
    keys, _limits, _audits = stores
    item, token = _create()

    assert agent_invocation_keys.revoke_agent_invocation_key(
        item["_id"], actor_id="admin-1"
    )
    with pytest.raises(agent_invocation_keys.AgentInvocationKeyError, match="revoked"):
        agent_invocation_keys.authenticate_agent_invocation_key(token)

    expired, expired_token = _create(name="Expired")
    keys.documents[expired["_id"]]["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    with pytest.raises(agent_invocation_keys.AgentInvocationKeyError, match="expired"):
        agent_invocation_keys.authenticate_agent_invocation_key(expired_token)


def test_rotate_revokes_old_key_and_preserves_scope(stores):
    _keys, _limits, _audits = stores
    current, old_token = _create()

    replacement, new_token = agent_invocation_keys.rotate_agent_invocation_key(
        current["_id"], actor_id="admin-1", expiry_days=30
    )

    assert replacement["allowed_agent_ids"] == ["agent-1"]
    assert replacement["allowed_data_group_ids"] == ["group-1"]
    assert new_token != old_token
    with pytest.raises(agent_invocation_keys.AgentInvocationKeyError, match="revoked"):
        agent_invocation_keys.authenticate_agent_invocation_key(old_token)
    assert agent_invocation_keys.authenticate_agent_invocation_key(new_token)["_id"] == replacement["_id"]


def test_rate_limit_is_enforced_per_key_and_minute(stores):
    _keys, _limits, _audits = stores
    item, token = _create(rate_limit_per_minute=2)
    document = agent_invocation_keys.authenticate_agent_invocation_key(token)

    agent_invocation_keys.enforce_agent_invocation_rate_limit(document)
    agent_invocation_keys.enforce_agent_invocation_rate_limit(document)
    with pytest.raises(agent_invocation_keys.AgentInvocationKeyError) as limited:
        agent_invocation_keys.enforce_agent_invocation_rate_limit(document)

    assert limited.value.status_code == 429


@pytest.mark.asyncio
async def test_invocation_route_returns_stable_response_without_tool_trace(
    client, monkeypatch
):
    key_document = {
        "_id": "key-1",
        "team_id": "team-1",
        "allowed_agent_ids": ["agent-1"],
        "allowed_data_group_ids": [],
        "allow_global_knowledge": False,
        "rate_limit_per_minute": 60,
    }
    audits = []
    monkeypatch.setattr(
        backend_app,
        "authenticate_agent_invocation_key",
        lambda token: key_document if token == "nxai_test.secret" else None,
    )
    monkeypatch.setattr(
        backend_app, "enforce_agent_invocation_rate_limit", lambda _key: None
    )
    monkeypatch.setattr(
        backend_app, "mark_agent_invocation_key_used", lambda _key_id: None
    )
    monkeypatch.setattr(
        backend_app,
        "insert_agent_invocation_audit",
        lambda **event: audits.append(event),
    )

    async def execute(**_kwargs):
        return (
            {
                "message": {"content": "Safe answer"},
                "context": {
                    "data_points": {"text": [{"title": "Policy", "page": 2}]},
                    "thoughts": [{"secret": "must not leave the runtime"}],
                    "chart": {"type": "bar"},
                },
            },
            "11111111-1111-4111-8111-111111111111",
        )

    monkeypatch.setattr(backend_app, "_execute_agent_invocation", execute)

    response = await client.post(
        "/api/v1/agents/agent-1/invoke",
        headers={"Authorization": "Bearer nxai_test.secret"},
        json={"input": "Summarize the policy"},
    )

    assert response.status_code == 200
    payload = await response.get_json()
    assert payload["output"] == "Safe answer"
    assert payload["citations"] == [{"title": "Policy", "page": 2}]
    assert payload["chart"] == {"type": "bar"}
    assert "thoughts" not in str(payload)
    assert "Summarize the policy" not in str(audits)



@pytest.mark.asyncio
async def test_async_job_route_is_idempotent_and_schedules_only_new_job(
    client, monkeypatch
):
    now = datetime.now(timezone.utc)
    key_document = {
        "_id": "key-1",
        "team_id": "team-1",
        "allowed_agent_ids": ["agent-1"],
    }
    job = {
        "_id": "job-1",
        "key_id": "key-1",
        "team_id": "team-1",
        "agent_id": "agent-1",
        "conversation_id": None,
        "status": "queued",
        "attempt": 0,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "expires_at": now + timedelta(hours=1),
    }
    scheduled = []
    created_values = iter((True, False))
    monkeypatch.setattr(
        backend_app, "authenticate_agent_invocation_key", lambda _token: key_document
    )
    monkeypatch.setattr(
        backend_app, "enforce_agent_invocation_rate_limit", lambda _key: None
    )
    monkeypatch.setattr(
        backend_app, "_validate_agent_invocation_target", lambda *_args: ({}, {}, [])
    )
    monkeypatch.setattr(
        backend_app,
        "create_agent_invocation_job",
        lambda **_kwargs: (job, next(created_values)),
    )
    monkeypatch.setattr(
        backend_app,
        "_schedule_agent_invocation_job",
        lambda job_id: scheduled.append(job_id),
    )

    headers = {
        "Authorization": "Bearer nxai_test.secret",
        "Idempotency-Key": "customer-request-1",
    }
    first = await client.post(
        "/api/v1/agents/agent-1/jobs",
        headers=headers,
        json={"input": "run the analysis"},
    )
    second = await client.post(
        "/api/v1/agents/agent-1/jobs",
        headers=headers,
        json={"input": "run the analysis"},
    )

    assert first.status_code == 202
    assert first.headers["Location"] == "/api/v1/agent-jobs/job-1"
    assert (await first.get_json())["idempotent_replay"] is False
    assert (await second.get_json())["idempotent_replay"] is True
    assert scheduled == ["job-1"]


@pytest.mark.asyncio
async def test_job_status_is_visible_only_to_creating_key(client, monkeypatch):
    now = datetime.now(timezone.utc)
    job = {
        "_id": "job-1",
        "key_id": "key-1",
        "team_id": "team-1",
        "agent_id": "agent-1",
        "conversation_id": None,
        "status": "queued",
        "attempt": 0,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "expires_at": now + timedelta(hours=1),
    }
    monkeypatch.setattr(
        backend_app,
        "authenticate_agent_invocation_key",
        lambda _token: {"_id": "key-2", "team_id": "team-1"},
    )
    monkeypatch.setattr(
        backend_app, "get_agent_invocation_job", lambda _job_id: job
    )

    response = await client.get(
        "/api/v1/agent-jobs/job-1",
        headers={"Authorization": "Bearer nxai_other.secret"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_stream_route_emits_lifecycle_and_public_result(client, monkeypatch):
    key_document = {
        "_id": "key-1",
        "team_id": "team-1",
        "allowed_agent_ids": ["agent-1"],
    }
    monkeypatch.setattr(
        backend_app, "authenticate_agent_invocation_key", lambda _token: key_document
    )
    monkeypatch.setattr(
        backend_app, "enforce_agent_invocation_rate_limit", lambda _key: None
    )
    monkeypatch.setattr(
        backend_app, "_validate_agent_invocation_target", lambda *_args: ({}, {}, [])
    )
    monkeypatch.setattr(
        backend_app, "mark_agent_invocation_key_used", lambda _key_id: None
    )
    monkeypatch.setattr(
        backend_app, "insert_agent_invocation_audit", lambda **_event: None
    )

    async def execute(**_kwargs):
        return (
            {
                "message": {"content": "streamed answer"},
                "context": {
                    "data_points": {"text": [{"title": "Runbook"}]},
                    "thoughts": ["private"],
                },
            },
            "11111111-1111-4111-8111-111111111111",
        )

    monkeypatch.setattr(backend_app, "_execute_agent_invocation", execute)

    response = await client.post(
        "/api/v1/agents/agent-1/invoke/stream",
        headers={"Authorization": "Bearer nxai_test.secret"},
        json={"input": "check the service"},
    )
    body = (await response.get_data()).decode("utf-8")

    assert response.status_code == 200
    assert response.content_type == "text/event-stream; charset=utf-8"
    assert "event: started" in body
    assert "event: completed" in body
    assert "streamed answer" in body
    assert "private" not in body



@pytest.mark.asyncio
async def test_invocation_route_requires_bearer_key(client):
    response = await client.post(
        "/api/v1/agents/agent-1/invoke", json={"input": "hello"}
    )
    assert response.status_code == 401


def test_key_scope_rejects_legacy_agents(monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "get_agent_by_id",
        lambda _agent_id: {
            "_id": "agent-1",
            "lifecycle_status": "active",
            "config": {"runtime": "legacy"},
        },
    )

    with pytest.raises(agent_invocation_keys.AgentInvocationKeyError, match="LangGraph"):
        backend_app._validate_agent_invocation_scope(
            {"agent_id": ["agent-1"], "data_group_id": []},
            agent_ids=["agent-1"],
            data_group_ids=[],
        )

def test_key_scope_rejects_cross_team_agent_and_private_data_group(monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "get_agent_by_id",
        lambda _agent_id: {
            "_id": "agent-1",
            "lifecycle_status": "active",
            "config": {"runtime": "langgraph"},
        },
    )
    with pytest.raises(agent_invocation_keys.AgentInvocationKeyError) as cross_team:
        backend_app._validate_agent_invocation_scope(
            {"agent_id": ["agent-2"], "data_group_id": []},
            agent_ids=["agent-1"],
            data_group_ids=[],
        )
    assert cross_team.value.status_code == 403

    monkeypatch.setattr(
        backend_app,
        "get_data_group_by_id",
        lambda _group_id: {
            "_id": "group-1",
            "name": "Private",
            "access_mode": "selected_users",
            "user_id": ["user-1"],
        },
    )
    with pytest.raises(agent_invocation_keys.AgentInvocationKeyError) as private_group:
        backend_app._validate_agent_invocation_scope(
            {"agent_id": ["agent-1"], "data_group_id": ["group-1"]},
            agent_ids=["agent-1"],
            data_group_ids=["group-1"],
        )
    assert private_group.value.status_code == 403
