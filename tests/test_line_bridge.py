import asyncio
import base64
import hashlib
import hmac
import json

import pytest

from line_bridge import (
    EphemeralConversationState,
    LineBridgeSettings,
    MongoConversationState,
    build_agent_input,
    create_app,
    format_agent_answer,
    line_session_id,
    line_source_id,
    run_line_worker,
    split_line_messages,
    stable_conversation_id,
    verify_line_signature,
)


def settings(**overrides):
    values = {
        "channel_secret": "line-secret",
        "channel_access_token": "line-token",
        "nexora_base_url": "http://nexora.test",
        "nexora_agent_id": "agent-1",
        "nexora_api_key": "nxai_test",
        "allowed_source_ids": frozenset(),
        "history_turns": 2,
        "state_ttl_seconds": 3600,
        "job_timeout_seconds": 30,
        "poll_interval_seconds": 1.0,
        "send_ack": True,
        "ack_text": "Working",
    }
    values.update(overrides)
    return LineBridgeSettings(**values)


def signature(body: bytes, secret: str = "line-secret") -> str:
    return base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()


def test_verify_line_signature_uses_exact_raw_body():
    body = b'{"events":[]}'
    assert verify_line_signature(body, signature(body), "line-secret")
    assert not verify_line_signature(body + b" ", signature(body), "line-secret")
    assert not verify_line_signature(body, "invalid", "line-secret")


def test_build_agent_input_and_stable_conversation_id():
    assert build_agent_input([], "current") == "current"
    rendered = build_agent_input(
        [("first question", "first answer")],
        "follow up",
    )
    assert "User: first question" in rendered
    assert "Assistant: first answer" in rendered
    assert rendered.endswith("Current user message: follow up")
    bounded = build_agent_input([("user", "answer" * 10_000)], "current")
    assert len(bounded) <= 32_768
    assert bounded.endswith("Current user message: current")
    assert stable_conversation_id("U123") == stable_conversation_id("U123")
    assert stable_conversation_id("U123") != stable_conversation_id("U456")


def test_group_messages_reply_to_group_but_keep_per_user_context():
    event = {
        "source": {"type": "group", "groupId": "G123", "userId": "U123"}
    }
    assert line_source_id(event) == "G123"
    assert line_session_id(event) == "G123:U123"



def test_format_answer_includes_only_public_http_citations():
    result = {
        "output": "Verified answer",
        "citations": [
            {"title": "Guide", "url": "https://example.com/guide"},
            {"title": "Internal", "url": "file:///secret"},
            {"title": "Duplicate", "url": "https://example.com/guide"},
        ],
    }
    rendered = format_agent_answer(result)
    assert rendered.startswith("Verified answer")
    assert "Guide: https://example.com/guide" in rendered
    assert "file:///secret" not in rendered


def test_split_line_messages_obeys_line_limits():
    messages = split_line_messages("A" * 12_000, limit=1_000, maximum=5)
    assert len(messages) == 5
    assert all(len(message) <= 1_000 for message in messages)
    assert "ข้อความถูกตัด" in messages[-1]


@pytest.mark.asyncio
async def test_ephemeral_state_deduplicates_and_bounds_history():
    state = EphemeralConversationState(settings(history_turns=2))
    assert await state.reserve_event("event-1")
    assert not await state.reserve_event("event-1")

    await state.append_turn("U1", "q1", "a1")
    await state.append_turn("U1", "q2", "a2")
    await state.append_turn("U1", "q3", "a3")

    assert await state.get_history("U1") == [("q2", "a2"), ("q3", "a3")]


