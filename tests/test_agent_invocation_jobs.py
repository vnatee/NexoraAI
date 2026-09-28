from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet

from mongo_table_connecters import agent_invocation_jobs


class _Result:
    def __init__(self, modified_count: int = 0):
        self.modified_count = modified_count


class _Cursor(list):
    def sort(self, key, direction):
        return _Cursor(
            sorted(self, key=lambda item: item.get(key), reverse=direction < 0)
        )

    def limit(self, value):
        return _Cursor(self[:value])


class _Collection:
    def __init__(self):
        self.documents: dict[str, dict] = {}

    def create_index(self, *_args, **_kwargs):
        return None

    @classmethod
    def _matches(cls, document, query):
        for key, expected in query.items():
            if key == "$or":
                if not any(cls._matches(document, item) for item in expected):
                    return False
                continue
            actual = document.get(key)
            if isinstance(expected, dict):
                for operator, value in expected.items():
                    if operator == "$in" and actual not in value:
                        return False
                    if operator == "$lte" and not (actual is not None and actual <= value):
                        return False
                    if operator == "$gt" and not (actual is not None and actual > value):
                        return False
                    if operator == "$type" and value == "string" and not isinstance(actual, str):
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
        document = self._matching_document(query)
        if document is None:
            return _Result()
        self._apply_update(document, update)
        return _Result(1)

    def find_one_and_update(self, query, update, *, return_document=None):
        document = self._matching_document(query)
        if document is None:
            return None
        self._apply_update(document, update)
        return deepcopy(document)

    def _matching_document(self, query):
        for document in self.documents.values():
            if self._matches(document, query):
                return document
        return None

    @staticmethod
    def _apply_update(document, update):
        document.update(deepcopy(update.get("$set") or {}))
        for key, value in (update.get("$inc") or {}).items():
            document[key] = int(document.get(key) or 0) + int(value)


@pytest.fixture
def jobs(monkeypatch):
    collection = _Collection()
    monkeypatch.setattr(agent_invocation_jobs, "collection", collection)
    monkeypatch.setenv(
        "APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8")
    )
    return collection


def _create(**overrides):
    values = {
        "key_id": "key-1",
        "team_id": "team-1",
        "agent_id": "agent-1",
        "input_text": "private customer question",
        "conversation_id": "conversation-1",
        "idempotency_key": "request-1",
    }
    values.update(overrides)
    return agent_invocation_jobs.create_agent_invocation_job(**values)


def test_idempotency_replays_same_request_and_rejects_changed_payload(jobs):
    first, created = _create()
    replay, replay_created = _create()

    assert created is True
    assert replay_created is False
    assert replay["_id"] == first["_id"]

    with pytest.raises(
        agent_invocation_jobs.AgentInvocationJobError, match="different request"
    ) as conflict:
        _create(input_text="different private question")

    assert conflict.value.status_code == 409


def test_job_encrypts_input_and_result_at_rest(jobs):
    job, _created = _create()
    stored = jobs.documents[job["_id"]]

    assert "private customer question" not in str(stored)
    assert (
        agent_invocation_jobs.decrypt_agent_invocation_job_input(stored)
        == "private customer question"
    )

    claimed = agent_invocation_jobs.claim_agent_invocation_job(
        job["_id"], "worker-1"
    )
    assert claimed and claimed["status"] == "running"
    completed = agent_invocation_jobs.complete_agent_invocation_job(
        job["_id"],
        "worker-1",
        result={"output": "private response", "citations": []},
    )

    assert completed and completed["status"] == "succeeded"
    assert "private response" not in str(jobs.documents[job["_id"]])
    assert agent_invocation_jobs.serialize_agent_invocation_job(completed)["result"] == {
        "output": "private response",
        "citations": [],
    }


def test_failed_job_can_be_retried_by_owning_key(jobs):
    job, _created = _create()
    agent_invocation_jobs.claim_agent_invocation_job(job["_id"], "worker-1")
    failed = agent_invocation_jobs.complete_agent_invocation_job(
        job["_id"], "worker-1", error="provider token=secret-value failed"
    )

    assert failed and failed["error"]["message"] == "Agent invocation failed"
    assert (
        agent_invocation_jobs.retry_agent_invocation_job(job["_id"], "other-key")
        is None
    )
    retried = agent_invocation_jobs.retry_agent_invocation_job(
        job["_id"], "key-1"
    )
    assert retried and retried["status"] == "queued"
    assert retried["error"] is None


def test_expired_lease_is_recoverable(jobs):
    job, _created = _create(idempotency_key=None)
    jobs.documents[job["_id"]].update(
        {
            "status": "running",
            "worker_id": "dead-worker",
            "lease_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
        }
    )

    recoverable = agent_invocation_jobs.list_recoverable_agent_invocation_jobs()

    assert [item["_id"] for item in recoverable] == [job["_id"]]
