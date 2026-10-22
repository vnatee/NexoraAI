import asyncio
import base64
import hashlib
import hmac
import json

import pytest

from line_bridge import (
    EphemeralConversationState,
    LineBridgeSettings,
    build_agent_input,
    create_app,
    format_agent_answer,
    line_session_id,
    line_source_id,
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
