from dataclasses import dataclass
from typing import Any

from core.runtime_settings import ModelProvider, parse_model_provider


@dataclass(frozen=True)
class LLMVendor:
    id: str
    label: str
    provider: ModelProvider
    default_base_url: str | None = None
    requires_api_key: bool = False
    supports_seed: bool = True
    seed_parameter: str = "seed"
    send_n: bool = True
    supports_stream_usage: bool = True
    max_temperature: float | None = None


LLM_VENDORS = (
    LLMVendor("azure_openai", "Azure OpenAI", ModelProvider.AZURE_OPENAI),
    LLMVendor("openai", "OpenAI", ModelProvider.OPENAI, requires_api_key=True),
    LLMVendor(
        "google_gemini",
        "Google Gemini",
        ModelProvider.OPENAI_COMPATIBLE,
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        requires_api_key=True,
        supports_seed=False,
    ),
    LLMVendor(
        "anthropic_claude",
        "Anthropic Claude",
        ModelProvider.OPENAI_COMPATIBLE,
        "https://api.anthropic.com/v1/",
        requires_api_key=True,
        supports_seed=False,
        max_temperature=1.0,
    ),
    LLMVendor(
        "ollama",
        "Ollama (Local)",
        ModelProvider.OPENAI_COMPATIBLE,
        "http://localhost:11434/v1/",
        send_n=False,
    ),
    LLMVendor(
        "groq",
        "Groq",
        ModelProvider.OPENAI_COMPATIBLE,
        "https://api.groq.com/openai/v1",
        requires_api_key=True,
    ),
    LLMVendor(
        "openrouter",
        "OpenRouter",
        ModelProvider.OPENAI_COMPATIBLE,
        "https://openrouter.ai/api/v1",
        requires_api_key=True,
    ),
    LLMVendor(
        "mistral",
        "Mistral AI",
        ModelProvider.OPENAI_COMPATIBLE,
        "https://api.mistral.ai/v1",
        requires_api_key=True,
        seed_parameter="random_seed",
        supports_stream_usage=False,
    ),
    LLMVendor(
        "deepseek",
        "DeepSeek",
        ModelProvider.OPENAI_COMPATIBLE,
        "https://api.deepseek.com/v1",
        requires_api_key=True,
        supports_seed=False,
        send_n=False,
    ),
    LLMVendor(
        "together",
        "Together AI",
        ModelProvider.OPENAI_COMPATIBLE,
        "https://api.together.xyz/v1",
        requires_api_key=True,
        send_n=False,
        supports_stream_usage=False,
        max_temperature=1.0,
    ),
    LLMVendor("vllm", "vLLM (Local)", ModelProvider.OPENAI_COMPATIBLE, "http://localhost:8000/v1"),
    LLMVendor(
        "localai",
        "LocalAI (Local)",
        ModelProvider.OPENAI_COMPATIBLE,
        "http://localhost:8080/v1",
        supports_stream_usage=False,
    ),
    LLMVendor(
        "other_openai_compatible",
        "Other OpenAI-compatible",
        ModelProvider.OPENAI_COMPATIBLE,
        supports_seed=False,
        send_n=False,
        supports_stream_usage=False,
    ),
)

LLM_VENDOR_BY_ID = {vendor.id: vendor for vendor in LLM_VENDORS}


def get_llm_vendor(vendor_id: str) -> LLMVendor:
    normalized = vendor_id.strip().lower().replace("-", "_")
    try:
        return LLM_VENDOR_BY_ID[normalized]
    except KeyError as error:
        allowed = ", ".join(vendor.id for vendor in LLM_VENDORS)
        raise ValueError(f"Unsupported LLM vendor '{vendor_id}'. Expected one of: {allowed}") from error


def apply_llm_vendor_chat_policy(vendor_id: str | None, params: dict[str, Any]) -> dict[str, Any]:
    """Normalize OpenAI Chat Completions parameters for a vendor compatibility layer."""
    vendor = get_llm_vendor(vendor_id or "openai")
    normalized = dict(params)

    seed = normalized.pop("seed", None)
    if seed is not None and vendor.supports_seed:
        if vendor.seed_parameter == "seed":
            normalized["seed"] = seed
        else:
            extra_body = dict(normalized.get("extra_body") or {})
            extra_body[vendor.seed_parameter] = seed
            normalized["extra_body"] = extra_body

    if not vendor.send_n:
        normalized.pop("n", None)

    if not normalized.get("stream") or not vendor.supports_stream_usage:
        normalized.pop("stream_options", None)

    temperature = normalized.get("temperature")
    if isinstance(temperature, (int, float)):
        if vendor.max_temperature is not None:
            normalized["temperature"] = min(float(temperature), vendor.max_temperature)
        if vendor.id == "groq" and normalized["temperature"] == 0:
            normalized["temperature"] = 1e-8

    return {key: value for key, value in normalized.items() if value is not None}


def infer_llm_vendor(document: dict[str, Any]) -> LLMVendor:
    stored_vendor = str(document.get("vendor") or "").strip()
    if stored_vendor:
        return get_llm_vendor(stored_vendor)

    provider = parse_model_provider(str(document.get("provider") or ""))
    if provider == ModelProvider.AZURE_OPENAI:
        return LLM_VENDOR_BY_ID["azure_openai"]
    if provider == ModelProvider.OPENAI:
        return LLM_VENDOR_BY_ID["openai"]

    searchable = " ".join(
        str(document.get(field) or "").lower()
        for field in ("name", "base_url", "endpoint")
    )
    fingerprints = (
        ("google_gemini", ("gemini", "generativelanguage.googleapis.com")),
        ("anthropic_claude", ("anthropic", "claude", "api.anthropic.com")),
        ("ollama", ("ollama", ":11434")),
        ("groq", ("groq", "api.groq.com")),
        ("openrouter", ("openrouter",)),
        ("mistral", ("mistral",)),
        ("deepseek", ("deepseek",)),
        ("together", ("together", "api.together.xyz")),
        ("vllm", ("vllm",)),
        ("localai", ("localai",)),
    )
    for vendor_id, terms in fingerprints:
        if any(term in searchable for term in terms):
            return LLM_VENDOR_BY_ID[vendor_id]
    return LLM_VENDOR_BY_ID["other_openai_compatible"]
