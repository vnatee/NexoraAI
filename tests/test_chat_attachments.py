import base64

import pytest
from quart import Quart

import app
from core.chat_attachments import ChatAttachmentError, redact_inline_images, validate_chat_attachments
from error import error_dict


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-image"


def _attachment(**changes):
    item = {
        "id": "client-id",
        "kind": "image",
        "name": "screenshot.png",
        "mime_type": "image/png",
        "size": len(PNG_BYTES),
        "data_url": "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode(),
    }
    item.update(changes)
    return item


def test_validate_chat_attachments_returns_canonical_image():
    result = validate_chat_attachments([_attachment(name="../private/screenshot.png", ignored="value")])

    assert result == [{**_attachment(), "name": "screenshot.png"}]


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"mime_type": "application/pdf"}, "unsupported image type"),
        ({"data_url": "data:image/png;base64,not-base64"}, "invalid base64"),
        ({"size": 99}, "size does not match"),
        (
            {
                "size": 4,
                "data_url": "data:image/png;base64," + base64.b64encode(b"nope").decode(),
            },
            "does not match its image type",
        ),
    ],
)
def test_validate_chat_attachments_rejects_invalid_images(changes, message):
    with pytest.raises(ValueError, match=message):
        validate_chat_attachments([_attachment(**changes)])


def test_validate_chat_attachments_limits_count():
    with pytest.raises(ValueError, match="at most 4"):
        validate_chat_attachments([_attachment(id=str(index)) for index in range(5)])


def test_redact_inline_images_does_not_return_image_bytes():
    image_url = _attachment()["data_url"]
    value = {"content": [{"image_url": {"url": image_url}}]}

    assert redact_inline_images(value, [image_url]) == {
        "content": [{"image_url": {"url": "[inline image omitted]"}}]
    }


def test_attachment_errors_are_safe_for_client_display():
    assert error_dict(ChatAttachmentError("This agent cannot process images")) == {
        "error": "This agent cannot process images"
    }


@pytest.mark.asyncio
async def test_managed_vision_attachment_does_not_require_azure_knowledge_vision():
    quart_app = Quart(__name__)
    quart_app.config[app.CONFIG_GPT4V_DEPLOYED] = False
    context = {
        "overrides": {
            "use_gpt4v": True,
            "_llm_supports_vision": True,
            "vector_fields": "textAndImageEmbeddings",
        }
    }

    async with quart_app.app_context():
        app._apply_inline_image_attachments(
            {"attachments": [_attachment()]},
            context,
            vision_enabled=True,
            vision_available=True,
        )
        assert app._use_vision_approach(context) is True

    assert context["overrides"]["_rag_vision_enabled"] is False
    assert context["overrides"]["_image_attachments"] == [_attachment()["data_url"]]


@pytest.mark.asyncio
async def test_chat_rejects_images_when_vision_is_disabled(client):
    response = await client.post(
        "/chat",
        json={
            "messages": [{"content": "What is shown here?", "role": "user"}],
            "attachments": [_attachment()],
            "context": {"overrides": {"use_gpt4v": False}},
            "session_state": None,
        },
    )

    assert response.status_code == 400
    assert await response.get_json() == {
        "error": "This agent cannot process images. Enable a vision-capable model and try again"
    }


@pytest.mark.asyncio
async def test_chat_vision_redacts_user_image_from_response(client):
    attachment = _attachment()
    response = await client.post(
        "/chat",
        json={
            "messages": [{"content": "What is shown here?", "role": "user"}],
            "attachments": [attachment],
            "context": {
                "overrides": {
                    "use_gpt4v": True,
                    "gpt4v_input": "textAndImages",
                    "vector_fields": "textAndImageEmbeddings",
                }
            },
            "session_state": None,
        },
    )

    result = await response.get_json()
    if response.status_code == 400:
        assert result == {"error": "The model selected for this agent does not support image input"}
        return

    assert response.status_code == 200
    serialized = str(result)
    assert attachment["data_url"] not in serialized
    assert "[inline image omitted]" in serialized
