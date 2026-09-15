import base64

import pytest
from quart import Quart

import app
from core.chat_attachments import ChatAttachmentError, redact_inline_images, validate_chat_attachments
from core.model_profiles import LLMProfile
from core.runtime_settings import LLMProviderSettings, ModelProvider
from core.sessionhelper import ConversationIdError
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


@pytest.mark.parametrize(
    ("use_gpt4v", "endpoint", "expected"),
    [
        (True, "https://vision.example.test/", True),
        (True, "http://vision:8080", True),
        (True, "", False),
        (True, "computervision", False),
        (False, "https://vision.example.test/", False),
    ],
)
def test_knowledge_vision_requires_flag_and_absolute_endpoint(use_gpt4v, endpoint, expected):
    assert app._has_configured_knowledge_vision(use_gpt4v, endpoint) is expected


def test_attachment_errors_are_safe_for_client_display():
    assert error_dict(ChatAttachmentError("This agent cannot process images")) == {
        "error": "This agent cannot process images"
    }
    assert error_dict(ConversationIdError("conversation_id must be a valid UUID")) == {
        "error": "conversation_id must be a valid UUID"
    }


@pytest.mark.asyncio
async def test_chat_rejects_invalid_conversation_id(client):
    response = await client.post(
        "/chat",
        json={
            "messages": [{"content": "Hello", "role": "user"}],
            "conversation_id": "../../another-conversation",
            "context": {"overrides": {}},
            "session_state": None,
        },
    )

    assert response.status_code == 400
    assert await response.get_json() == {"error": "conversation_id must be a valid UUID"}


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
async def test_agent_selects_vision_only_for_validated_image_attachments():
    quart_app = Quart(__name__)
    quart_app.config[app.CONFIG_KNOWLEDGE_VISION_ENABLED] = False
    context = {
        "overrides": {
            "use_gpt4v": True,
            "_llm_supports_vision": True,
            "_agent_image_input_enabled": True,
        }
    }

    async with quart_app.app_context():
        app._apply_inline_image_attachments(
            {"document_attachment_ids": ["9aee2161-d67f-45a1-b4a5-7d2042dd1c26"]},
            context,
            vision_enabled=True,
            vision_available=True,
            select_vision_from_attachments=True,
        )
        assert context["overrides"]["use_gpt4v"] is False
        assert app._use_vision_approach(context) is False

        app._apply_inline_image_attachments(
            {"attachments": [_attachment()]},
            context,
            vision_enabled=True,
            vision_available=True,
            select_vision_from_attachments=True,
        )
        assert context["overrides"]["use_gpt4v"] is True
        assert app._use_vision_approach(context) is True


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
    assert await response.get_json() == {"error": "Image input is disabled for this agent"}


@pytest.mark.asyncio
async def test_agent_attachment_policy_overrides_spoofed_client_values(monkeypatch):
    quart_app = Quart(__name__)
    settings = LLMProviderSettings(
        provider=ModelProvider.OPENAI_COMPATIBLE,
        model="vision-model",
        deployment=None,
        api_version=None,
        endpoint=None,
        base_url="http://local",
        api_key=None,
        organization=None,
    )
    profile = LLMProfile("system", "System", settings, supports_vision=True)
    quart_app.config[app.CONFIG_LLM_PROFILES] = {"system": profile}
    quart_app.config[app.CONFIG_LLM_PROFILE_CLIENTS] = {"system": object()}
    monkeypatch.setattr(
        app,
        "get_agent_by_id",
        lambda agent_id: {
            "config": {
                "llm_profile_id": "system",
                "image_input_enabled": False,
                "document_attachments_enabled": False,
            }
        },
    )
    context = {
        "overrides": {
            "use_gpt4v": True,
            "_agent_image_input_enabled": True,
            "_agent_document_attachments_enabled": True,
        }
    }

    async with quart_app.app_context():
        app._apply_agent_llm_profile(context, "agent-1")

    assert context["overrides"]["use_gpt4v"] is False
    assert context["overrides"]["_agent_image_input_enabled"] is False
    assert context["overrides"]["_agent_document_attachments_enabled"] is False


@pytest.mark.asyncio
async def test_agent_config_requires_vision_model_and_legacy_runtime():
    quart_app = Quart(__name__)
    settings = LLMProviderSettings(
        provider=ModelProvider.OPENAI_COMPATIBLE,
        model="model",
        deployment=None,
        api_version=None,
        endpoint=None,
        base_url="http://local",
        api_key=None,
        organization=None,
    )
    quart_app.config[app.CONFIG_LLM_PROFILES] = {
        "system": LLMProfile("system", "System", settings, supports_tools=True, supports_vision=False)
    }
    base_config = {"llm_profile_id": "system", "runtime": "legacy", "tool_settings": {}}

    async with quart_app.app_context():
        normalized = app._validate_agent_model_config(base_config)
        assert normalized["image_input_enabled"] is False
        assert normalized["document_attachments_enabled"] is True
        with pytest.raises(ValueError, match="Supports image"):
            app._validate_agent_model_config({**base_config, "image_input_enabled": True})
        with pytest.raises(ValueError, match="document_attachments_enabled must be a boolean"):
            app._validate_agent_model_config({**base_config, "document_attachments_enabled": "false"})


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