class FakeClient:
    def __init__(self):
        self.acks = []
        self.invocations = []
        self.pushes = []

    async def reply_ack(self, reply_token):
        self.acks.append(reply_token)

    async def invoke_agent(self, **kwargs):
        self.invocations.append(kwargs)
        return {
            "output": "Agent answer",
            "citations": [{"title": "Public source", "url": "https://example.com"}],
        }

    async def push_text(self, target, text):
        self.pushes.append((target, text))


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature():
    app = create_app(settings())
    client = app.test_client()
    response = await client.post(
        "/webhook",
        data=b'{"events":[]}',
        headers={"X-Line-Signature": "invalid", "Content-Type": "application/json"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_accepts_once_and_processes_in_background():
    fake = FakeClient()
    app = create_app(settings(), client=fake)
    client = app.test_client()
    payload = {
        "events": [
            {
                "type": "message",
                "webhookEventId": "event-1",
                "replyToken": "reply-1",
                "source": {"type": "user", "userId": "U123"},
                "message": {"type": "text", "id": "message-1", "text": "Question"},
            }
        ]
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = {
        "X-Line-Signature": signature(body),
        "Content-Type": "application/json",
    }

    first = await client.post("/webhook", data=body, headers=headers)
    second = await client.post("/webhook", data=body, headers=headers)
    await asyncio.sleep(0.05)

    assert first.status_code == 200
    assert await first.get_json() == {"accepted": 1}
    assert await second.get_json() == {"accepted": 0}
    assert fake.acks == ["reply-1"]
    assert fake.invocations[0]["source_id"] == "U123"
    assert fake.invocations[0]["input_text"] == "Question"
    assert fake.pushes == [
        ("U123", "Agent answer\n\nSources:\n- Public source: https://example.com")
    ]


@pytest.mark.asyncio
async def test_webhook_enforces_source_allowlist():
    fake = FakeClient()
    app = create_app(
        settings(allowed_source_ids=frozenset({"U-allowed"})),
        client=fake,
    )
    client = app.test_client()
    payload = {
        "events": [
            {
                "type": "message",
                "webhookEventId": "event-denied",
                "source": {"type": "user", "userId": "U-denied"},
                "message": {"type": "text", "text": "Question"},
            }
        ]
    }
    body = json.dumps(payload).encode()
    response = await client.post(
        "/webhook",
        data=body,
        headers={
            "X-Line-Signature": signature(body),
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert await response.get_json() == {"accepted": 0}
    assert fake.invocations == []


@pytest.mark.asyncio
async def test_group_message_can_be_allowed_by_actor_user_id():
    fake = FakeClient()
    app = create_app(
        settings(allowed_source_ids=frozenset({"U-allowed"})),
        client=fake,
    )
    client = app.test_client()
    payload = {
        "events": [
            {
                "type": "message",
                "webhookEventId": "event-group-allowed",
                "source": {
                    "type": "group",
                    "groupId": "G123",
                    "userId": "U-allowed",
                },
                "message": {"type": "text", "text": "Question"},
            }
        ]
    }
    body = json.dumps(payload).encode()
    response = await client.post(
        "/webhook",
        data=body,
        headers={
            "X-Line-Signature": signature(body),
            "Content-Type": "application/json",
        },
    )
    await asyncio.sleep(0.05)

    assert response.status_code == 200
    assert await response.get_json() == {"accepted": 1}
    assert fake.invocations[0]["source_id"] == "G123:U-allowed"
    assert fake.pushes[0][0] == "G123"


class RecordingEvents:
    def __init__(self):
        self.documents = []

    def count_documents(self, query, **kwargs):
        return 0

    def find_one(self, query, projection=None):
        return None


    def insert_one(self, document):
        self.documents.append(document)


def test_mongodb_queue_encrypts_message_and_line_identifiers(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    queue = RecordingEvents()
    state = object.__new__(MongoConversationState)
    state._settings = settings(storage_backend="mongodb")
    state._events = queue

    assert state._enqueue_event("event-1", "U123", "U123", "test-message") == "queued"

    document = queue.documents[0]
    serialized = json.dumps(document, default=str)
    assert "test-message" not in serialized
    assert "U123" not in serialized
    assert document["status"] == "queued"
    assert document["attempt"] == 0


class FakeDurableState:
    def __init__(self, *, terminal=False):
        self.event = {
            "_line_job_id": "job-1",
            "_line_session_hash": "session-hash",
            "_line_attempt": 1,
            "_nexora_event_id": "event-1",
            "_line_target": "U123",
            "_line_session_id": "U123",
            "message": {"type": "text", "text": "Question"},
        }
        self.terminal = terminal
        self.completed = False
        self.failed = False
        self.turns = []

    async def claim_event(self):
        if self.event is None:
            return None
        event, self.event = self.event, None
        return event

    async def get_history(self, source_id):
        return []

    async def append_turn(self, source_id, user_text, answer):
        self.turns.append((source_id, user_text, answer))

    async def complete_event(self, event):
        self.completed = True

    async def fail_event(self, event, error):
        self.failed = True
        return self.terminal


@pytest.mark.asyncio
async def test_durable_worker_completes_claimed_event():
    state = FakeDurableState()
    fake = FakeClient()
    task = asyncio.create_task(
        run_line_worker(settings(worker_poll_seconds=0.01), state, fake)
    )
    try:
        await asyncio.wait_for(_wait_until(lambda: state.completed), timeout=1)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert state.turns == [("U123", "Question", "Agent answer")]
    assert fake.pushes[0][0] == "U123"


class FailingClient(FakeClient):
    async def invoke_agent(self, **kwargs):
        raise RuntimeError("simulated failure")


async def _wait_until(predicate):
    while not predicate():
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_durable_worker_dead_letters_and_notifies_after_final_attempt():
    state = FakeDurableState(terminal=True)
    fake = FailingClient()
    task = asyncio.create_task(
        run_line_worker(settings(worker_poll_seconds=0.01), state, fake)
    )
    try:
        await asyncio.wait_for(_wait_until(lambda: state.failed), timeout=1)
        await asyncio.wait_for(_wait_until(lambda: bool(fake.pushes)), timeout=1)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert "กรุณาลองใหม่อีกครั้ง" in fake.pushes[0][1]
