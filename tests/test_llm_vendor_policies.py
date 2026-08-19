import pytest

from core.llm_vendors import apply_llm_vendor_chat_policy


def _params(**overrides):
    return {
        "temperature": 0.3,
        "max_tokens": 100,
        "n": 1,
        "seed": 42,
        "stream": True,
        "stream_options": {"include_usage": True},
        **overrides,
    }


def test_gemini_omits_unsupported_chat_seed():
    result = apply_llm_vendor_chat_policy("google_gemini", _params())

    assert "seed" not in result
    assert result["n"] == 1
    assert result["stream_options"] == {"include_usage": True}


def test_claude_omits_ignored_seed_and_caps_temperature():
    result = apply_llm_vendor_chat_policy("anthropic_claude", _params(temperature=1.8))

    assert "seed" not in result
    assert result["temperature"] == 1.0
    assert result["n"] == 1


def test_ollama_uses_seed_but_omits_undocumented_n():
    result = apply_llm_vendor_chat_policy("ollama", _params())

    assert result["seed"] == 42
    assert "n" not in result


def test_mistral_maps_seed_to_random_seed_and_omits_stream_usage_option():
    result = apply_llm_vendor_chat_policy("mistral", _params())

    assert "seed" not in result
    assert result["extra_body"] == {"random_seed": 42}
    assert "stream_options" not in result


def test_deepseek_omits_seed_and_n_but_keeps_supported_stream_usage():
    result = apply_llm_vendor_chat_policy("deepseek", _params())

    assert "seed" not in result
    assert "n" not in result
    assert result["stream_options"] == {"include_usage": True}


def test_together_uses_conservative_single_completion_policy():
    result = apply_llm_vendor_chat_policy("together", _params(temperature=1.5))

    assert result["seed"] == 42
    assert "n" not in result
    assert "stream_options" not in result
    assert result["temperature"] == 1.0


def test_groq_normalizes_zero_temperature_and_keeps_seed():
    result = apply_llm_vendor_chat_policy("groq", _params(temperature=0))

    assert result["temperature"] == 1e-8
    assert result["seed"] == 42
    assert result["n"] == 1


@pytest.mark.parametrize("vendor", ["openai", "azure_openai", "openrouter", "vllm", "localai"])
def test_known_openai_compatible_vendors_never_send_null_seed(vendor):
    result = apply_llm_vendor_chat_policy(vendor, _params(seed=None))

    assert "seed" not in result


def test_stream_options_are_omitted_when_not_streaming():
    result = apply_llm_vendor_chat_policy("openai", _params(stream=False))

    assert "stream_options" not in result
