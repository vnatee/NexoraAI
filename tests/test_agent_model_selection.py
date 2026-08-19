from types import SimpleNamespace
from unittest.mock import MagicMock

from approaches.approach import Approach


def _client_with_create_mock():
    create = MagicMock(return_value="completion-request")
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client, create


def test_create_chat_completion_uses_agent_profile_client_and_model():
    approach = object.__new__(Approach)
    default_client, default_create = _client_with_create_mock()
    profile_client, profile_create = _client_with_create_mock()
    approach.openai_client = default_client
    approach.reasoning_effort = None

    result = approach.create_chat_completion(
        chatgpt_deployment="system-deployment",
        chatgpt_model="system-model",
        messages=[{"role": "user", "content": "hello"}],
        overrides={
            "_llm_client": profile_client,
            "_llm_model": "qwen3",
            "_llm_deployment": None,
            "_llm_profile_id": "local-qwen",
        },
        response_token_limit=100,
    )

    assert result == "completion-request"
    default_create.assert_not_called()
    profile_create.assert_called_once()
    assert profile_create.call_args.kwargs["model"] == "qwen3"


def test_create_chat_completion_keeps_system_client_without_agent_override():
    approach = object.__new__(Approach)
    default_client, default_create = _client_with_create_mock()
    approach.openai_client = default_client
    approach.reasoning_effort = None

    approach.create_chat_completion(
        chatgpt_deployment="system-deployment",
        chatgpt_model="system-model",
        messages=[{"role": "user", "content": "hello"}],
        overrides={},
        response_token_limit=100,
    )

    assert default_create.call_args.kwargs["model"] == "system-deployment"


def test_create_chat_completion_omits_tools_for_model_without_tool_support():
    approach = object.__new__(Approach)
    client, create = _client_with_create_mock()
    approach.openai_client = client
    approach.reasoning_effort = None

    approach.create_chat_completion(
        chatgpt_deployment=None,
        chatgpt_model="qwen2.5vl",
        messages=[{"role": "user", "content": "hello"}],
        overrides={"_llm_supports_tools": False},
        response_token_limit=100,
        tools=[{"type": "function", "function": {"name": "search_sources", "parameters": {}}}],
    )

    assert "tools" not in create.call_args.kwargs


def test_create_chat_completion_omits_seed_for_gemini():
    approach = object.__new__(Approach)
    client, create = _client_with_create_mock()
    approach.openai_client = client
    approach.reasoning_effort = None

    approach.create_chat_completion(
        chatgpt_deployment=None,
        chatgpt_model="gemini-3.6-flash",
        messages=[{"role": "user", "content": "hello"}],
        overrides={"_llm_vendor": "google_gemini", "seed": 42},
        response_token_limit=100,
    )

    assert "seed" not in create.call_args.kwargs
    assert create.call_args.kwargs["n"] == 1


def test_create_chat_completion_keeps_non_null_seed_for_openai():
    approach = object.__new__(Approach)
    client, create = _client_with_create_mock()
    approach.openai_client = client
    approach.reasoning_effort = None

    approach.create_chat_completion(
        chatgpt_deployment=None,
        chatgpt_model="gpt-4.1-mini",
        messages=[{"role": "user", "content": "hello"}],
        overrides={"_llm_vendor": "openai", "seed": 42},
        response_token_limit=100,
    )

    assert create.call_args.kwargs["seed"] == 42


def test_create_chat_completion_omits_null_seed_for_compatible_providers():
    approach = object.__new__(Approach)
    client, create = _client_with_create_mock()
    approach.openai_client = client
    approach.reasoning_effort = None

    approach.create_chat_completion(
        chatgpt_deployment=None,
        chatgpt_model="qwen3",
        messages=[{"role": "user", "content": "hello"}],
        overrides={"_llm_vendor": "ollama", "seed": None},
        response_token_limit=100,
    )

    assert "seed" not in create.call_args.kwargs
